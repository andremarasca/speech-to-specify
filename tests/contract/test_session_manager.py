"""Contract tests for SessionManager.

These tests validate the SessionManager interface contract defined in
contracts/session-manager.md. Tests focus on:
- State transition rules (from data-model.md)
- Session creation with auto-finalize
- Audio entry management
- State machine enforcement
"""

import pytest
from datetime import datetime, timezone
from pathlib import Path

from src.models.session import (
    AudioEntry,
    ErrorEntry,
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
def storage(sessions_dir: Path) -> SessionStorage:
    """Create a SessionStorage instance."""
    return SessionStorage(sessions_dir)


@pytest.fixture
def manager(storage: SessionStorage) -> SessionManager:
    """Create a SessionManager instance."""
    return SessionManager(storage)


class TestSessionCreation:
    """Test session creation functionality."""

    def test_create_session_returns_new_session(self, manager: SessionManager):
        """Create should return a new session in COLLECTING state."""
        session = manager.create_session(chat_id=123456789)

        assert session is not None
        assert session.state == SessionState.COLLECTING
        assert session.chat_id == 123456789
        assert session.created_at is not None
        assert session.finalized_at is None

    def test_create_session_generates_unique_id(self, manager: SessionManager):
        """Created session should have timestamp-based ID."""
        session = manager.create_session(chat_id=123)

        # ID format: YYYY-MM-DD_HH-MM-SS
        assert len(session.id) >= 19
        assert "_" in session.id

    def test_create_session_persists_to_storage(self, manager: SessionManager):
        """Created session should be persisted immediately."""
        session = manager.create_session(chat_id=123)

        # Should be loadable from storage
        loaded = manager.get_session(session.id)
        assert loaded is not None
        assert loaded.id == session.id

    def test_create_session_creates_folders(
        self, manager: SessionManager, sessions_dir: Path
    ):
        """Created session should have folder structure."""
        session = manager.create_session(chat_id=123)

        session_path = sessions_dir / session.id
        assert session_path.exists()
        assert (session_path / "audio").exists()
        assert (session_path / "transcripts").exists()
        assert (session_path / "process").exists()


class TestAutoFinalize:
    """Test auto-finalize behavior when starting new session."""

    def test_auto_finalize_on_new_session(self, manager: SessionManager):
        """Starting new session should auto-finalize existing COLLECTING session."""
        # Create first session with audio
        session1 = manager.create_session(chat_id=123)
        audio_entry = AudioEntry(
            sequence=1,
            received_at=datetime.now(timezone.utc),
            telegram_file_id="file_123",
            local_filename="001_audio.ogg",
            file_size_bytes=1024,
        )
        manager.add_audio(session1.id, audio_entry)

        # Create second session - should auto-finalize first
        session2 = manager.create_session(chat_id=123)

        # First session should be finalized
        reloaded1 = manager.get_session(session1.id)
        assert reloaded1.state == SessionState.TRANSCRIBING
        assert reloaded1.finalized_at is not None

        # Second session should be collecting
        assert session2.state == SessionState.COLLECTING

    def test_auto_finalize_empty_session_becomes_error(self, manager: SessionManager):
        """Auto-finalizing session with no audio should mark as error."""
        # Create first session WITHOUT audio
        session1 = manager.create_session(chat_id=123)

        # Create second session - should error first (no audios)
        session2 = manager.create_session(chat_id=123)

        # First session should be in error state
        reloaded1 = manager.get_session(session1.id)
        assert reloaded1.state == SessionState.ERROR
        assert len(reloaded1.errors) > 0

        # Second session should be collecting
        assert session2.state == SessionState.COLLECTING


class TestGetActiveSession:
    """Test active session retrieval."""

    def test_no_active_session_returns_none(self, manager: SessionManager):
        """Should return None when no active session exists."""
        active = manager.get_active_session()
        assert active is None

    def test_returns_collecting_session(self, manager: SessionManager):
        """Should return session in COLLECTING state."""
        session = manager.create_session(chat_id=123)

        active = manager.get_active_session()
        assert active is not None
        assert active.id == session.id

    def test_finalized_session_not_active(self, manager: SessionManager):
        """Finalized session should not be returned as active."""
        session = manager.create_session(chat_id=123)

        # Add audio and finalize
        audio_entry = AudioEntry(
            sequence=1,
            received_at=datetime.now(timezone.utc),
            telegram_file_id="file_123",
            local_filename="001_audio.ogg",
            file_size_bytes=1024,
        )
        manager.add_audio(session.id, audio_entry)
        manager.finalize_session(session.id)

        active = manager.get_active_session()
        assert active is None


class TestAddAudio:
    """Test audio entry addition."""

    def test_add_audio_to_collecting_session(self, manager: SessionManager):
        """Should successfully add audio to COLLECTING session."""
        session = manager.create_session(chat_id=123)

        audio_entry = AudioEntry(
            sequence=1,
            received_at=datetime.now(timezone.utc),
            telegram_file_id="file_123",
            local_filename="001_audio.ogg",
            file_size_bytes=1024,
            duration_seconds=30.0,
        )

        updated = manager.add_audio(session.id, audio_entry)

        assert len(updated.audio_entries) == 1
        assert updated.audio_entries[0].sequence == 1

    def test_add_audio_to_finalized_session_raises(self, manager: SessionManager):
        """Should raise error when adding audio to finalized session."""
        session = manager.create_session(chat_id=123)

        # Add audio and finalize
        audio_entry = AudioEntry(
            sequence=1,
            received_at=datetime.now(timezone.utc),
            telegram_file_id="file_123",
            local_filename="001_audio.ogg",
            file_size_bytes=1024,
        )
        manager.add_audio(session.id, audio_entry)
        manager.finalize_session(session.id)

        # Try to add another audio
        another_audio = AudioEntry(
            sequence=2,
            received_at=datetime.now(timezone.utc),
            telegram_file_id="file_456",
            local_filename="002_audio.ogg",
            file_size_bytes=2048,
        )

        with pytest.raises(InvalidStateError):
            manager.add_audio(session.id, another_audio)


class TestFinalizeSession:
    """Test session finalization."""

    def test_finalize_with_audio(self, manager: SessionManager):
        """Should finalize session with at least one audio."""
        session = manager.create_session(chat_id=123)

        audio_entry = AudioEntry(
            sequence=1,
            received_at=datetime.now(timezone.utc),
            telegram_file_id="file_123",
            local_filename="001_audio.ogg",
            file_size_bytes=1024,
        )
        manager.add_audio(session.id, audio_entry)

        finalized = manager.finalize_session(session.id)

        assert finalized.state == SessionState.TRANSCRIBING
        assert finalized.finalized_at is not None

    def test_finalize_empty_session_raises(self, manager: SessionManager):
        """Should raise error when finalizing session with no audio."""
        session = manager.create_session(chat_id=123)

        with pytest.raises(InvalidStateError):
            manager.finalize_session(session.id)

    def test_finalize_already_finalized_raises(self, manager: SessionManager):
        """Should raise error when finalizing already finalized session."""
        session = manager.create_session(chat_id=123)

        audio_entry = AudioEntry(
            sequence=1,
            received_at=datetime.now(timezone.utc),
            telegram_file_id="file_123",
            local_filename="001_audio.ogg",
            file_size_bytes=1024,
        )
        manager.add_audio(session.id, audio_entry)
        manager.finalize_session(session.id)

        with pytest.raises(InvalidStateError):
            manager.finalize_session(session.id)


class TestStateTransitions:
    """Test state machine enforcement from data-model.md."""

    def test_collecting_to_transcribing(self, manager: SessionManager):
        """COLLECTING → TRANSCRIBING is allowed."""
        session = manager.create_session(chat_id=123)
        audio = AudioEntry(
            sequence=1,
            received_at=datetime.now(timezone.utc),
            telegram_file_id="f",
            local_filename="001_audio.ogg",
            file_size_bytes=100,
        )
        manager.add_audio(session.id, audio)

        updated = manager.transition_state(session.id, SessionState.TRANSCRIBING)
        assert updated.state == SessionState.TRANSCRIBING

    def test_transcribing_to_transcribed(self, manager: SessionManager):
        """TRANSCRIBING → TRANSCRIBED is allowed."""
        session = manager.create_session(chat_id=123)
        audio = AudioEntry(
            sequence=1,
            received_at=datetime.now(timezone.utc),
            telegram_file_id="f",
            local_filename="001_audio.ogg",
            file_size_bytes=100,
        )
        manager.add_audio(session.id, audio)
        manager.finalize_session(session.id)

        updated = manager.transition_state(session.id, SessionState.TRANSCRIBED)
        assert updated.state == SessionState.TRANSCRIBED

    def test_transcribed_to_processing(self, manager: SessionManager):
        """TRANSCRIBED → PROCESSING is allowed."""
        session = manager.create_session(chat_id=123)
        audio = AudioEntry(
            sequence=1,
            received_at=datetime.now(timezone.utc),
            telegram_file_id="f",
            local_filename="001_audio.ogg",
            file_size_bytes=100,
        )
        manager.add_audio(session.id, audio)
        manager.finalize_session(session.id)
        manager.transition_state(session.id, SessionState.TRANSCRIBED)

        updated = manager.transition_state(session.id, SessionState.PROCESSING)
        assert updated.state == SessionState.PROCESSING

    def test_processing_to_processed(self, manager: SessionManager):
        """PROCESSING → PROCESSED is allowed."""
        session = manager.create_session(chat_id=123)
        audio = AudioEntry(
            sequence=1,
            received_at=datetime.now(timezone.utc),
            telegram_file_id="f",
            local_filename="001_audio.ogg",
            file_size_bytes=100,
        )
        manager.add_audio(session.id, audio)
        manager.finalize_session(session.id)
        manager.transition_state(session.id, SessionState.TRANSCRIBED)
        manager.transition_state(session.id, SessionState.PROCESSING)

        updated = manager.transition_state(session.id, SessionState.PROCESSED)
        assert updated.state == SessionState.PROCESSED

    def test_any_to_error(self, manager: SessionManager):
        """Any state → ERROR is allowed."""
        session = manager.create_session(chat_id=123)

        updated = manager.transition_state(session.id, SessionState.ERROR)
        assert updated.state == SessionState.ERROR

    def test_invalid_transition_raises(self, manager: SessionManager):
        """Invalid transition should raise InvalidStateError."""
        session = manager.create_session(chat_id=123)

        # COLLECTING → PROCESSED is not allowed
        with pytest.raises(InvalidStateError):
            manager.transition_state(session.id, SessionState.PROCESSED)

    def test_error_is_terminal(self, manager: SessionManager):
        """ERROR state should be terminal (no transitions allowed)."""
        session = manager.create_session(chat_id=123)
        manager.transition_state(session.id, SessionState.ERROR)

        with pytest.raises(InvalidStateError):
            manager.transition_state(session.id, SessionState.COLLECTING)


class TestUpdateTranscriptionStatus:
    """Test transcription status updates."""

    def test_update_status_success(self, manager: SessionManager):
        """Should update transcription status and filename."""
        session = manager.create_session(chat_id=123)
        audio = AudioEntry(
            sequence=1,
            received_at=datetime.now(timezone.utc),
            telegram_file_id="f",
            local_filename="001_audio.ogg",
            file_size_bytes=100,
        )
        manager.add_audio(session.id, audio)

        updated = manager.update_transcription_status(
            session.id,
            sequence=1,
            status=TranscriptionStatus.SUCCESS,
            transcript_filename="001_audio.txt",
        )

        assert updated.audio_entries[0].transcription_status == TranscriptionStatus.SUCCESS
        assert updated.audio_entries[0].transcript_filename == "001_audio.txt"

    def test_update_status_invalid_sequence_raises(self, manager: SessionManager):
        """Should raise error for invalid sequence number."""
        session = manager.create_session(chat_id=123)

        with pytest.raises(ValueError):
            manager.update_transcription_status(
                session.id, sequence=99, status=TranscriptionStatus.FAILED
            )


class TestAddError:
    """Test error entry addition."""

    def test_add_error_entry(self, manager: SessionManager):
        """Should add error to session."""
        session = manager.create_session(chat_id=123)

        error = ErrorEntry(
            timestamp=datetime.now(timezone.utc),
            operation="download",
            target="file_xyz",
            message="Network timeout",
            recoverable=True,
        )

        updated = manager.add_error(session.id, error)

        assert len(updated.errors) == 1
        assert updated.errors[0].operation == "download"
