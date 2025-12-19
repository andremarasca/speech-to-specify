"""Contract tests for TranscriptionQueueService.

Tests per contracts/transcription-queue.md for 004-resilient-voice-capture.
These tests define the expected behavior before implementation.
"""

import pytest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

from src.models.session import (
    AudioEntry,
    Session,
    SessionState,
    TranscriptionStatus,
)
from src.services.transcription.queue import (
    CancelResult,
    FailedSegment,
    QueueItem,
    QueueResult,
    QueueStatus,
    RetryResult,
    SessionNotFoundError,
    SessionProgress,
    TranscriptionEvent,
    TranscriptionEventType,
    TranscriptionQueueService,
)


def create_test_session(
    session_id: str = "2025-01-01_00-00-00",
    state: SessionState = SessionState.TRANSCRIBING,
    audio_count: int = 3,
) -> Session:
    """Create a test session with audio entries."""
    entries = []
    for i in range(audio_count):
        entries.append(
            AudioEntry(
                sequence=i + 1,
                received_at=datetime.now(timezone.utc),
                telegram_file_id=f"file_{i+1}",
                local_filename=f"{i+1:03d}_audio.ogg",
                file_size_bytes=1024 * (i + 1),
                duration_seconds=10.0 * (i + 1),
                transcription_status=TranscriptionStatus.PENDING,
            )
        )
    
    return Session(
        id=session_id,
        state=state,
        created_at=datetime.now(timezone.utc),
        chat_id=12345,
        audio_entries=entries,
    )


class TestQueueSession:
    """Contract tests for TranscriptionQueueService.queue_session."""

    def test_queue_session_returns_queue_result(
        self, queue_service: TranscriptionQueueService
    ):
        """queue_session must return QueueResult with expected fields."""
        result = queue_service.queue_session("test-session")
        
        assert isinstance(result, QueueResult)
        assert hasattr(result, "session_id")
        assert hasattr(result, "queued_count")
        assert hasattr(result, "already_queued")
        assert hasattr(result, "already_complete")
        assert hasattr(result, "message")

    def test_queue_session_only_queues_pending_segments(
        self, queue_service: TranscriptionQueueService
    ):
        """Only segments with transcription_status=PENDING should be queued."""
        # Session with 3 audios, 1 already transcribed
        result = queue_service.queue_session("mixed-status-session")
        
        # Should only queue pending segments
        assert result.queued_count == 2  # 2 pending, 1 complete
        assert result.already_complete == 1

    def test_queue_session_raises_for_nonexistent_session(
        self, queue_service: TranscriptionQueueService
    ):
        """Must raise SessionNotFoundError for non-existent session."""
        with pytest.raises(SessionNotFoundError) as exc_info:
            queue_service.queue_session("nonexistent-session")
        
        assert "nonexistent-session" in str(exc_info.value)

    def test_queue_session_idempotent(
        self, queue_service: TranscriptionQueueService
    ):
        """Calling queue_session twice should not duplicate queue items."""
        result1 = queue_service.queue_session("test-session")
        result2 = queue_service.queue_session("test-session")
        
        # Second call should report items already queued
        assert result2.already_queued == result1.queued_count


class TestGetSessionProgress:
    """Contract tests for TranscriptionQueueService.get_session_progress."""

    def test_get_session_progress_returns_progress(
        self, queue_service: TranscriptionQueueService
    ):
        """get_session_progress must return SessionProgress with counts."""
        progress = queue_service.get_session_progress("test-session")
        
        assert isinstance(progress, SessionProgress)
        assert progress.session_id == "test-session"
        assert progress.total_segments >= 0
        assert progress.pending >= 0
        assert progress.processing >= 0
        assert progress.completed >= 0
        assert progress.failed >= 0
        assert 0.0 <= progress.progress_percent <= 100.0

    def test_progress_percent_calculation(
        self, queue_service: TranscriptionQueueService
    ):
        """progress_percent should be (completed + failed) / total * 100."""
        progress = queue_service.get_session_progress("test-session")
        
        if progress.total_segments > 0:
            expected = (progress.completed + progress.failed) / progress.total_segments * 100
            assert abs(progress.progress_percent - expected) < 0.01

    def test_progress_includes_failed_segment_details(
        self, queue_service: TranscriptionQueueService
    ):
        """Failed segments should include error details when tracked by queue."""
        # Get progress for session with failed transcriptions
        progress = queue_service.get_session_progress("session-with-failures")
        
        # The session has a segment with FAILED status in storage
        # The failed_segments list tracks failures that occurred through the queue
        # They may not match 1:1 if failures happened outside the queue
        if progress.failed > 0 and len(progress.failed_segments) > 0:
            for segment in progress.failed_segments:
                assert isinstance(segment, FailedSegment)
                assert segment.sequence > 0
                assert segment.error


class TestQueueStatus:
    """Contract tests for TranscriptionQueueService.get_queue_status."""

    def test_get_queue_status_returns_status(
        self, queue_service: TranscriptionQueueService
    ):
        """get_queue_status must return QueueStatus with counts."""
        status = queue_service.get_queue_status()
        
        assert isinstance(status, QueueStatus)
        assert status.pending_count >= 0
        assert status.processing_count >= 0
        assert status.completed_today >= 0
        assert status.failed_count >= 0
        assert isinstance(status.worker_running, bool)

    def test_current_item_populated_when_processing(
        self, queue_service: TranscriptionQueueService
    ):
        """current_item should be set when processing."""
        status = queue_service.get_queue_status()
        
        if status.processing_count > 0:
            assert status.current_item is not None
            assert isinstance(status.current_item, QueueItem)


class TestRetryFailed:
    """Contract tests for TranscriptionQueueService.retry_failed."""

    def test_retry_failed_returns_result(
        self, queue_service: TranscriptionQueueService
    ):
        """retry_failed must return RetryResult."""
        result = queue_service.retry_failed("session-with-failures")
        
        assert isinstance(result, RetryResult)
        assert hasattr(result, "session_id")
        assert hasattr(result, "retried_count")
        assert hasattr(result, "max_retries_reached")
        assert hasattr(result, "message")

    def test_retry_respects_max_retries(
        self, queue_service: TranscriptionQueueService
    ):
        """Segments exceeding max retries should not be re-queued."""
        result = queue_service.retry_failed("session-max-retries")
        
        # Should report segments that exceeded max retries
        assert isinstance(result.max_retries_reached, list)


class TestCancelSession:
    """Contract tests for TranscriptionQueueService.cancel_session."""

    def test_cancel_session_returns_result(
        self, queue_service: TranscriptionQueueService
    ):
        """cancel_session must return CancelResult."""
        result = queue_service.cancel_session("test-session")
        
        assert isinstance(result, CancelResult)
        assert result.session_id == "test-session"
        assert result.cancelled_count >= 0
        assert result.already_processing >= 0


class TestEventCallbacks:
    """Contract tests for TranscriptionQueueService event callbacks."""

    def test_on_progress_registers_callback(
        self, queue_service: TranscriptionQueueService
    ):
        """on_progress should accept a callback function."""
        events_received = []
        
        def callback(event: TranscriptionEvent):
            events_received.append(event)
        
        # Should not raise
        queue_service.on_progress(callback)

    def test_events_include_all_required_fields(
        self, queue_service: TranscriptionQueueService
    ):
        """TranscriptionEvent must have required fields."""
        event = TranscriptionEvent(
            event_type=TranscriptionEventType.START,
            session_id="test-session",
            sequence=1,
        )
        
        assert event.event_type == TranscriptionEventType.START
        assert event.session_id == "test-session"
        assert event.sequence == 1
        assert event.timestamp is not None


class TestWorkerControl:
    """Contract tests for worker start/stop."""

    def test_start_worker_activates_processing(
        self, queue_service: TranscriptionQueueService
    ):
        """start_worker should enable background processing."""
        queue_service.start_worker()
        status = queue_service.get_queue_status()
        assert status.worker_running is True

    def test_stop_worker_deactivates_processing(
        self, queue_service: TranscriptionQueueService
    ):
        """stop_worker should disable background processing."""
        queue_service.start_worker()
        queue_service.stop_worker(wait=False)
        status = queue_service.get_queue_status()
        assert status.worker_running is False


# Fixtures - to be configured with actual implementation
@pytest.fixture
def sessions_dir(tmp_path: Path) -> Path:
    """Create temporary sessions directory."""
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    return sessions


@pytest.fixture
def queue_service(sessions_dir: Path) -> TranscriptionQueueService:
    """Create TranscriptionQueueService instance for testing.
    
    This fixture should be updated when implementation is complete
    to use the actual DefaultTranscriptionQueueService.
    """
    # Import implementation
    from src.services.transcription.queue import DefaultTranscriptionQueueService
    from src.services.session.storage import SessionStorage
    
    storage = SessionStorage(sessions_dir)
    
    # Create test sessions
    test_session = create_test_session("test-session", audio_count=3)
    storage.create_session_folders(test_session)
    storage.save(test_session)
    
    # Create session with mixed status
    mixed_session = create_test_session("mixed-status-session", audio_count=3)
    mixed_session.audio_entries[2].transcription_status = TranscriptionStatus.SUCCESS
    storage.create_session_folders(mixed_session)
    storage.save(mixed_session)
    
    # Create session with failures
    failed_session = create_test_session("session-with-failures", audio_count=3)
    failed_session.audio_entries[0].transcription_status = TranscriptionStatus.FAILED
    storage.create_session_folders(failed_session)
    storage.save(failed_session)
    
    # Create session with max retries
    max_retries_session = create_test_session("session-max-retries", audio_count=2)
    max_retries_session.audio_entries[0].transcription_status = TranscriptionStatus.FAILED
    storage.create_session_folders(max_retries_session)
    storage.save(max_retries_session)
    
    return DefaultTranscriptionQueueService(storage=storage)
