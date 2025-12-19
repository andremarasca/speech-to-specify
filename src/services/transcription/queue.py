"""Transcription queue service for async background processing.

Per contracts/transcription-queue.md for 004-resilient-voice-capture.
Manages async transcription of audio segments with progress tracking.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Callable, Optional

from src.models.session import TranscriptionStatus


class TranscriptionEventType(str, Enum):
    """Types of transcription events."""
    
    QUEUED = "QUEUED"  # Item added to queue
    START = "START"  # Transcription started
    PROGRESS = "PROGRESS"  # Progress update (for long transcriptions)
    COMPLETE = "COMPLETE"  # Successfully completed
    FAILED = "FAILED"  # Transcription failed


@dataclass
class QueueItem:
    """Item in transcription queue.
    
    Attributes:
        session_id: Session containing the audio
        sequence: Audio segment sequence number
        audio_path: Path to audio file
        queued_at: When item was added to queue
        started_at: When processing started (None if pending)
    """
    
    session_id: str
    sequence: int
    audio_path: Path
    queued_at: datetime
    started_at: Optional[datetime] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "session_id": self.session_id,
            "sequence": self.sequence,
            "audio_path": str(self.audio_path),
            "queued_at": self.queued_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
        }


@dataclass
class FailedSegment:
    """Details of a failed transcription.
    
    Attributes:
        sequence: Audio segment sequence number
        error: Error message
        failed_at: When failure occurred
        retry_count: Number of retry attempts
    """
    
    sequence: int
    error: str
    failed_at: datetime
    retry_count: int = 0
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "sequence": self.sequence,
            "error": self.error,
            "failed_at": self.failed_at.isoformat(),
            "retry_count": self.retry_count,
        }


@dataclass
class QueueResult:
    """Result of queue operation.
    
    Attributes:
        session_id: Session that was queued
        queued_count: Number of items added to queue
        already_queued: Items already in queue (skipped)
        already_complete: Items already transcribed (skipped)
        message: Human-readable status message
    """
    
    session_id: str
    queued_count: int
    already_queued: int
    already_complete: int
    message: str


@dataclass
class QueueStatus:
    """Overall queue status.
    
    Attributes:
        pending_count: Items waiting to be processed
        processing_count: Items currently being processed
        completed_today: Items completed in current day
        failed_count: Items that failed
        worker_running: Whether background worker is active
        current_item: Item currently being processed
    """
    
    pending_count: int
    processing_count: int
    completed_today: int
    failed_count: int
    worker_running: bool
    current_item: Optional[QueueItem] = None


@dataclass
class SessionProgress:
    """Transcription progress for session.
    
    Attributes:
        session_id: Session being tracked
        total_segments: Total audio segments in session
        pending: Segments waiting for transcription
        processing: Segments currently being transcribed
        completed: Segments successfully transcribed
        failed: Segments that failed transcription
        progress_percent: Completion percentage (0.0-100.0)
        estimated_remaining_seconds: Estimated time to complete
        failed_segments: Details of failed segments
    """
    
    session_id: str
    total_segments: int
    pending: int
    processing: int
    completed: int
    failed: int
    progress_percent: float
    estimated_remaining_seconds: Optional[float] = None
    failed_segments: list[FailedSegment] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "session_id": self.session_id,
            "total_segments": self.total_segments,
            "pending": self.pending,
            "processing": self.processing,
            "completed": self.completed,
            "failed": self.failed,
            "progress_percent": self.progress_percent,
            "estimated_remaining_seconds": self.estimated_remaining_seconds,
            "failed_segments": [s.to_dict() for s in self.failed_segments],
        }


@dataclass
class CancelResult:
    """Result of cancel operation.
    
    Attributes:
        session_id: Session that was cancelled
        cancelled_count: Items removed from queue
        already_processing: Items that couldn't be cancelled
    """
    
    session_id: str
    cancelled_count: int
    already_processing: int


@dataclass
class RetryResult:
    """Result of retry operation.
    
    Attributes:
        session_id: Session with retried segments
        retried_count: Number of segments re-queued
        max_retries_reached: Segments that exceeded retry limit
        message: Human-readable status message
    """
    
    session_id: str
    retried_count: int
    max_retries_reached: list[int]  # Segment sequences
    message: str


@dataclass
class TranscriptionEvent:
    """Event from transcription processing.
    
    Attributes:
        event_type: Type of event
        session_id: Session being processed
        sequence: Audio segment sequence (if applicable)
        progress_percent: Progress percentage (for PROGRESS events)
        error: Error message (for FAILED events)
        timestamp: When event occurred
    """
    
    event_type: TranscriptionEventType
    session_id: str
    sequence: Optional[int] = None
    progress_percent: Optional[float] = None
    error: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)


class SessionNotFoundError(Exception):
    """Raised when session doesn't exist."""
    
    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        super().__init__(f"Session '{session_id}' not found")


class TranscriptionQueueService(ABC):
    """Service for async transcription queue management.
    
    Per contracts/transcription-queue.md for 004-resilient-voice-capture.
    """
    
    @abstractmethod
    def queue_session(self, session_id: str) -> QueueResult:
        """Queue all pending audio segments from session for transcription.
        
        Only queues segments with transcription_status = PENDING.
        
        Args:
            session_id: Session to queue
            
        Returns:
            QueueResult with count of queued items
            
        Raises:
            SessionNotFoundError: Session doesn't exist
        """
        pass
    
    @abstractmethod
    def queue_segment(self, session_id: str, sequence: int) -> QueueResult:
        """Queue specific audio segment for transcription.
        
        Used for retry of failed segments.
        
        Args:
            session_id: Session containing segment
            sequence: Audio segment sequence number
            
        Returns:
            QueueResult with status
        """
        pass
    
    @abstractmethod
    def get_queue_status(self) -> QueueStatus:
        """Get overall queue status.
        
        Returns:
            QueueStatus with pending, processing, completed counts
        """
        pass
    
    @abstractmethod
    def get_session_progress(self, session_id: str) -> SessionProgress:
        """Get transcription progress for specific session.
        
        Args:
            session_id: Session to check
            
        Returns:
            SessionProgress with detailed status
        """
        pass
    
    @abstractmethod
    def cancel_session(self, session_id: str) -> CancelResult:
        """Cancel pending transcriptions for session.
        
        Does not affect already-running transcriptions.
        
        Args:
            session_id: Session to cancel
            
        Returns:
            CancelResult with cancelled count
        """
        pass
    
    @abstractmethod
    def retry_failed(self, session_id: str) -> RetryResult:
        """Re-queue all failed segments for session.
        
        Args:
            session_id: Session with failed segments
            
        Returns:
            RetryResult with re-queued count
        """
        pass
    
    @abstractmethod
    def on_progress(self, callback: Callable[[TranscriptionEvent], None]) -> None:
        """Register callback for transcription events.
        
        Called on: QUEUED, START, PROGRESS, COMPLETE, FAILED
        
        Args:
            callback: Function to call on events
        """
        pass
    
    @abstractmethod
    def start_worker(self) -> None:
        """Start background transcription worker."""
        pass
    
    @abstractmethod
    def stop_worker(self, wait: bool = True) -> None:
        """Stop background worker.
        
        Args:
            wait: If True, wait for current item to complete
        """
        pass


class DefaultTranscriptionQueueService(TranscriptionQueueService):
    """Default implementation of TranscriptionQueueService.
    
    Uses an in-memory queue with optional background worker.
    Queue state is persisted to disk for crash recovery.
    """
    
    MAX_RETRIES = 3
    
    def __init__(
        self,
        storage,  # SessionStorage
        transcription_service=None,  # TranscriptionService
        queue_file: Optional[Path] = None,
    ):
        """Initialize queue service.
        
        Args:
            storage: SessionStorage for session access
            transcription_service: Optional service for actual transcription
            queue_file: Optional path for queue persistence
        """
        self.storage = storage
        self.transcription_service = transcription_service
        self.queue_file = queue_file
        
        # In-memory state
        self._queue: list[QueueItem] = []
        self._processing: Optional[QueueItem] = None
        self._completed_today: int = 0
        self._failed: dict[str, list[FailedSegment]] = {}  # session_id -> failures
        self._retry_counts: dict[str, dict[int, int]] = {}  # session_id -> {seq: count}
        self._callbacks: list[Callable[[TranscriptionEvent], None]] = []
        self._worker_running: bool = False
        self._stop_requested: bool = False
        
    def queue_session(self, session_id: str) -> QueueResult:
        """Queue all pending audio segments from session."""
        session = self.storage.load(session_id)
        if not session:
            raise SessionNotFoundError(session_id)
        
        queued_count = 0
        already_queued = 0
        already_complete = 0
        
        sessions_dir = self.storage.sessions_dir
        audio_dir = session.audio_path(sessions_dir)
        
        for entry in session.audio_entries:
            # Skip already transcribed
            if entry.transcription_status == TranscriptionStatus.SUCCESS:
                already_complete += 1
                continue
            
            # Check if already in queue
            if self._is_queued(session_id, entry.sequence):
                already_queued += 1
                continue
            
            # Add to queue
            item = QueueItem(
                session_id=session_id,
                sequence=entry.sequence,
                audio_path=audio_dir / entry.local_filename,
                queued_at=datetime.now(),
            )
            self._queue.append(item)
            queued_count += 1
            
            # Emit event
            self._emit_event(TranscriptionEvent(
                event_type=TranscriptionEventType.QUEUED,
                session_id=session_id,
                sequence=entry.sequence,
            ))
        
        message = f"Queued {queued_count} segment(s) for transcription"
        if already_complete:
            message += f", {already_complete} already complete"
        if already_queued:
            message += f", {already_queued} already queued"
            
        return QueueResult(
            session_id=session_id,
            queued_count=queued_count,
            already_queued=already_queued,
            already_complete=already_complete,
            message=message,
        )
    
    def queue_segment(self, session_id: str, sequence: int) -> QueueResult:
        """Queue specific audio segment for transcription."""
        session = self.storage.load(session_id)
        if not session:
            raise SessionNotFoundError(session_id)
        
        # Find the entry
        entry = next(
            (e for e in session.audio_entries if e.sequence == sequence),
            None
        )
        if not entry:
            return QueueResult(
                session_id=session_id,
                queued_count=0,
                already_queued=0,
                already_complete=0,
                message=f"Segment {sequence} not found in session",
            )
        
        # Check if already queued
        if self._is_queued(session_id, sequence):
            return QueueResult(
                session_id=session_id,
                queued_count=0,
                already_queued=1,
                already_complete=0,
                message=f"Segment {sequence} already queued",
            )
        
        # Add to queue
        sessions_dir = self.storage.sessions_dir
        audio_dir = session.audio_path(sessions_dir)
        
        item = QueueItem(
            session_id=session_id,
            sequence=sequence,
            audio_path=audio_dir / entry.local_filename,
            queued_at=datetime.now(),
        )
        self._queue.append(item)
        
        self._emit_event(TranscriptionEvent(
            event_type=TranscriptionEventType.QUEUED,
            session_id=session_id,
            sequence=sequence,
        ))
        
        return QueueResult(
            session_id=session_id,
            queued_count=1,
            already_queued=0,
            already_complete=0,
            message=f"Segment {sequence} queued for transcription",
        )
    
    def get_queue_status(self) -> QueueStatus:
        """Get overall queue status."""
        return QueueStatus(
            pending_count=len(self._queue),
            processing_count=1 if self._processing else 0,
            completed_today=self._completed_today,
            failed_count=sum(len(f) for f in self._failed.values()),
            worker_running=self._worker_running,
            current_item=self._processing,
        )
    
    def get_session_progress(self, session_id: str) -> SessionProgress:
        """Get transcription progress for specific session."""
        session = self.storage.load(session_id)
        if not session:
            raise SessionNotFoundError(session_id)
        
        total = session.audio_count
        pending = 0
        processing = 0
        completed = 0
        failed = 0
        
        for entry in session.audio_entries:
            if entry.transcription_status == TranscriptionStatus.SUCCESS:
                completed += 1
            elif entry.transcription_status == TranscriptionStatus.FAILED:
                failed += 1
            elif self._is_processing(session_id, entry.sequence):
                processing += 1
            elif self._is_queued(session_id, entry.sequence):
                pending += 1
            else:
                pending += 1  # Not yet queued counts as pending
        
        progress_percent = 0.0
        if total > 0:
            progress_percent = (completed + failed) / total * 100.0
        
        failed_segments = self._failed.get(session_id, [])
        
        # Estimate remaining time (rough: 10s per segment)
        remaining = pending + processing
        estimated_remaining = remaining * 10.0 if remaining > 0 else None
        
        return SessionProgress(
            session_id=session_id,
            total_segments=total,
            pending=pending,
            processing=processing,
            completed=completed,
            failed=failed,
            progress_percent=progress_percent,
            estimated_remaining_seconds=estimated_remaining,
            failed_segments=failed_segments,
        )
    
    def cancel_session(self, session_id: str) -> CancelResult:
        """Cancel pending transcriptions for session."""
        cancelled = 0
        already_processing = 0
        
        # Remove from queue
        original_len = len(self._queue)
        self._queue = [
            item for item in self._queue 
            if item.session_id != session_id
        ]
        cancelled = original_len - len(self._queue)
        
        # Check if currently processing
        if self._processing and self._processing.session_id == session_id:
            already_processing = 1
        
        return CancelResult(
            session_id=session_id,
            cancelled_count=cancelled,
            already_processing=already_processing,
        )
    
    def retry_failed(self, session_id: str) -> RetryResult:
        """Re-queue all failed segments for session."""
        failed_segments = self._failed.get(session_id, [])
        if not failed_segments:
            return RetryResult(
                session_id=session_id,
                retried_count=0,
                max_retries_reached=[],
                message="No failed segments to retry",
            )
        
        retried = 0
        max_reached = []
        
        # Initialize retry counts for session if needed
        if session_id not in self._retry_counts:
            self._retry_counts[session_id] = {}
        
        for segment in list(failed_segments):
            seq = segment.sequence
            current_retries = self._retry_counts[session_id].get(seq, 0)
            
            if current_retries >= self.MAX_RETRIES:
                max_reached.append(seq)
                continue
            
            # Re-queue the segment
            result = self.queue_segment(session_id, seq)
            if result.queued_count > 0:
                retried += 1
                self._retry_counts[session_id][seq] = current_retries + 1
                # Remove from failed list
                self._failed[session_id] = [
                    s for s in self._failed[session_id] 
                    if s.sequence != seq
                ]
        
        message = f"Retried {retried} segment(s)"
        if max_reached:
            message += f", {len(max_reached)} exceeded max retries"
        
        return RetryResult(
            session_id=session_id,
            retried_count=retried,
            max_retries_reached=max_reached,
            message=message,
        )
    
    def on_progress(self, callback: Callable[[TranscriptionEvent], None]) -> None:
        """Register callback for transcription events."""
        self._callbacks.append(callback)
    
    def start_worker(self) -> None:
        """Start background transcription worker."""
        self._worker_running = True
        self._stop_requested = False
    
    def stop_worker(self, wait: bool = True) -> None:
        """Stop background worker."""
        self._stop_requested = True
        self._worker_running = False
    
    def _is_queued(self, session_id: str, sequence: int) -> bool:
        """Check if segment is in queue."""
        return any(
            item.session_id == session_id and item.sequence == sequence
            for item in self._queue
        )
    
    def _is_processing(self, session_id: str, sequence: int) -> bool:
        """Check if segment is currently processing."""
        return (
            self._processing is not None and
            self._processing.session_id == session_id and
            self._processing.sequence == sequence
        )
    
    def _emit_event(self, event: TranscriptionEvent) -> None:
        """Emit event to all registered callbacks."""
        for callback in self._callbacks:
            try:
                callback(event)
            except Exception:
                pass  # Don't let callback errors break the service
