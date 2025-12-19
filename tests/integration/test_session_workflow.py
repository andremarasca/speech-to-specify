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


class TestStartRecordFlow:
    """Test start-record flow for 004-resilient-voice-capture."""

    def test_start_session_initializes_reopen_count(self, manager: SessionManager):
        """Test that new sessions have reopen_count=0."""
        session = manager.create_session(chat_id=12345)
        assert session.reopen_count == 0, "New session should have reopen_count=0"
        assert session.state == SessionState.COLLECTING

    def test_add_audio_increments_sequence(self, manager: SessionManager):
        """Test that audio entries get sequential sequence numbers."""
        session = manager.create_session(chat_id=12345)
        
        for i in range(3):
            audio = create_audio_entry(i + 1)
            manager.add_audio(session.id, audio)
        
        updated = manager.get_session(session.id)
        assert updated.audio_count == 3
        assert [e.sequence for e in updated.audio_entries] == [1, 2, 3]

    def test_session_metadata_persisted(self, manager: SessionManager, sessions_dir: Path):
        """Test that session metadata is persisted to disk."""
        session = manager.create_session(chat_id=12345)
        
        # Add audio
        audio = create_audio_entry(1)
        manager.add_audio(session.id, audio)
        
        # Verify metadata.json exists
        metadata_path = sessions_dir / session.id / "metadata.json"
        assert metadata_path.exists()
        
        # Load and verify content
        import json
        with open(metadata_path, "r") as f:
            data = json.load(f)
        
        assert data["id"] == session.id
        assert data["state"] == "COLLECTING"
        assert data["reopen_count"] == 0
        assert len(data["audio_entries"]) == 1

    def test_start_record_complete_flow(self, manager: SessionManager, sessions_dir: Path):
        """Test complete start-record-finalize flow with integrity checks."""
        # 1. Start session
        session = manager.create_session(chat_id=12345)
        assert session.state == SessionState.COLLECTING
        assert session.reopen_count == 0
        
        # Verify folder structure
        session_path = sessions_dir / session.id
        assert (session_path / "audio").exists()
        assert (session_path / "transcripts").exists()
        assert (session_path / "process").exists()
        
        # 2. Add multiple audio entries
        for i in range(3):
            audio = create_audio_entry(i + 1)
            manager.add_audio(session.id, audio)
        
        # Verify audio entries persisted
        updated = manager.get_session(session.id)
        assert updated.audio_count == 3
        
        # 3. Finalize session
        finalized = manager.finalize_session(session.id)
        assert finalized.state == SessionState.TRANSCRIBING
        assert finalized.finalized_at is not None
        
        # Verify session persisted correctly
        reloaded = manager.get_session(session.id)
        assert reloaded.state == SessionState.TRANSCRIBING
        assert reloaded.audio_count == 3


class TestFinalizeAndQueueFlow:
    """Test finalize session and queue for transcription flow (US2)."""

    def test_finalize_and_queue_workflow(self, manager: SessionManager, sessions_dir: Path):
        """Test complete finalize → queue → status workflow."""
        from src.services.session.storage import SessionStorage
        from src.services.transcription.queue import DefaultTranscriptionQueueService
        
        # Setup
        storage = SessionStorage(sessions_dir)
        queue_service = DefaultTranscriptionQueueService(storage=storage)
        
        # 1. Create session with audio
        session = manager.create_session(chat_id=12345)
        for i in range(3):
            manager.add_audio(session.id, create_audio_entry(i + 1))
        
        # 2. Finalize
        finalized = manager.finalize_session(session.id)
        assert finalized.state == SessionState.TRANSCRIBING
        
        # 3. Queue for transcription
        result = queue_service.queue_session(session.id)
        assert result.queued_count == 3
        assert result.already_complete == 0
        
        # 4. Check queue status
        status = queue_service.get_queue_status()
        assert status.pending_count == 3
        
        # 5. Check session progress
        progress = queue_service.get_session_progress(session.id)
        assert progress.total_segments == 3
        assert progress.pending == 3
        assert progress.progress_percent == 0.0

    def test_queue_only_pending_segments(self, manager: SessionManager, sessions_dir: Path):
        """Test that only PENDING segments are queued."""
        from src.services.session.storage import SessionStorage
        from src.services.transcription.queue import DefaultTranscriptionQueueService
        
        storage = SessionStorage(sessions_dir)
        queue_service = DefaultTranscriptionQueueService(storage=storage)
        
        # Create session with mixed status entries
        session = manager.create_session(chat_id=12345)
        
        for i in range(4):
            audio = create_audio_entry(i + 1)
            manager.add_audio(session.id, audio)
        
        # Manually set some as completed
        loaded = manager.get_session(session.id)
        loaded.audio_entries[0].transcription_status = TranscriptionStatus.SUCCESS
        loaded.audio_entries[2].transcription_status = TranscriptionStatus.SUCCESS
        manager.storage.save(loaded)
        
        # Finalize
        manager.finalize_session(session.id)
        
        # Queue
        result = queue_service.queue_session(session.id)
        
        # Should only queue 2 pending segments
        assert result.queued_count == 2
        assert result.already_complete == 2

    def test_idempotent_queuing(self, manager: SessionManager, sessions_dir: Path):
        """Test that queuing same session twice doesn't duplicate."""
        from src.services.session.storage import SessionStorage
        from src.services.transcription.queue import DefaultTranscriptionQueueService
        
        storage = SessionStorage(sessions_dir)
        queue_service = DefaultTranscriptionQueueService(storage=storage)
        
        # Create and finalize session
        session = manager.create_session(chat_id=12345)
        manager.add_audio(session.id, create_audio_entry(1))
        manager.finalize_session(session.id)
        
        # Queue twice
        result1 = queue_service.queue_session(session.id)
        result2 = queue_service.queue_session(session.id)
        
        assert result1.queued_count == 1
        assert result2.queued_count == 0
        assert result2.already_queued == 1


class TestReopenSessionFlow:
    """Test session reopen flow (US3)."""

    def test_complete_reopen_flow(self, manager: SessionManager, sessions_dir: Path):
        """Test complete session reopen workflow."""
        # 1. Create session with audio
        session = manager.create_session(chat_id=12345)
        for i in range(2):
            manager.add_audio(session.id, create_audio_entry(i + 1))
        
        # 2. Finalize and process
        manager.finalize_session(session.id)
        manager.transition_state(session.id, SessionState.TRANSCRIBED)
        manager.transition_state(session.id, SessionState.PROCESSING)
        manager.transition_state(session.id, SessionState.PROCESSED)
        manager.transition_state(session.id, SessionState.READY)
        
        # 3. Reopen session
        reopened = manager.reopen_session(session.id)
        assert reopened.state == SessionState.COLLECTING
        assert reopened.reopen_count == 1
        assert reopened.audio_count == 2  # Original audio preserved
        
        # 4. Add new audio with correct epoch
        new_audio = create_audio_entry(3)
        new_audio.reopen_epoch = reopened.reopen_count
        manager.add_audio(session.id, new_audio)
        
        # 5. Finalize again
        finalized = manager.finalize_session(session.id)
        assert finalized.audio_count == 3
        
        # Verify epochs
        assert finalized.audio_entries[0].reopen_epoch == 0
        assert finalized.audio_entries[1].reopen_epoch == 0
        assert finalized.audio_entries[2].reopen_epoch == 1

    def test_only_queue_new_audio_after_reopen(
        self, manager: SessionManager, sessions_dir: Path
    ):
        """Test that only new audio (with new epoch) is queued after reopen."""
        from src.services.session.storage import SessionStorage
        from src.services.transcription.queue import DefaultTranscriptionQueueService
        
        storage = SessionStorage(sessions_dir)
        queue_service = DefaultTranscriptionQueueService(storage=storage)
        
        # 1. Create and process session
        session = manager.create_session(chat_id=12345)
        manager.add_audio(session.id, create_audio_entry(1))
        manager.finalize_session(session.id)
        
        # Mark first audio as transcribed
        loaded = manager.get_session(session.id)
        loaded.audio_entries[0].transcription_status = TranscriptionStatus.SUCCESS
        manager.storage.save(loaded)
        
        manager.transition_state(session.id, SessionState.TRANSCRIBED)
        manager.transition_state(session.id, SessionState.PROCESSING)
        manager.transition_state(session.id, SessionState.PROCESSED)
        manager.transition_state(session.id, SessionState.READY)
        
        # 2. Reopen and add new audio
        reopened = manager.reopen_session(session.id)
        new_audio = create_audio_entry(2)
        new_audio.reopen_epoch = reopened.reopen_count
        manager.add_audio(session.id, new_audio)
        
        # 3. Finalize and queue
        manager.finalize_session(session.id)
        result = queue_service.queue_session(session.id)
        
        # Only the new audio should be queued (the old one is SUCCESS)
        assert result.queued_count == 1
        assert result.already_complete == 1

    def test_multiple_reopens(self, manager: SessionManager, sessions_dir: Path):
        """Test that session can be reopened multiple times."""
        # Create and process
        session = manager.create_session(chat_id=12345)
        manager.add_audio(session.id, create_audio_entry(1))
        manager.finalize_session(session.id)
        manager.transition_state(session.id, SessionState.TRANSCRIBED)
        manager.transition_state(session.id, SessionState.PROCESSING)
        manager.transition_state(session.id, SessionState.PROCESSED)
        manager.transition_state(session.id, SessionState.READY)
        
        # First reopen
        manager.reopen_session(session.id)
        new_audio = create_audio_entry(2)
        new_audio.reopen_epoch = 1
        manager.add_audio(session.id, new_audio)
        manager.finalize_session(session.id)
        manager.transition_state(session.id, SessionState.TRANSCRIBED)
        manager.transition_state(session.id, SessionState.PROCESSING)
        manager.transition_state(session.id, SessionState.PROCESSED)
        manager.transition_state(session.id, SessionState.READY)
        
        # Second reopen
        reopened = manager.reopen_session(session.id)
        assert reopened.reopen_count == 2


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
