"""Contract tests for checkpoint persistence.

Per contracts for 005-telegram-ux-overhaul.

These tests verify:
1. Checkpoint save/load cycle works correctly
2. Orphaned session detection works
3. Session recovery transitions correctly
"""

import json
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from src.models.session import Session, SessionState
from src.models.ui_state import CheckpointData, UIState, KeyboardType
from src.services.session.checkpoint import (
    save_checkpoint,
    load_checkpoint,
    clear_checkpoint,
    has_checkpoint,
    is_orphaned_session,
    find_orphaned_sessions,
    recover_session,
)


@pytest.fixture
def temp_sessions_dir():
    """Create a temporary sessions directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_session() -> Session:
    """Create a sample session for testing."""
    return Session(
        id="2025-12-19_15-30-00",
        state=SessionState.COLLECTING,
        created_at=datetime.now(),
        chat_id=123456789,
        intelligible_name="Test Session",
    )


class TestSaveCheckpoint:
    """Tests for save_checkpoint function."""

    def test_save_checkpoint_creates_checkpoint_data(
        self, temp_sessions_dir: Path, sample_session: Session
    ):
        """save_checkpoint should create CheckpointData on session."""
        checkpoint = save_checkpoint(
            session=sample_session,
            sessions_root=temp_sessions_dir,
            audio_sequence=3,
            processing_state="receiving_audio",
        )
        
        assert checkpoint is not None
        assert checkpoint.last_audio_sequence == 3
        assert checkpoint.processing_state == "receiving_audio"
        assert sample_session.checkpoint_data == checkpoint

    def test_save_checkpoint_persists_to_disk(
        self, temp_sessions_dir: Path, sample_session: Session
    ):
        """save_checkpoint should persist session to disk."""
        save_checkpoint(
            session=sample_session,
            sessions_root=temp_sessions_dir,
            audio_sequence=1,
        )
        
        metadata_path = sample_session.metadata_path(temp_sessions_dir)
        assert metadata_path.exists()
        
        with open(metadata_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        assert data["id"] == sample_session.id
        assert data["checkpoint_data"] is not None
        assert data["checkpoint_data"]["last_audio_sequence"] == 1

    def test_save_checkpoint_includes_ui_state(
        self, temp_sessions_dir: Path, sample_session: Session
    ):
        """save_checkpoint should include UI state if provided."""
        ui_state = UIState(
            status_message_id=12345,
            last_keyboard_type=KeyboardType.SESSION_ACTIVE,
        )
        
        checkpoint = save_checkpoint(
            session=sample_session,
            sessions_root=temp_sessions_dir,
            audio_sequence=2,
            ui_state=ui_state,
        )
        
        assert checkpoint.ui_state is not None
        assert checkpoint.ui_state.status_message_id == 12345


class TestLoadCheckpoint:
    """Tests for load_checkpoint function."""

    def test_load_checkpoint_returns_checkpoint_data(
        self, temp_sessions_dir: Path, sample_session: Session
    ):
        """load_checkpoint should return checkpoint data from session."""
        save_checkpoint(
            session=sample_session,
            sessions_root=temp_sessions_dir,
            audio_sequence=5,
        )
        
        checkpoint = load_checkpoint(sample_session)
        
        assert checkpoint is not None
        assert checkpoint.last_audio_sequence == 5

    def test_load_checkpoint_returns_none_if_no_checkpoint(
        self, sample_session: Session
    ):
        """load_checkpoint should return None if no checkpoint exists."""
        assert load_checkpoint(sample_session) is None


class TestClearCheckpoint:
    """Tests for clear_checkpoint function."""

    def test_clear_checkpoint_removes_checkpoint_data(
        self, temp_sessions_dir: Path, sample_session: Session
    ):
        """clear_checkpoint should remove checkpoint data from session."""
        save_checkpoint(
            session=sample_session,
            sessions_root=temp_sessions_dir,
            audio_sequence=3,
        )
        assert sample_session.checkpoint_data is not None
        
        clear_checkpoint(sample_session, temp_sessions_dir)
        
        assert sample_session.checkpoint_data is None

    def test_clear_checkpoint_persists_to_disk(
        self, temp_sessions_dir: Path, sample_session: Session
    ):
        """clear_checkpoint should persist changes to disk."""
        save_checkpoint(
            session=sample_session,
            sessions_root=temp_sessions_dir,
            audio_sequence=3,
        )
        
        clear_checkpoint(sample_session, temp_sessions_dir)
        
        metadata_path = sample_session.metadata_path(temp_sessions_dir)
        with open(metadata_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        assert data["checkpoint_data"] is None


class TestHasCheckpoint:
    """Tests for has_checkpoint function."""

    def test_has_checkpoint_returns_true_when_checkpoint_exists(
        self, temp_sessions_dir: Path, sample_session: Session
    ):
        """has_checkpoint should return True when checkpoint exists."""
        save_checkpoint(
            session=sample_session,
            sessions_root=temp_sessions_dir,
            audio_sequence=1,
        )
        
        assert has_checkpoint(sample_session) is True

    def test_has_checkpoint_returns_false_when_no_checkpoint(
        self, sample_session: Session
    ):
        """has_checkpoint should return False when no checkpoint."""
        assert has_checkpoint(sample_session) is False


class TestIsOrphanedSession:
    """Tests for is_orphaned_session function."""

    def test_orphaned_session_with_checkpoint_and_audio(
        self, temp_sessions_dir: Path, sample_session: Session
    ):
        """Session is orphaned if it has checkpoint, audio, and is in COLLECTING state."""
        from src.models.session import AudioEntry, TranscriptionStatus
        
        sample_session.audio_entries.append(
            AudioEntry(
                sequence=1,
                received_at=datetime.now(),
                telegram_file_id="abc123",
                local_filename="001_audio.ogg",
                file_size_bytes=1000,
                transcription_status=TranscriptionStatus.PENDING,
            )
        )
        
        save_checkpoint(
            session=sample_session,
            sessions_root=temp_sessions_dir,
            audio_sequence=1,
        )
        
        assert is_orphaned_session(sample_session) is True

    def test_not_orphaned_without_checkpoint(self, sample_session: Session):
        """Session is not orphaned without checkpoint."""
        assert is_orphaned_session(sample_session) is False

    def test_not_orphaned_if_finalized(
        self, temp_sessions_dir: Path, sample_session: Session
    ):
        """Session is not orphaned if already finalized."""
        sample_session.state = SessionState.TRANSCRIBED
        
        save_checkpoint(
            session=sample_session,
            sessions_root=temp_sessions_dir,
            audio_sequence=1,
        )
        
        assert is_orphaned_session(sample_session) is False

    def test_orphaned_if_interrupted_state(
        self, temp_sessions_dir: Path, sample_session: Session
    ):
        """Session is orphaned if in INTERRUPTED state with audio."""
        from src.models.session import AudioEntry, TranscriptionStatus
        
        sample_session.state = SessionState.INTERRUPTED
        sample_session.audio_entries.append(
            AudioEntry(
                sequence=1,
                received_at=datetime.now(),
                telegram_file_id="abc123",
                local_filename="001_audio.ogg",
                file_size_bytes=1000,
                transcription_status=TranscriptionStatus.PENDING,
            )
        )
        
        save_checkpoint(
            session=sample_session,
            sessions_root=temp_sessions_dir,
            audio_sequence=1,
        )
        
        assert is_orphaned_session(sample_session) is True


class TestFindOrphanedSessions:
    """Tests for find_orphaned_sessions function."""

    def test_find_orphaned_sessions_returns_empty_for_new_dir(
        self, temp_sessions_dir: Path
    ):
        """find_orphaned_sessions returns empty list for new directory."""
        orphaned = find_orphaned_sessions(temp_sessions_dir)
        assert orphaned == []

    def test_find_orphaned_sessions_finds_orphaned(
        self, temp_sessions_dir: Path
    ):
        """find_orphaned_sessions finds orphaned sessions."""
        from src.models.session import AudioEntry, TranscriptionStatus
        
        session = Session(
            id="2025-12-19_15-30-00",
            state=SessionState.COLLECTING,
            created_at=datetime.now(),
            chat_id=123456789,
        )
        session.audio_entries.append(
            AudioEntry(
                sequence=1,
                received_at=datetime.now(),
                telegram_file_id="abc123",
                local_filename="001_audio.ogg",
                file_size_bytes=1000,
                transcription_status=TranscriptionStatus.PENDING,
            )
        )
        
        save_checkpoint(
            session=session,
            sessions_root=temp_sessions_dir,
            audio_sequence=1,
        )
        
        orphaned = find_orphaned_sessions(temp_sessions_dir)
        
        assert len(orphaned) == 1
        assert orphaned[0].id == session.id


class TestRecoverSession:
    """Tests for recover_session function."""

    def test_recover_session_transitions_to_collecting(
        self, temp_sessions_dir: Path
    ):
        """recover_session transitions INTERRUPTED to COLLECTING."""
        from src.models.session import AudioEntry, TranscriptionStatus
        
        session = Session(
            id="2025-12-19_15-30-00",
            state=SessionState.INTERRUPTED,
            created_at=datetime.now(),
            chat_id=123456789,
        )
        session.audio_entries.append(
            AudioEntry(
                sequence=1,
                received_at=datetime.now(),
                telegram_file_id="abc123",
                local_filename="001_audio.ogg",
                file_size_bytes=1000,
                transcription_status=TranscriptionStatus.PENDING,
            )
        )
        
        save_checkpoint(
            session=session,
            sessions_root=temp_sessions_dir,
            audio_sequence=1,
        )
        
        recovered = recover_session(session, temp_sessions_dir)
        
        assert recovered.state == SessionState.COLLECTING
        assert recovered.checkpoint_data is None
        assert recovered.audio_count == 1  # Audio preserved

    def test_recover_session_clears_checkpoint(
        self, temp_sessions_dir: Path, sample_session: Session
    ):
        """recover_session clears checkpoint data."""
        save_checkpoint(
            session=sample_session,
            sessions_root=temp_sessions_dir,
            audio_sequence=1,
        )
        
        recovered = recover_session(sample_session, temp_sessions_dir)
        
        assert recovered.checkpoint_data is None
