"""Integration tests for session workflow.

These tests validate the complete workflow from /start to /process,
testing the integration between all components.
"""

import pytest
from datetime import datetime, timezone
from pathlib import Path

from src.models.session import (
    AudioEntry,
    Session,
    SessionState,
    TranscriptionStatus,
)
from src.services.session.storage import SessionStorage
from src.services.session.manager import SessionManager, InvalidStateError


@pytest.fixture
def sessions_dir(tmp_path: Path) -> Path:
    """Create a temporary sessions directory."""
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    return sessions


@pytest.fixture
def manager(sessions_dir: Path) -> SessionManager:
    """Create a SessionManager instance."""
    storage = SessionStorage(sessions_dir)
    return SessionManager(storage)


def create_audio_entry(sequence: int, filename: str = None) -> AudioEntry:
    """Helper to create audio entries."""
    if filename is None:
        filename = f"{sequence:03d}_audio.ogg"
    return AudioEntry(
        sequence=sequence,
        received_at=datetime.now(timezone.utc),
        telegram_file_id=f"file_id_{sequence}",
        local_filename=filename,
        file_size_bytes=1024 * sequence,
        duration_seconds=10.0 * sequence,
    )


class TestFullSessionWorkflow:
    """Test complete session lifecycle from start to process."""

    def test_create_collect_finalize_workflow(self, manager: SessionManager):
        """Test basic workflow: create → add audios → finalize."""
        # 1. Create session
        session = manager.create_session(chat_id=12345)
        assert session.state == SessionState.COLLECTING
        assert session.audio_count == 0

        # 2. Add audio entries
        for i in range(3):
            audio = create_audio_entry(i + 1)
            manager.add_audio(session.id, audio)

        # Verify audios added
        updated = manager.get_session(session.id)
        assert updated.audio_count == 3

        # 3. Finalize session
        finalized = manager.finalize_session(session.id)
        assert finalized.state == SessionState.TRANSCRIBING
        assert finalized.finalized_at is not None

    def test_transcription_status_updates(self, manager: SessionManager):
        """Test updating transcription status for each audio."""
        session = manager.create_session(chat_id=12345)

        # Add audios
        for i in range(2):
            manager.add_audio(session.id, create_audio_entry(i + 1))

        # Finalize
        manager.finalize_session(session.id)

        # Update transcription status
        manager.update_transcription_status(
            session.id, 1, TranscriptionStatus.SUCCESS, "001_audio.txt"
        )
        manager.update_transcription_status(
            session.id, 2, TranscriptionStatus.SUCCESS, "002_audio.txt"
        )

        # Verify
        updated = manager.get_session(session.id)
        assert updated.audio_entries[0].transcription_status == TranscriptionStatus.SUCCESS
        assert updated.audio_entries[0].transcript_filename == "001_audio.txt"
        assert updated.audio_entries[1].transcription_status == TranscriptionStatus.SUCCESS

    def test_full_state_machine_transitions(self, manager: SessionManager):
        """Test all state transitions in order."""
        # COLLECTING
        session = manager.create_session(chat_id=12345)
        assert session.state == SessionState.COLLECTING

        # Add audio and finalize
        manager.add_audio(session.id, create_audio_entry(1))

        # COLLECTING → TRANSCRIBING
        manager.finalize_session(session.id)
        session = manager.get_session(session.id)
        assert session.state == SessionState.TRANSCRIBING

        # TRANSCRIBING → TRANSCRIBED
        manager.transition_state(session.id, SessionState.TRANSCRIBED)
        session = manager.get_session(session.id)
        assert session.state == SessionState.TRANSCRIBED

        # TRANSCRIBED → PROCESSING
        manager.transition_state(session.id, SessionState.PROCESSING)
        session = manager.get_session(session.id)
        assert session.state == SessionState.PROCESSING

        # PROCESSING → PROCESSED
        manager.transition_state(session.id, SessionState.PROCESSED)
        session = manager.get_session(session.id)
        assert session.state == SessionState.PROCESSED

    def test_invalid_transition_raises(self, manager: SessionManager):
        """Test that invalid state transitions raise errors."""
        session = manager.create_session(chat_id=12345)
        manager.add_audio(session.id, create_audio_entry(1))

        # Cannot go directly from COLLECTING to TRANSCRIBED
        with pytest.raises(InvalidStateError):
            manager.transition_state(session.id, SessionState.TRANSCRIBED)

    def test_session_folder_structure(self, manager: SessionManager, sessions_dir: Path):
        """Test that all required folders are created."""
        session = manager.create_session(chat_id=12345)
        session_path = sessions_dir / session.id

        # Check folders exist
        assert session_path.exists()
        assert (session_path / "audio").exists()
        assert (session_path / "transcripts").exists()
        assert (session_path / "process").exists()
        assert (session_path / "metadata.json").exists()

    def test_multiple_sessions_lifecycle(self, manager: SessionManager):
        """Test creating multiple sessions with auto-finalize."""
        # Create first session with audio
        s1 = manager.create_session(chat_id=12345)
        manager.add_audio(s1.id, create_audio_entry(1))

        # Create second session (should auto-finalize first)
        s2 = manager.create_session(chat_id=12345)

        # Verify first session was auto-finalized
        s1_reloaded = manager.get_session(s1.id)
        assert s1_reloaded.state == SessionState.TRANSCRIBING

        # Verify second session is COLLECTING
        assert s2.state == SessionState.COLLECTING

        # Verify only s2 is active
        active = manager.get_active_session()
        assert active.id == s2.id


class TestCleanupOldSessions:
    """Test session cleanup functionality."""

    def test_cleanup_old_processed_sessions(self, manager: SessionManager):
        """Test that old processed sessions are cleaned up."""
        # Create and process a session
        session = manager.create_session(chat_id=12345)
        manager.add_audio(session.id, create_audio_entry(1))
        manager.finalize_session(session.id)
        manager.transition_state(session.id, SessionState.TRANSCRIBED)
        manager.transition_state(session.id, SessionState.PROCESSING)
        manager.transition_state(session.id, SessionState.PROCESSED)

        # Verify session exists
        assert manager.get_session(session.id) is not None

        # Cleanup with 0 days max age
        cleaned = manager.cleanup_old_sessions(max_age_days=0)
        assert cleaned == 1

        # Verify session was deleted
        assert manager.get_session(session.id) is None

    def test_cleanup_preserves_recent_sessions(self, manager: SessionManager):
        """Test that recent sessions are not cleaned up."""
        session = manager.create_session(chat_id=12345)
        manager.add_audio(session.id, create_audio_entry(1))
        manager.finalize_session(session.id)
        manager.transition_state(session.id, SessionState.TRANSCRIBED)
        manager.transition_state(session.id, SessionState.PROCESSING)
        manager.transition_state(session.id, SessionState.PROCESSED)

        # Cleanup with 30 days max age (session is recent)
        cleaned = manager.cleanup_old_sessions(max_age_days=30)
        assert cleaned == 0

        # Verify session still exists
        assert manager.get_session(session.id) is not None
