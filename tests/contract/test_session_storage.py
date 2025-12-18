"""Contract tests for SessionStorage.

These tests validate the SessionStorage interface contract defined in
contracts/session-manager.md. Tests focus on:
- Atomic write consistency (crash safety)
- Load/save round-trip integrity
- Session folder structure creation
"""

import json
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
from src.services.session.storage import (
    SessionStorage,
    SessionStorageError,
    SessionNotFoundError,
)


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
def sample_session() -> Session:
    """Create a sample session for testing."""
    return Session(
        id="2025-12-18_14-30-00",
        state=SessionState.COLLECTING,
        created_at=datetime(2025, 12, 18, 14, 30, 0, tzinfo=timezone.utc),
        chat_id=123456789,
    )


@pytest.fixture
def sample_session_with_audio() -> Session:
    """Create a sample session with audio entries."""
    session = Session(
        id="2025-12-18_15-00-00",
        state=SessionState.TRANSCRIBING,
        created_at=datetime(2025, 12, 18, 15, 0, 0, tzinfo=timezone.utc),
        chat_id=123456789,
        finalized_at=datetime(2025, 12, 18, 15, 10, 0, tzinfo=timezone.utc),
    )
    session.audio_entries = [
        AudioEntry(
            sequence=1,
            received_at=datetime(2025, 12, 18, 15, 1, 0, tzinfo=timezone.utc),
            telegram_file_id="file_abc123",
            local_filename="001_audio.ogg",
            file_size_bytes=102400,
            duration_seconds=30.5,
            transcription_status=TranscriptionStatus.SUCCESS,
            transcript_filename="001_audio.txt",
        ),
        AudioEntry(
            sequence=2,
            received_at=datetime(2025, 12, 18, 15, 2, 0, tzinfo=timezone.utc),
            telegram_file_id="file_def456",
            local_filename="002_audio.ogg",
            file_size_bytes=204800,
            duration_seconds=60.0,
            transcription_status=TranscriptionStatus.PENDING,
        ),
    ]
    session.errors = [
        ErrorEntry(
            timestamp=datetime(2025, 12, 18, 15, 5, 0, tzinfo=timezone.utc),
            operation="download",
            target="file_xyz789",
            message="Network timeout",
            recoverable=True,
        ),
    ]
    return session


class TestSessionStorageSaveLoad:
    """Test save/load round-trip integrity."""

    def test_save_creates_folder_and_metadata(
        self, storage: SessionStorage, sample_session: Session
    ):
        """Save should create session folder and metadata.json."""
        storage.save(sample_session)

        session_path = storage.sessions_dir / sample_session.id
        metadata_path = session_path / "metadata.json"

        assert session_path.exists()
        assert metadata_path.exists()

    def test_save_load_round_trip(
        self, storage: SessionStorage, sample_session: Session
    ):
        """Loaded session should match saved session."""
        storage.save(sample_session)
        loaded = storage.load(sample_session.id)

        assert loaded is not None
        assert loaded.id == sample_session.id
        assert loaded.state == sample_session.state
        assert loaded.chat_id == sample_session.chat_id
        assert loaded.created_at == sample_session.created_at

    def test_save_load_with_audio_entries(
        self, storage: SessionStorage, sample_session_with_audio: Session
    ):
        """Session with audio entries should survive round-trip."""
        storage.save(sample_session_with_audio)
        loaded = storage.load(sample_session_with_audio.id)

        assert loaded is not None
        assert len(loaded.audio_entries) == 2
        assert loaded.audio_entries[0].sequence == 1
        assert loaded.audio_entries[0].telegram_file_id == "file_abc123"
        assert loaded.audio_entries[0].transcription_status == TranscriptionStatus.SUCCESS
        assert loaded.audio_entries[1].transcription_status == TranscriptionStatus.PENDING

    def test_save_load_with_errors(
        self, storage: SessionStorage, sample_session_with_audio: Session
    ):
        """Session with error entries should survive round-trip."""
        storage.save(sample_session_with_audio)
        loaded = storage.load(sample_session_with_audio.id)

        assert loaded is not None
        assert len(loaded.errors) == 1
        assert loaded.errors[0].operation == "download"
        assert loaded.errors[0].recoverable is True

    def test_load_nonexistent_returns_none(self, storage: SessionStorage):
        """Load should return None for nonexistent session."""
        loaded = storage.load("nonexistent-session")
        assert loaded is None


class TestSessionStorageAtomicWrite:
    """Test atomic write behavior."""

    def test_metadata_is_valid_json(
        self, storage: SessionStorage, sample_session: Session
    ):
        """Saved metadata should be valid JSON."""
        storage.save(sample_session)

        metadata_path = storage.sessions_dir / sample_session.id / "metadata.json"
        with open(metadata_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["id"] == sample_session.id
        assert data["state"] == "COLLECTING"

    def test_save_overwrites_previous(
        self, storage: SessionStorage, sample_session: Session
    ):
        """Save should atomically overwrite previous state."""
        storage.save(sample_session)

        # Modify and save again
        sample_session.state = SessionState.TRANSCRIBING
        sample_session.finalized_at = datetime(2025, 12, 18, 15, 0, 0, tzinfo=timezone.utc)
        storage.save(sample_session)

        loaded = storage.load(sample_session.id)
        assert loaded.state == SessionState.TRANSCRIBING
        assert loaded.finalized_at is not None


class TestSessionStorageList:
    """Test session listing functionality."""

    def test_list_empty_returns_empty(self, storage: SessionStorage):
        """List on empty directory should return empty list."""
        sessions = storage.list_sessions()
        assert sessions == []

    def test_list_returns_sessions(self, storage: SessionStorage):
        """List should return saved sessions."""
        session1 = Session(
            id="2025-12-18_14-00-00",
            state=SessionState.COLLECTING,
            created_at=datetime(2025, 12, 18, 14, 0, 0, tzinfo=timezone.utc),
            chat_id=123,
        )
        session2 = Session(
            id="2025-12-18_15-00-00",
            state=SessionState.TRANSCRIBED,
            created_at=datetime(2025, 12, 18, 15, 0, 0, tzinfo=timezone.utc),
            chat_id=123,
        )

        storage.save(session1)
        storage.save(session2)

        sessions = storage.list_sessions()
        assert len(sessions) == 2

    def test_list_sorted_newest_first(self, storage: SessionStorage):
        """List should return sessions sorted by ID (newest first)."""
        session_old = Session(
            id="2025-12-18_10-00-00",
            state=SessionState.PROCESSED,
            created_at=datetime(2025, 12, 18, 10, 0, 0, tzinfo=timezone.utc),
            chat_id=123,
        )
        session_new = Session(
            id="2025-12-18_16-00-00",
            state=SessionState.COLLECTING,
            created_at=datetime(2025, 12, 18, 16, 0, 0, tzinfo=timezone.utc),
            chat_id=123,
        )

        storage.save(session_old)
        storage.save(session_new)

        sessions = storage.list_sessions()
        assert sessions[0].id == "2025-12-18_16-00-00"
        assert sessions[1].id == "2025-12-18_10-00-00"

    def test_list_respects_limit(self, storage: SessionStorage):
        """List should respect the limit parameter."""
        for i in range(5):
            session = Session(
                id=f"2025-12-18_{10+i:02d}-00-00",
                state=SessionState.PROCESSED,
                created_at=datetime(2025, 12, 18, 10 + i, 0, 0, tzinfo=timezone.utc),
                chat_id=123,
            )
            storage.save(session)

        sessions = storage.list_sessions(limit=3)
        assert len(sessions) == 3


class TestSessionStorageFolderStructure:
    """Test session folder structure creation."""

    def test_create_session_folders(
        self, storage: SessionStorage, sample_session: Session
    ):
        """Should create all required subdirectories."""
        storage.create_session_folders(sample_session)

        session_path = storage.sessions_dir / sample_session.id
        assert (session_path / "audio").exists()
        assert (session_path / "transcripts").exists()
        assert (session_path / "process").exists()

    def test_exists_false_for_new(self, storage: SessionStorage):
        """Exists should return False for new session."""
        assert not storage.exists("nonexistent-session")

    def test_exists_true_after_save(
        self, storage: SessionStorage, sample_session: Session
    ):
        """Exists should return True after save."""
        storage.save(sample_session)
        assert storage.exists(sample_session.id)


class TestSessionStorageDelete:
    """Test session deletion."""

    def test_delete_removes_folder(
        self, storage: SessionStorage, sample_session: Session
    ):
        """Delete should remove the session folder."""
        storage.save(sample_session)
        storage.create_session_folders(sample_session)

        result = storage.delete(sample_session.id)

        assert result is True
        assert not storage.exists(sample_session.id)
        assert not (storage.sessions_dir / sample_session.id).exists()

    def test_delete_nonexistent_returns_false(self, storage: SessionStorage):
        """Delete should return False for nonexistent session."""
        result = storage.delete("nonexistent-session")
        assert result is False
