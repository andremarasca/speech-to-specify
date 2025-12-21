"""TTS (Text-to-Speech) data models.

Per data-model.md for 008-async-audio-response.

This module defines the data structures for:
- TTSRequest: Request for TTS synthesis
- TTSResult: Result from synthesis operation
- TTSArtifact: Persisted audio artifact for GC tracking
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional
import hashlib


@dataclass
class TTSRequest:
    """Request for TTS synthesis.
    
    Attributes:
        text: Text content to synthesize (will be sanitized)
        session_id: Session identifier for storage path
        sequence: LLM response sequence number (aligns with llm_responses/)
        oracle_name: Oracle name for filename
        oracle_id: Oracle identifier for idempotency key
    """
    text: str
    session_id: str
    sequence: int
    oracle_name: str
    oracle_id: str
    
    @property
    def idempotency_key(self) -> str:
        """Generate unique key for deduplication.
        
        Key is based on session_id, oracle_id, and text content hash.
        """
        content = f"{self.session_id}:{self.oracle_id}:{self.text}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    @property
    def filename(self) -> str:
        """Generate filename following llm_responses pattern.
        
        Format: {sequence:03d}_{oracle_name}.{format}
        The format extension is NOT included here - it's added by the service.
        """
        safe_name = self.oracle_name.lower().replace(" ", "_")
        return f"{self.sequence:03d}_{safe_name}"

    def __post_init__(self):
        """Validate request fields."""
        if not self.text or not self.text.strip():
            raise ValueError("Text cannot be empty")
        if self.sequence <= 0:
            raise ValueError("Sequence must be positive")
        if not self.session_id:
            raise ValueError("Session ID cannot be empty")


@dataclass
class TTSResult:
    """Result from TTS synthesis operation.
    
    Attributes:
        success: Whether synthesis completed successfully
        file_path: Path to generated audio file (if success)
        error_message: Error description (if failed)
        duration_ms: Time taken for synthesis in milliseconds
        cached: Whether result was returned from cache (idempotent)
    """
    success: bool
    file_path: Optional[Path] = None
    error_message: Optional[str] = None
    duration_ms: int = 0
    cached: bool = False
    
    @classmethod
    def ok(cls, file_path: Path, duration_ms: int, cached: bool = False) -> "TTSResult":
        """Create successful result.
        
        Args:
            file_path: Path to the generated audio file
            duration_ms: Time taken for synthesis
            cached: Whether result was from cache
            
        Returns:
            TTSResult with success=True
        """
        return cls(success=True, file_path=file_path, duration_ms=duration_ms, cached=cached)
    
    @classmethod
    def error(cls, message: str, duration_ms: int = 0) -> "TTSResult":
        """Create failed result.
        
        Args:
            message: Error description
            duration_ms: Time taken before failure
            
        Returns:
            TTSResult with success=False
        """
        return cls(success=False, error_message=message, duration_ms=duration_ms)
    
    @classmethod
    def timeout(cls, timeout_seconds: int) -> "TTSResult":
        """Create timeout result.
        
        Args:
            timeout_seconds: The timeout value that was exceeded
            
        Returns:
            TTSResult with success=False and timeout message
        """
        return cls(success=False, error_message=f"Synthesis timed out after {timeout_seconds}s")


@dataclass
class TTSArtifact:
    """Persisted TTS audio artifact.
    
    Used for garbage collection tracking.
    
    Attributes:
        file_path: Absolute path to audio file
        session_id: Associated session
        sequence: LLM response sequence
        oracle_id: Oracle that generated the source text
        created_at: When the artifact was created
        file_size_bytes: Size of the audio file
        idempotency_key: Hash for deduplication
    """
    file_path: Path
    session_id: str
    sequence: int
    oracle_id: str
    created_at: datetime
    file_size_bytes: int
    idempotency_key: str = ""
    
    @property
    def age_hours(self) -> float:
        """Calculate artifact age in hours."""
        delta = datetime.now() - self.created_at
        return delta.total_seconds() / 3600
    
    def is_expired(self, retention_hours: int) -> bool:
        """Check if artifact exceeds retention period.
        
        Args:
            retention_hours: Maximum age in hours before expiration
            
        Returns:
            True if artifact is older than retention_hours
        """
        return self.age_hours > retention_hours

    @classmethod
    def from_file(cls, file_path: Path, session_id: str, sequence: int, oracle_id: str) -> "TTSArtifact":
        """Create TTSArtifact from an existing file.
        
        Args:
            file_path: Path to the audio file
            session_id: Session identifier
            sequence: LLM response sequence
            oracle_id: Oracle identifier
            
        Returns:
            TTSArtifact with file metadata
        """
        stat = file_path.stat()
        # Use st_mtime (modification time) as it's portable across platforms
        # On Windows, st_ctime is creation time; on Unix it's metadata change time
        return cls(
            file_path=file_path,
            session_id=session_id,
            sequence=sequence,
            oracle_id=oracle_id,
            created_at=datetime.fromtimestamp(stat.st_mtime),
            file_size_bytes=stat.st_size,
        )
