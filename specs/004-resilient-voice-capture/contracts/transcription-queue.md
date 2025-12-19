# Contract: Transcription Queue Service

**Feature**: 004-resilient-voice-capture  
**Service**: `TranscriptionQueueService`  
**Location**: `src/services/transcription/queue.py`

## Purpose

Manages async transcription of audio segments with progress tracking and failure handling. Ensures transcription runs in background without blocking user interaction.

## Interface

```python
from abc import ABC, abstractmethod
from typing import Callable, Optional
from enum import Enum

class TranscriptionQueueService(ABC):
    """Service for async transcription queue management."""
    
    @abstractmethod
    def queue_session(self, session_id: str) -> QueueResult:
        """
        Queue all pending audio segments from session for transcription.
        
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
    def queue_segment(
        self, 
        session_id: str, 
        sequence: int
    ) -> QueueResult:
        """
        Queue specific audio segment for transcription.
        
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
        """
        Get overall queue status.
        
        Returns:
            QueueStatus with pending, processing, completed counts
        """
        pass
    
    @abstractmethod
    def get_session_progress(self, session_id: str) -> SessionProgress:
        """
        Get transcription progress for specific session.
        
        Args:
            session_id: Session to check
            
        Returns:
            SessionProgress with detailed status
        """
        pass
    
    @abstractmethod
    def cancel_session(self, session_id: str) -> CancelResult:
        """
        Cancel pending transcriptions for session.
        
        Does not affect already-running transcriptions.
        
        Args:
            session_id: Session to cancel
            
        Returns:
            CancelResult with cancelled count
        """
        pass
    
    @abstractmethod
    def retry_failed(self, session_id: str) -> RetryResult:
        """
        Re-queue all failed segments for session.
        
        Args:
            session_id: Session with failed segments
            
        Returns:
            RetryResult with re-queued count
        """
        pass
    
    @abstractmethod
    def on_progress(
        self, 
        callback: Callable[[TranscriptionEvent], None]
    ) -> None:
        """
        Register callback for transcription events.
        
        Called on: START, PROGRESS, COMPLETE, FAILED
        
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
        """
        Stop background worker.
        
        Args:
            wait: If True, wait for current item to complete
        """
        pass
```

## Data Types

```python
@dataclass
class QueueResult:
    """Result of queue operation."""
    session_id: str
    queued_count: int
    already_queued: int
    already_complete: int
    message: str

@dataclass
class QueueStatus:
    """Overall queue status."""
    pending_count: int
    processing_count: int
    completed_today: int
    failed_count: int
    worker_running: bool
    current_item: Optional[QueueItem]

@dataclass
class QueueItem:
    """Item in transcription queue."""
    session_id: str
    sequence: int
    audio_path: Path
    queued_at: datetime
    started_at: Optional[datetime]
    
@dataclass
class SessionProgress:
    """Transcription progress for session."""
    session_id: str
    total_segments: int
    pending: int
    processing: int
    completed: int
    failed: int
    progress_percent: float
    estimated_remaining_seconds: Optional[float]
    failed_segments: list[FailedSegment]
    
@dataclass
class FailedSegment:
    """Details of a failed transcription."""
    sequence: int
    error: str
    failed_at: datetime
    retry_count: int

@dataclass
class CancelResult:
    """Result of cancel operation."""
    session_id: str
    cancelled_count: int
    already_processing: int

@dataclass
class RetryResult:
    """Result of retry operation."""
    session_id: str
    requeued_count: int
    message: str

class TranscriptionEventType(str, Enum):
    QUEUED = "QUEUED"
    STARTED = "STARTED"
    PROGRESS = "PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

@dataclass
class TranscriptionEvent:
    """Event from transcription worker."""
    event_type: TranscriptionEventType
    session_id: str
    sequence: int
    timestamp: datetime
    progress_percent: Optional[float] = None
    result: Optional[str] = None  # Transcript text for COMPLETED
    error: Optional[str] = None   # Error message for FAILED
```

## Worker Behavior

### Processing Loop

```
while running:
    1. Dequeue next item (FIFO)
    2. Emit STARTED event
    3. Load audio from disk
    4. Run Whisper transcription
    5. If success:
       - Write transcript file
       - Update session metadata (atomic)
       - Emit COMPLETED event
    6. If failure:
       - Log error
       - Update segment status = FAILED
       - Emit FAILED event
    7. Check for next item
```

### Failure Handling

| Failure | Behavior |
|---------|----------|
| Audio file missing | Mark FAILED, log error, continue |
| Whisper OOM | Mark FAILED, reduce batch size, retry |
| Whisper timeout | Mark FAILED, queue for retry |
| Disk full on write | Mark FAILED, alert user, pause worker |

### Retry Policy

- Max retries per segment: 3
- Retry delay: exponential backoff (30s, 60s, 120s)
- After max retries: mark as permanently FAILED

## Test Cases (Contract Tests)

```python
def test_queue_session_only_pending():
    """Only PENDING segments are queued."""
    
def test_queue_idempotent():
    """Re-queueing same segment has no effect."""
    
def test_progress_updates_on_completion():
    """Session progress reflects completed transcriptions."""
    
def test_failure_preserves_audio():
    """Failed transcription does not delete audio."""
    
def test_retry_resets_status():
    """Retry changes FAILED back to PENDING."""
    
def test_cancel_does_not_affect_running():
    """Cancel only removes pending items."""
    
def test_worker_emits_events():
    """Worker emits appropriate events for each stage."""
```

## Integration Points

- `WhisperTranscriptionService`: Actual transcription
- `SessionStorage`: Atomic metadata updates
- `EmbeddingIndexer`: Triggered after session fully transcribed

## Configuration

```python
@dataclass
class TranscriptionQueueConfig:
    max_concurrent: int = 1  # One at a time for GPU memory
    max_retries: int = 3
    retry_delay_seconds: list[int] = field(default_factory=lambda: [30, 60, 120])
    timeout_seconds: int = 300  # 5 min max per segment
```
