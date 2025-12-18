"""Session manager for lifecycle and state transitions.

This module manages session lifecycle following the state machine
defined in data-model.md. It enforces state transition rules and
maintains session immutability after finalization.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.lib.timestamps import generate_id, generate_timestamp
from src.models.session import (
    AudioEntry,
    ErrorEntry,
    Session,
    SessionState,
    TranscriptionStatus,
)
from src.services.session.storage import SessionStorage, SessionStorageError

logger = logging.getLogger(__name__)


class InvalidStateError(Exception):
    """Raised when an operation is invalid for the current session state."""

    pass


class SessionManager:
    """
    Manage session lifecycle, state transitions, and persistence.

    Implements the SessionManager interface from contracts/session-manager.md.
    Ensures state transitions follow the rules defined in data-model.md.
    """

    def __init__(self, storage: SessionStorage):
        """
        Initialize session manager.

        Args:
            storage: SessionStorage instance for persistence
        """
        self.storage = storage

    @property
    def sessions_dir(self) -> Path:
        """Get the sessions directory."""
        return self.storage.sessions_dir

    def get_active_session(self) -> Optional[Session]:
        """
        Return current session in COLLECTING state, or None.

        Only one session can be in COLLECTING state at a time.
        """
        sessions = self.storage.list_sessions(limit=50)  # Check recent sessions

        for session in sessions:
            if session.state == SessionState.COLLECTING:
                return session

        return None

    def create_session(self, chat_id: int) -> Session:
        """
        Create a new session.

        If an active session exists, it will be auto-finalized first.
        This implements the auto-finalize policy from spec.md FR-004.

        Args:
            chat_id: Telegram chat ID for this session

        Returns:
            The newly created session
        """
        # Auto-finalize existing active session
        active = self.get_active_session()
        if active:
            logger.info(f"Auto-finalizing existing session {active.id}")
            try:
                self._transition_to_transcribing(active)
            except InvalidStateError:
                # If can't finalize (no audios), just mark as error
                active.state = SessionState.ERROR
                active.errors.append(
                    ErrorEntry(
                        timestamp=generate_timestamp(),
                        operation="auto-finalize",
                        message="Auto-finalized due to new session start (no audios)",
                        recoverable=False,
                    )
                )
                self.storage.save(active)

        # Generate unique session ID
        session_id = generate_id()

        # Ensure uniqueness (edge case: multiple starts within same second)
        counter = 0
        while self.storage.exists(session_id):
            counter += 1
            session_id = f"{generate_id()}_{counter:02d}"

        # Create new session
        session = Session(
            id=session_id,
            state=SessionState.COLLECTING,
            created_at=generate_timestamp(),
            chat_id=chat_id,
        )

        # Create folder structure and save
        self.storage.create_session_folders(session)
        self.storage.save(session)

        logger.info(f"Created new session {session.id} for chat {chat_id}")
        return session

    def finalize_session(self, session_id: str) -> Session:
        """
        Finalize session (COLLECTING → TRANSCRIBING).

        Args:
            session_id: Session to finalize

        Returns:
            Updated session

        Raises:
            InvalidStateError: If session not in COLLECTING state or no audios
        """
        session = self.storage.load(session_id)
        if not session:
            raise SessionStorageError(f"Session {session_id} not found")

        return self._transition_to_transcribing(session)

    def _transition_to_transcribing(self, session: Session) -> Session:
        """Internal method to transition session to TRANSCRIBING."""
        if session.state != SessionState.COLLECTING:
            raise InvalidStateError(
                f"Cannot finalize session in {session.state.value} state"
            )

        if session.audio_count == 0:
            raise InvalidStateError("Cannot finalize session with no audio entries")

        session.state = SessionState.TRANSCRIBING
        session.finalized_at = generate_timestamp()
        self.storage.save(session)

        logger.info(
            f"Finalized session {session.id} with {session.audio_count} audio(s)"
        )
        return session

    def add_audio(self, session_id: str, audio_entry: AudioEntry) -> Session:
        """
        Add audio entry to session.

        Args:
            session_id: Session to add audio to
            audio_entry: Audio entry to add

        Returns:
            Updated session

        Raises:
            InvalidStateError: If session not in COLLECTING state
        """
        session = self.storage.load(session_id)
        if not session:
            raise SessionStorageError(f"Session {session_id} not found")

        if not session.can_add_audio:
            raise InvalidStateError(
                f"Cannot add audio to session in {session.state.value} state"
            )

        session.audio_entries.append(audio_entry)
        self.storage.save(session)

        logger.info(
            f"Added audio #{audio_entry.sequence} to session {session.id}"
        )
        return session

    def update_transcription_status(
        self,
        session_id: str,
        sequence: int,
        status: TranscriptionStatus,
        transcript_filename: Optional[str] = None,
    ) -> Session:
        """
        Update transcription status for specific audio entry.

        Args:
            session_id: Session containing the audio
            sequence: Sequence number of the audio entry
            status: New transcription status
            transcript_filename: Filename of the transcript (if successful)

        Returns:
            Updated session
        """
        session = self.storage.load(session_id)
        if not session:
            raise SessionStorageError(f"Session {session_id} not found")

        # Find the audio entry
        for entry in session.audio_entries:
            if entry.sequence == sequence:
                entry.transcription_status = status
                if transcript_filename:
                    entry.transcript_filename = transcript_filename
                break
        else:
            raise ValueError(f"Audio entry with sequence {sequence} not found")

        self.storage.save(session)

        logger.debug(
            f"Updated transcription status for audio #{sequence} in session {session.id}: {status.value}"
        )
        return session

    def transition_state(self, session_id: str, new_state: SessionState) -> Session:
        """
        Transition session to new state.

        Validates transition is allowed according to state machine.

        Args:
            session_id: Session to transition
            new_state: Target state

        Returns:
            Updated session

        Raises:
            InvalidStateError: If transition not allowed
        """
        session = self.storage.load(session_id)
        if not session:
            raise SessionStorageError(f"Session {session_id} not found")

        if not session.state.can_transition_to(new_state):
            raise InvalidStateError(
                f"Cannot transition from {session.state.value} to {new_state.value}"
            )

        old_state = session.state
        session.state = new_state

        # Set finalized_at if transitioning from COLLECTING
        if old_state == SessionState.COLLECTING and session.finalized_at is None:
            session.finalized_at = generate_timestamp()

        self.storage.save(session)

        logger.info(
            f"Session {session.id} transitioned: {old_state.value} → {new_state.value}"
        )
        return session

    def add_error(self, session_id: str, error: ErrorEntry) -> Session:
        """
        Add error entry to session.

        Args:
            session_id: Session to add error to
            error: Error entry to add

        Returns:
            Updated session
        """
        session = self.storage.load(session_id)
        if not session:
            raise SessionStorageError(f"Session {session_id} not found")

        session.errors.append(error)
        self.storage.save(session)

        logger.warning(
            f"Error in session {session.id}: [{error.operation}] {error.message}"
        )
        return session

    def get_session(self, session_id: str) -> Optional[Session]:
        """Get session by ID."""
        return self.storage.load(session_id)

    def list_sessions(self, limit: int = 10) -> list[Session]:
        """List recent sessions, newest first."""
        return self.storage.list_sessions(limit)

    def get_session_path(self, session_id: str) -> Path:
        """Get filesystem path for session folder."""
        return self.sessions_dir / session_id

    def cleanup_old_sessions(
        self,
        max_age_days: int = 30,
        states: list[SessionState] | None = None,
    ) -> int:
        """
        Archive or delete old completed sessions.

        Args:
            max_age_days: Maximum age in days before cleanup
            states: Only cleanup sessions in these states (default: PROCESSED, ERROR)

        Returns:
            Number of sessions cleaned up
        """
        from datetime import timedelta

        if states is None:
            states = [SessionState.PROCESSED, SessionState.ERROR]

        cutoff = generate_timestamp() - timedelta(days=max_age_days)
        sessions = self.storage.list_sessions(limit=1000)
        cleaned = 0

        for session in sessions:
            if session.state not in states:
                continue

            if session.created_at < cutoff:
                logger.info(f"Cleaning up old session {session.id}")
                self.storage.delete(session.id)
                cleaned += 1

        logger.info(f"Cleaned up {cleaned} old sessions")
        return cleaned
