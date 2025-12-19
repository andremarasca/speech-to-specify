"""Session manager for lifecycle and state transitions.

This module manages session lifecycle following the state machine
defined in data-model.md. It enforces state transition rules and
maintains session immutability after finalization.

Extended for 003-auto-session-audio with:
- handle_audio_receipt(): Auto-create session on audio
- get_or_create_session(): Get or create active session
- update_session_name(): Update session intelligible name
- SessionMatcher integration: Index updated on session changes
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.lib.timestamps import generate_id, generate_timestamp
from src.models.session import (
    AudioEntry,
    ErrorEntry,
    NameSource,
    Session,
    SessionState,
    TranscriptionStatus,
)
from src.services.session.storage import SessionStorage, SessionStorageError
from src.services.session.name_generator import get_name_generator
from src.services.session.matcher import get_session_matcher

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

    # =========================================================================
    # Auto-Session Methods (003-auto-session-audio)
    # =========================================================================

    def get_or_create_session(self, chat_id: int) -> tuple[Session, bool]:
        """
        Get active session or create new one.

        If an active session exists, returns it.
        Otherwise, creates a new session with fallback name.

        Args:
            chat_id: Telegram chat ID

        Returns:
            Tuple of (session, was_created)
        """
        active = self.get_active_session()
        if active:
            return (active, False)

        # Create new session with intelligible name
        session = self._create_session_with_name(chat_id)
        return (session, True)

    def _create_session_with_name(self, chat_id: int) -> Session:
        """
        Create a new session with fallback intelligible name.

        Internal method that creates session with proper naming.
        """
        # Generate unique session ID
        session_id = generate_id()
        counter = 0
        while self.storage.exists(session_id):
            counter += 1
            session_id = f"{generate_id()}_{counter:02d}"

        created_at = generate_timestamp()

        # Generate fallback name
        name_generator = get_name_generator()
        fallback_name = name_generator.generate_fallback_name(created_at)

        # Ensure uniqueness against existing session names
        existing_names = self._get_all_session_names()
        intelligible_name = name_generator.ensure_unique(fallback_name, existing_names)

        # Create session with name
        session = Session(
            id=session_id,
            state=SessionState.COLLECTING,
            created_at=created_at,
            chat_id=chat_id,
            intelligible_name=intelligible_name,
            name_source=NameSource.FALLBACK_TIMESTAMP,
        )

        # Create folder structure and save
        self.storage.create_session_folders(session)
        self.storage.save(session)

        # Update SessionMatcher index
        self._update_matcher_index(session)

        logger.info(
            f"Created session {session.id} with name '{intelligible_name}' for chat {chat_id}"
        )
        return session

    def _get_all_session_names(self) -> set[str]:
        """Get all existing session intelligible names."""
        try:
            return set(self.storage.get_session_names().values())
        except Exception:
            return set()

    def _update_matcher_index(self, session: Session) -> None:
        """Update SessionMatcher index for a session."""
        try:
            matcher = get_session_matcher()
            if session.intelligible_name:
                matcher.update_session(
                    session.id,
                    session.intelligible_name,
                    session.embedding
                )
                logger.debug(f"Updated matcher index for session {session.id}")
        except Exception as e:
            # Don't let matcher errors break session operations
            logger.warning(f"Failed to update matcher index: {e}")

    def _remove_from_matcher_index(self, session_id: str) -> None:
        """Remove session from SessionMatcher index."""
        try:
            matcher = get_session_matcher()
            matcher.remove_session(session_id)
            logger.debug(f"Removed session {session_id} from matcher index")
        except Exception as e:
            logger.warning(f"Failed to remove from matcher index: {e}")

    def handle_audio_receipt(
        self,
        chat_id: int,
        audio_data: bytes,
        telegram_file_id: str,
        duration_seconds: Optional[float] = None,
    ) -> tuple[Session, AudioEntry]:
        """
        Handle incoming audio with automatic session creation.

        Flow:
        1. Get or create active session
        2. Save audio to session folder
        3. Create and link AudioEntry
        4. Return session and audio entry

        This method guarantees zero data loss - audio is persisted
        to the session folder before any other operation.

        Args:
            chat_id: Telegram chat ID
            audio_data: Raw audio bytes
            telegram_file_id: Telegram file ID for re-download
            duration_seconds: Audio duration if known

        Returns:
            Tuple of (session, audio_entry)

        Raises:
            AudioPersistenceError: If audio cannot be saved
        """
        from src.lib.exceptions import AudioPersistenceError

        # Step 1: Get or create session
        session, was_created = self.get_or_create_session(chat_id)

        if was_created:
            logger.info(f"Auto-created session {session.id} for incoming audio")

        # Step 2: Save audio to session folder
        sequence = session.next_sequence
        audio_filename = f"{sequence:03d}_audio.ogg"
        audio_path = session.audio_path(self.sessions_dir) / audio_filename

        try:
            audio_path.write_bytes(audio_data)
            logger.debug(f"Saved audio to {audio_path}")
        except Exception as e:
            logger.error(f"Failed to save audio: {e}")
            raise AudioPersistenceError(f"Failed to save audio: {e}") from e

        # Step 3: Create AudioEntry
        audio_entry = AudioEntry(
            sequence=sequence,
            received_at=generate_timestamp(),
            telegram_file_id=telegram_file_id,
            local_filename=audio_filename,
            file_size_bytes=len(audio_data),
            duration_seconds=duration_seconds,
            transcription_status=TranscriptionStatus.PENDING,
        )

        # Step 4: Link to session and persist
        session.audio_entries.append(audio_entry)
        self.storage.save(session)

        logger.info(
            f"Added audio #{sequence} to session {session.id} "
            f"({len(audio_data)} bytes, {duration_seconds}s)"
        )

        return (session, audio_entry)

    def update_session_name(
        self,
        session_id: str,
        new_name: str,
        source: NameSource,
    ) -> Session:
        """
        Update session's intelligible name.

        Only updates if:
        - source priority > current source priority
        - OR source == USER_ASSIGNED (always wins)

        Priority order: FALLBACK < TRANSCRIPTION < LLM_TITLE < USER_ASSIGNED

        Args:
            session_id: Session to update
            new_name: New intelligible name
            source: Origin of the new name

        Returns:
            Updated session (may be unchanged if priority too low)

        Raises:
            SessionStorageError: If session not found
        """
        session = self.storage.load(session_id)
        if not session:
            raise SessionStorageError(f"Session {session_id} not found")

        # Priority order (index = priority level)
        priority_order = [
            NameSource.FALLBACK_TIMESTAMP,
            NameSource.TRANSCRIPTION,
            NameSource.LLM_TITLE,
            NameSource.USER_ASSIGNED,
        ]

        current_priority = priority_order.index(session.name_source)
        new_priority = priority_order.index(source)

        # Only update if new source has higher priority
        if new_priority > current_priority:
            old_name = session.intelligible_name
            session.intelligible_name = new_name
            session.name_source = source
            self.storage.save(session)

            # Update SessionMatcher index with new name
            self._update_matcher_index(session)

            logger.info(
                f"Updated session {session_id} name: '{old_name}' → '{new_name}' "
                f"({session.name_source.value})"
            )
        else:
            logger.debug(
                f"Skipped name update for {session_id}: "
                f"{source.value} priority <= {session.name_source.value}"
            )

        return session

    def resolve_session_reference(
        self,
        reference: str,
        active_session_id: Optional[str] = None
    ) -> "SessionMatch":
        """
        Resolve a natural language reference to a session.

        Uses SessionMatcher to find session by:
        1. Empty reference → active session
        2. Exact substring match
        3. Fuzzy match (Levenshtein ≤ 2)
        4. Semantic similarity (if embeddings available)

        Args:
            reference: User's natural language reference
            active_session_id: Currently active session ID

        Returns:
            SessionMatch with resolved session or ambiguity info
        """
        from src.models.session import SessionMatch

        matcher = get_session_matcher()
        return matcher.resolve(reference, active_session_id)

    def rebuild_session_index(self) -> None:
        """
        Rebuild SessionMatcher index from all sessions.

        Call this on startup to populate the matcher with existing sessions.
        """
        matcher = get_session_matcher()
        matcher.rebuild_index()

        # Add all sessions to index
        sessions = self.storage.list_all_sessions()
        for session in sessions:
            if session.intelligible_name:
                matcher.update_session(
                    session.id,
                    session.intelligible_name,
                    session.embedding
                )

        logger.info(f"Rebuilt session index with {len(sessions)} sessions")
