# Contract: Audio Capture Service

**Feature**: 004-resilient-voice-capture  
**Service**: `AudioCaptureService`  
**Location**: `src/services/audio/capture.py`

## Purpose

Handles audio data ingestion with incremental persistence and integrity verification. Ensures no audio is lost even during crash scenarios.

## Interface

```python
from abc import ABC, abstractmethod
from pathlib import Path
from datetime import datetime
from typing import Optional

class AudioCaptureService(ABC):
    """Service for capturing and persisting audio data."""
    
    @abstractmethod
    def start_capture(self, session_id: str) -> CaptureContext:
        """
        Start audio capture for a session.
        
        Args:
            session_id: Target session identifier
            
        Returns:
            CaptureContext with capture state and methods
            
        Raises:
            SessionNotFoundError: Session doesn't exist
            SessionNotCollectingError: Session not in COLLECTING state
        """
        pass
    
    @abstractmethod
    def add_audio_chunk(
        self,
        session_id: str,
        audio_data: bytes,
        timestamp: datetime,
        source_metadata: Optional[dict] = None
    ) -> AudioSegment:
        """
        Add audio chunk to session with immediate persistence.
        
        Args:
            session_id: Target session
            audio_data: Raw audio bytes
            timestamp: When audio was captured
            source_metadata: Optional source info (e.g., telegram_file_id)
            
        Returns:
            Created AudioSegment with checksum
            
        Raises:
            SessionNotFoundError: Session doesn't exist
            SessionNotCollectingError: Session not accepting audio
            AudioPersistenceError: Failed to write audio to disk
            
        Guarantees:
            - Audio is fsynced to disk before return
            - Checksum computed and stored
            - Session metadata updated atomically
        """
        pass
    
    @abstractmethod
    def verify_integrity(self, session_id: str) -> IntegrityReport:
        """
        Verify all audio files match their stored checksums.
        
        Args:
            session_id: Session to verify
            
        Returns:
            IntegrityReport with status of each segment
        """
        pass
    
    @abstractmethod
    def recover_orphans(self, sessions_dir: Path) -> list[OrphanRecovery]:
        """
        Find audio files not referenced in any session metadata.
        
        Used during crash recovery to prevent data loss.
        
        Args:
            sessions_dir: Root sessions directory
            
        Returns:
            List of orphan files with suggested recovery actions
        """
        pass
```

## Data Types

```python
@dataclass
class CaptureContext:
    """Active capture context."""
    session_id: str
    started_at: datetime
    segment_count: int
    
    def is_active(self) -> bool: ...
    def close(self) -> None: ...

@dataclass  
class IntegrityReport:
    """Result of integrity verification."""
    session_id: str
    verified_at: datetime
    segments_checked: int
    segments_valid: int
    segments_corrupted: list[CorruptedSegment]
    
@dataclass
class CorruptedSegment:
    """Details of a corrupted audio segment."""
    sequence: int
    filename: str
    expected_checksum: str
    actual_checksum: str
    suggested_action: str

@dataclass
class OrphanRecovery:
    """Orphan audio file recovery suggestion."""
    filepath: Path
    probable_session: Optional[str]
    file_timestamp: datetime
    suggested_action: str  # "attach_to_session" | "quarantine" | "delete"
```

## Behavioral Contract

### Persistence Guarantees

1. **Immediate Write**: Audio data is written to disk before `add_audio_chunk` returns
2. **Fsync**: `os.fsync()` called on audio file after write
3. **Atomic Metadata**: Session metadata updated via temp file + replace pattern
4. **Checksum First**: Checksum computed before metadata update

### Failure Modes

| Failure | Behavior |
|---------|----------|
| Disk full | Raise `AudioPersistenceError` with clear message |
| Permission denied | Raise `AudioPersistenceError` with path info |
| Session locked | Raise `SessionNotCollectingError` |
| Checksum mismatch on verify | Return in `IntegrityReport.segments_corrupted` |

### Test Cases (Contract Tests)

```python
def test_audio_persisted_before_return():
    """Audio file must exist on disk after add_audio_chunk returns."""
    
def test_checksum_matches_content():
    """Stored checksum must match SHA-256 of file content."""
    
def test_metadata_updated_atomically():
    """Session metadata must include new segment after add_audio_chunk."""
    
def test_orphan_detection():
    """Audio files without metadata entries must be detected."""
    
def test_crash_recovery_preserves_audio():
    """Simulated crash must not lose written audio chunks."""
```

## Dependencies

- `SessionStorage`: For atomic metadata persistence
- `ChecksumService`: For SHA-256 computation
- `logging`: For audit trail

## Configuration

```python
@dataclass
class AudioCaptureConfig:
    chunk_flush_interval_seconds: float = 5.0
    max_segment_size_mb: float = 50.0
    checksum_algorithm: str = "sha256"
```
