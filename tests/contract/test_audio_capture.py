"""Contract tests for AudioCaptureService.

Per contracts/audio-capture.md for 004-resilient-voice-capture.
Tests the behavioral contract of audio capture service.
"""

import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.lib.checksum import ChecksumService
from src.models.session import (
    AudioEntry,
    Session,
    SessionState,
    TranscriptionStatus,
)
from src.services.session.storage import SessionStorage
from src.services.audio.capture import (
    AudioCaptureService,
    DefaultAudioCaptureService,
    AudioPersistenceError,
    SessionNotCollectingError,
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
    """Create session storage."""
    return SessionStorage(sessions_dir)


@pytest.fixture
def collecting_session(storage: SessionStorage, sessions_dir: Path) -> Session:
    """Create a session in COLLECTING state with folder structure."""
    session = Session(
        id="2025-12-18_14-30-00",
        state=SessionState.COLLECTING,
        created_at=datetime.now(timezone.utc),
        chat_id=123,
    )
    # Create folder structure
    session_dir = sessions_dir / session.id
    session_dir.mkdir()
    (session_dir / "audio").mkdir()
    (session_dir / "transcripts").mkdir()
    storage.save(session)
    return session


class TestAddAudioChunk:
    """Contract tests for add_audio_chunk method (T014)."""
    
    def test_audio_persisted_before_return(
        self, storage: SessionStorage, collecting_session: Session, sessions_dir: Path
    ) -> None:
        """Audio file must exist on disk after add_audio_chunk returns."""
        capture = DefaultAudioCaptureService(storage, sessions_dir)
        audio_data = b"fake audio content for testing"
        timestamp = datetime.now(timezone.utc)
        
        segment = capture.add_audio_chunk(
            session_id=collecting_session.id,
            audio_data=audio_data,
            timestamp=timestamp,
        )
        
        # Audio file must exist
        audio_path = sessions_dir / collecting_session.id / "audio" / segment.local_filename
        assert audio_path.exists(), "Audio file not found after add_audio_chunk"
        assert audio_path.read_bytes() == audio_data
    
    def test_checksum_matches_content(
        self, storage: SessionStorage, collecting_session: Session, sessions_dir: Path
    ) -> None:
        """Stored checksum must match SHA-256 of file content (T015)."""
        capture = DefaultAudioCaptureService(storage, sessions_dir)
        audio_data = b"test audio data for checksum verification"
        timestamp = datetime.now(timezone.utc)
        
        segment = capture.add_audio_chunk(
            session_id=collecting_session.id,
            audio_data=audio_data,
            timestamp=timestamp,
        )
        
        # Verify checksum
        expected_checksum = ChecksumService.compute_bytes_checksum(audio_data)
        assert segment.checksum == expected_checksum
        
        # Also verify file on disk
        audio_path = sessions_dir / collecting_session.id / "audio" / segment.local_filename
        file_checksum = ChecksumService.compute_file_checksum(audio_path)
        assert segment.checksum == file_checksum
    
    def test_metadata_updated_atomically(
        self, storage: SessionStorage, collecting_session: Session, sessions_dir: Path
    ) -> None:
        """Session metadata must include new segment after add_audio_chunk."""
        capture = DefaultAudioCaptureService(storage, sessions_dir)
        audio_data = b"test audio"
        timestamp = datetime.now(timezone.utc)
        
        segment = capture.add_audio_chunk(
            session_id=collecting_session.id,
            audio_data=audio_data,
            timestamp=timestamp,
        )
        
        # Reload session and verify segment is there
        reloaded = storage.load(collecting_session.id)
        assert len(reloaded.audio_entries) == 1
        assert reloaded.audio_entries[0].sequence == segment.sequence
        assert reloaded.audio_entries[0].checksum == segment.checksum
    
    def test_sequence_increments_correctly(
        self, storage: SessionStorage, collecting_session: Session, sessions_dir: Path
    ) -> None:
        """Each new audio chunk should have incrementing sequence number."""
        capture = DefaultAudioCaptureService(storage, sessions_dir)
        
        segments = []
        for i in range(3):
            segment = capture.add_audio_chunk(
                session_id=collecting_session.id,
                audio_data=f"audio chunk {i}".encode(),
                timestamp=datetime.now(timezone.utc),
            )
            segments.append(segment)
        
        assert segments[0].sequence == 1
        assert segments[1].sequence == 2
        assert segments[2].sequence == 3
    
    def test_reopen_epoch_defaults_to_session_reopen_count(
        self, storage: SessionStorage, sessions_dir: Path
    ) -> None:
        """Audio segment reopen_epoch should match session's reopen_count."""
        # Create session with reopen_count = 2
        session = Session(
            id="2025-12-18_15-00-00",
            state=SessionState.COLLECTING,
            created_at=datetime.now(timezone.utc),
            chat_id=123,
            reopen_count=2,
        )
        session_dir = sessions_dir / session.id
        session_dir.mkdir()
        (session_dir / "audio").mkdir()
        storage.save(session)
        
        capture = DefaultAudioCaptureService(storage, sessions_dir)
        segment = capture.add_audio_chunk(
            session_id=session.id,
            audio_data=b"reopened session audio",
            timestamp=datetime.now(timezone.utc),
        )
        
        assert segment.reopen_epoch == 2
    
    def test_rejects_non_collecting_session(
        self, storage: SessionStorage, sessions_dir: Path
    ) -> None:
        """Should raise error for session not in COLLECTING state."""
        # Create TRANSCRIBING session
        session = Session(
            id="2025-12-18_16-00-00",
            state=SessionState.TRANSCRIBING,
            created_at=datetime.now(timezone.utc),
            chat_id=123,
        )
        session_dir = sessions_dir / session.id
        session_dir.mkdir()
        (session_dir / "audio").mkdir()
        storage.save(session)
        
        capture = DefaultAudioCaptureService(storage, sessions_dir)
        
        with pytest.raises(SessionNotCollectingError):
            capture.add_audio_chunk(
                session_id=session.id,
                audio_data=b"should fail",
                timestamp=datetime.now(timezone.utc),
            )
    
    def test_source_metadata_stored(
        self, storage: SessionStorage, collecting_session: Session, sessions_dir: Path
    ) -> None:
        """Source metadata should be stored with audio segment."""
        capture = DefaultAudioCaptureService(storage, sessions_dir)
        segment = capture.add_audio_chunk(
            session_id=collecting_session.id,
            audio_data=b"audio with metadata",
            timestamp=datetime.now(timezone.utc),
            source_metadata={"telegram_file_id": "file_abc123"},
        )
        
        assert segment.telegram_file_id == "file_abc123"


class TestVerifyIntegrity:
    """Contract tests for verify_integrity method (T015)."""
    
    def test_valid_audio_passes_verification(
        self, storage: SessionStorage, collecting_session: Session, sessions_dir: Path
    ) -> None:
        """Audio files with matching checksums should pass verification."""
        capture = DefaultAudioCaptureService(storage, sessions_dir)
        
        # Add some audio
        for i in range(3):
            capture.add_audio_chunk(
                session_id=collecting_session.id,
                audio_data=f"valid audio {i}".encode(),
                timestamp=datetime.now(timezone.utc),
            )
        
        report = capture.verify_integrity(collecting_session.id)
        
        assert report.segments_checked == 3
        assert report.segments_valid == 3
        assert len(report.segments_corrupted) == 0
    
    def test_corrupted_audio_detected(
        self, storage: SessionStorage, collecting_session: Session, sessions_dir: Path
    ) -> None:
        """Modified audio files should be detected as corrupted."""
        capture = DefaultAudioCaptureService(storage, sessions_dir)
        
        # Add audio
        segment = capture.add_audio_chunk(
            session_id=collecting_session.id,
            audio_data=b"original audio content",
            timestamp=datetime.now(timezone.utc),
        )
        
        # Corrupt the file
        audio_path = sessions_dir / collecting_session.id / "audio" / segment.local_filename
        audio_path.write_bytes(b"corrupted content!!!")
        
        report = capture.verify_integrity(collecting_session.id)
        
        assert report.segments_valid == 0
        assert len(report.segments_corrupted) == 1
        assert report.segments_corrupted[0].sequence == 1
    
    def test_missing_audio_detected(
        self, storage: SessionStorage, collecting_session: Session, sessions_dir: Path
    ) -> None:
        """Missing audio files should be reported."""
        capture = DefaultAudioCaptureService(storage, sessions_dir)
        
        # Add audio
        segment = capture.add_audio_chunk(
            session_id=collecting_session.id,
            audio_data=b"will be deleted",
            timestamp=datetime.now(timezone.utc),
        )
        
        # Delete the file
        audio_path = sessions_dir / collecting_session.id / "audio" / segment.local_filename
        audio_path.unlink()
        
        report = capture.verify_integrity(collecting_session.id)
        
        assert len(report.segments_corrupted) == 1
        assert "missing" in report.segments_corrupted[0].suggested_action.lower()


class TestSessionCreation:
    """Contract tests for session lifecycle integration (T016)."""
    
    def test_session_starts_in_collecting_state(
        self, storage: SessionStorage, sessions_dir: Path
    ) -> None:
        """New sessions should start in COLLECTING state."""
        from src.services.session.manager import SessionManager
        
        manager = SessionManager(storage)
        session = manager.create_session(chat_id=123)
        
        assert session.state == SessionState.COLLECTING
        assert session.reopen_count == 0
    
    def test_session_folder_structure_created(
        self, storage: SessionStorage, sessions_dir: Path
    ) -> None:
        """Session should have audio/ folder for capture."""
        from src.services.session.manager import SessionManager
        
        manager = SessionManager(storage)
        session = manager.create_session(chat_id=123)
        
        audio_path = sessions_dir / session.id / "audio"
        assert audio_path.exists()
        assert audio_path.is_dir()


class TestOrphanRecovery:
    """Contract tests for recover_orphans method (T070)."""
    
    def test_orphan_detection(
        self, storage: SessionStorage, collecting_session: Session, sessions_dir: Path
    ) -> None:
        """Audio files not in metadata should be detected as orphans."""
        # Create orphan audio file directly
        audio_dir = sessions_dir / collecting_session.id / "audio"
        orphan_file = audio_dir / "orphan_audio.ogg"
        orphan_file.write_bytes(b"orphan audio content")
        
        capture = DefaultAudioCaptureService(storage, sessions_dir)
        orphans = capture.recover_orphans(sessions_dir)
        
        assert len(orphans) == 1
        assert orphans[0].filepath == orphan_file
    
    def test_tracked_audio_not_orphan(
        self, storage: SessionStorage, collecting_session: Session, sessions_dir: Path
    ) -> None:
        """Audio files in metadata should not be reported as orphans."""
        capture = DefaultAudioCaptureService(storage, sessions_dir)
        
        # Add audio properly
        capture.add_audio_chunk(
            session_id=collecting_session.id,
            audio_data=b"tracked audio",
            timestamp=datetime.now(timezone.utc),
        )
        
        orphans = capture.recover_orphans(sessions_dir)
        
        assert len(orphans) == 0
