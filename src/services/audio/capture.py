"""Audio capture service for voice recording with integrity guarantees.

Per contracts/audio-capture.md for 004-resilient-voice-capture.
Handles audio data ingestion with incremental persistence and integrity verification.
"""

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from src.lib.checksum import ChecksumService
from src.models.session import AudioEntry, Session, SessionState, TranscriptionStatus
from src.services.session.storage import SessionStorage


class AudioPersistenceError(Exception):
    """Raised when audio cannot be persisted to disk."""
    
    def __init__(self, message: str, path: Optional[Path] = None) -> None:
        self.path = path
        super().__init__(message)


class SessionNotCollectingError(Exception):
    """Raised when trying to add audio to a non-COLLECTING session."""
    
    def __init__(self, session_id: str, current_state: SessionState) -> None:
        self.session_id = session_id
        self.current_state = current_state
        super().__init__(
            f"Session '{session_id}' is in state {current_state.value}, "
            f"cannot accept audio"
        )


class SessionNotFoundError(Exception):
    """Raised when session doesn't exist."""
    
    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        super().__init__(f"Session '{session_id}' not found")


@dataclass
class CaptureContext:
    """Active capture context.
    
    Attributes:
        session_id: Session being captured
        started_at: When capture started
        segment_count: Number of segments captured
        _active: Whether capture is active
    """
    
    session_id: str
    started_at: datetime
    segment_count: int = 0
    _active: bool = True
    
    def is_active(self) -> bool:
        """Check if capture is still active."""
        return self._active
    
    def close(self) -> None:
        """Close capture context."""
        self._active = False


@dataclass
class CorruptedSegment:
    """Details of a corrupted audio segment.
    
    Attributes:
        sequence: Segment sequence number
        filename: Audio filename
        expected_checksum: Checksum stored in metadata
        actual_checksum: Checksum computed from file
        suggested_action: Recommended recovery action
    """
    
    sequence: int
    filename: str
    expected_checksum: str
    actual_checksum: str
    suggested_action: str


@dataclass
class IntegrityReport:
    """Result of integrity verification.
    
    Attributes:
        session_id: Session that was verified
        verified_at: When verification was performed
        segments_checked: Total segments checked
        segments_valid: Segments with valid checksums
        segments_corrupted: List of corrupted segments
    """
    
    session_id: str
    verified_at: datetime
    segments_checked: int
    segments_valid: int
    segments_corrupted: list[CorruptedSegment] = field(default_factory=list)


@dataclass
class OrphanRecovery:
    """Orphan audio file recovery suggestion.
    
    Attributes:
        filepath: Path to orphan file
        probable_session: Session ID the file likely belongs to
        file_timestamp: File modification timestamp
        suggested_action: Recommended action
    """
    
    filepath: Path
    probable_session: Optional[str]
    file_timestamp: datetime
    suggested_action: str  # "attach_to_session" | "quarantine" | "delete"


class AudioCaptureService(ABC):
    """Service for capturing and persisting audio data.
    
    Per contracts/audio-capture.md for 004-resilient-voice-capture.
    """
    
    @abstractmethod
    def start_capture(self, session_id: str) -> CaptureContext:
        """Start audio capture for a session."""
        pass
    
    @abstractmethod
    def add_audio_chunk(
        self,
        session_id: str,
        audio_data: bytes,
        timestamp: datetime,
        source_metadata: Optional[dict] = None
    ) -> AudioEntry:
        """Add audio chunk to session with immediate persistence."""
        pass
    
    @abstractmethod
    def verify_integrity(self, session_id: str) -> IntegrityReport:
        """Verify all audio files match their stored checksums."""
        pass
    
    @abstractmethod
    def recover_orphans(self, sessions_dir: Path) -> list[OrphanRecovery]:
        """Find audio files not referenced in any session metadata."""
        pass


class DefaultAudioCaptureService(AudioCaptureService):
    """Default implementation of AudioCaptureService.
    
    Provides immediate persistence with fsync and atomic metadata updates.
    """
    
    def __init__(self, storage: SessionStorage, sessions_dir: Path) -> None:
        self._storage = storage
        self._sessions_dir = sessions_dir
    
    def start_capture(self, session_id: str) -> CaptureContext:
        """Start audio capture for a session."""
        session = self._storage.load(session_id)
        if session is None:
            raise SessionNotFoundError(session_id)
        
        if session.state != SessionState.COLLECTING:
            raise SessionNotCollectingError(session_id, session.state)
        
        return CaptureContext(
            session_id=session_id,
            started_at=datetime.now(timezone.utc),
            segment_count=len(session.audio_entries),
        )
    
    def add_audio_chunk(
        self,
        session_id: str,
        audio_data: bytes,
        timestamp: datetime,
        source_metadata: Optional[dict] = None
    ) -> AudioEntry:
        """Add audio chunk to session with immediate persistence.
        
        Guarantees:
        - Audio is fsynced to disk before return
        - Checksum computed and stored
        - Session metadata updated atomically
        """
        # Load session
        session = self._storage.load(session_id)
        if session is None:
            raise SessionNotFoundError(session_id)
        
        if session.state != SessionState.COLLECTING:
            raise SessionNotCollectingError(session_id, session.state)
        
        # Compute next sequence
        sequence = session.next_sequence
        
        # Generate filename
        time_part = timestamp.strftime("%H-%M-%S")
        filename = f"{sequence:03d}_{time_part}.ogg"
        
        # Prepare audio path
        audio_dir = self._sessions_dir / session_id / "audio"
        audio_path = audio_dir / filename
        
        # Compute checksum before writing
        checksum = ChecksumService.compute_bytes_checksum(audio_data)
        
        # Write audio with fsync
        try:
            self._write_with_fsync(audio_path, audio_data)
        except OSError as e:
            raise AudioPersistenceError(
                f"Failed to write audio: {e}",
                path=audio_path
            ) from e
        
        # Create audio entry
        telegram_file_id = ""
        if source_metadata and "telegram_file_id" in source_metadata:
            telegram_file_id = source_metadata["telegram_file_id"]
        
        entry = AudioEntry(
            sequence=sequence,
            received_at=timestamp,
            telegram_file_id=telegram_file_id,
            local_filename=filename,
            file_size_bytes=len(audio_data),
            duration_seconds=source_metadata.get("duration_seconds") if source_metadata else None,
            transcription_status=TranscriptionStatus.PENDING,
            checksum=checksum,
            reopen_epoch=session.reopen_count,
        )
        
        # Update session atomically
        session.audio_entries.append(entry)
        self._storage.save(session)
        
        return entry
    
    def verify_integrity(self, session_id: str) -> IntegrityReport:
        """Verify all audio files match their stored checksums."""
        session = self._storage.load(session_id)
        if session is None:
            raise SessionNotFoundError(session_id)
        
        corrupted: list[CorruptedSegment] = []
        valid_count = 0
        
        for entry in session.audio_entries:
            audio_path = self._sessions_dir / session_id / "audio" / entry.local_filename
            
            if not audio_path.exists():
                corrupted.append(CorruptedSegment(
                    sequence=entry.sequence,
                    filename=entry.local_filename,
                    expected_checksum=entry.checksum or "",
                    actual_checksum="<missing>",
                    suggested_action="missing: attempt recovery from backup",
                ))
                continue
            
            if entry.checksum:
                try:
                    if ChecksumService.verify_file_checksum(audio_path, entry.checksum):
                        valid_count += 1
                    else:
                        actual = ChecksumService.compute_file_checksum(audio_path)
                        corrupted.append(CorruptedSegment(
                            sequence=entry.sequence,
                            filename=entry.local_filename,
                            expected_checksum=entry.checksum,
                            actual_checksum=actual,
                            suggested_action="corrupted: compare with original source",
                        ))
                except Exception as e:
                    corrupted.append(CorruptedSegment(
                        sequence=entry.sequence,
                        filename=entry.local_filename,
                        expected_checksum=entry.checksum,
                        actual_checksum=f"<error: {e}>",
                        suggested_action="error: manual inspection required",
                    ))
            else:
                # No checksum stored (legacy entry), just check existence
                valid_count += 1
        
        return IntegrityReport(
            session_id=session_id,
            verified_at=datetime.now(timezone.utc),
            segments_checked=len(session.audio_entries),
            segments_valid=valid_count,
            segments_corrupted=corrupted,
        )
    
    def recover_orphans(self, sessions_dir: Path) -> list[OrphanRecovery]:
        """Find audio files not referenced in any session metadata."""
        orphans: list[OrphanRecovery] = []
        
        # Build set of all tracked audio files
        tracked_files: set[Path] = set()
        
        for session_dir in sessions_dir.iterdir():
            if not session_dir.is_dir():
                continue
            
            session_id = session_dir.name
            session = self._storage.load(session_id)
            
            if session:
                for entry in session.audio_entries:
                    tracked_files.add(session_dir / "audio" / entry.local_filename)
        
        # Find orphan files
        for session_dir in sessions_dir.iterdir():
            if not session_dir.is_dir():
                continue
            
            audio_dir = session_dir / "audio"
            if not audio_dir.exists():
                continue
            
            session_id = session_dir.name
            
            for audio_file in audio_dir.iterdir():
                if audio_file.is_file() and audio_file not in tracked_files:
                    stat = audio_file.stat()
                    orphans.append(OrphanRecovery(
                        filepath=audio_file,
                        probable_session=session_id,
                        file_timestamp=datetime.fromtimestamp(
                            stat.st_mtime, tz=timezone.utc
                        ),
                        suggested_action="attach_to_session",
                    ))
        
        return orphans
    
    def _write_with_fsync(self, path: Path, data: bytes) -> None:
        """Write data to file with fsync for durability."""
        with open(path, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
