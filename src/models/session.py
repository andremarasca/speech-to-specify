"""Session models for Telegram Voice Orchestrator.

This module defines the core data structures for voice capture sessions,
following the data model specification in specs/002-telegram-voice-orchestrator/data-model.md.

All state is persisted as JSON for auditability and reproducibility.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional


class SessionState(str, Enum):
    """
    Session lifecycle states.

    State transitions:
        COLLECTING → TRANSCRIBING → TRANSCRIBED → PROCESSING → PROCESSED
        Any state → ERROR (on unrecoverable failure)
    """

    COLLECTING = "COLLECTING"  # Session open, accepting audio messages
    TRANSCRIBING = "TRANSCRIBING"  # Finalized, transcription in progress
    TRANSCRIBED = "TRANSCRIBED"  # All audios transcribed, ready for downstream
    PROCESSING = "PROCESSING"  # Downstream processor running
    PROCESSED = "PROCESSED"  # Downstream complete, all artifacts available
    ERROR = "ERROR"  # Unrecoverable error, session halted

    @classmethod
    def allowed_transitions(cls) -> dict["SessionState", list["SessionState"]]:
        """Return allowed state transitions."""
        return {
            cls.COLLECTING: [cls.TRANSCRIBING, cls.ERROR],
            cls.TRANSCRIBING: [cls.TRANSCRIBED, cls.ERROR],
            cls.TRANSCRIBED: [cls.PROCESSING, cls.ERROR],
            cls.PROCESSING: [cls.PROCESSED, cls.ERROR],
            cls.PROCESSED: [cls.ERROR],  # Terminal state, only error possible
            cls.ERROR: [],  # Terminal state, no transitions allowed
        }

    def can_transition_to(self, new_state: "SessionState") -> bool:
        """Check if transition to new_state is allowed."""
        return new_state in self.allowed_transitions().get(self, [])


class TranscriptionStatus(str, Enum):
    """Status of transcription for an audio entry."""

    PENDING = "PENDING"  # Audio received, not yet transcribed
    SUCCESS = "SUCCESS"  # Transcription completed
    FAILED = "FAILED"  # Transcription failed (error logged)


@dataclass
class AudioEntry:
    """
    Represents one captured voice message.

    Attributes:
        sequence: 1-indexed order of receipt
        received_at: Timestamp when audio was received
        telegram_file_id: Telegram file ID for re-download if needed
        local_filename: Filename in session/audio/ folder (e.g., "001_audio.ogg")
        file_size_bytes: Size of the audio file
        duration_seconds: Duration of audio (if available from Telegram)
        transcription_status: Current transcription status
        transcript_filename: Filename of transcript (e.g., "001_audio.txt")
    """

    sequence: int
    received_at: datetime
    telegram_file_id: str
    local_filename: str
    file_size_bytes: int
    duration_seconds: Optional[float] = None
    transcription_status: TranscriptionStatus = TranscriptionStatus.PENDING
    transcript_filename: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "sequence": self.sequence,
            "received_at": self.received_at.isoformat(),
            "telegram_file_id": self.telegram_file_id,
            "local_filename": self.local_filename,
            "file_size_bytes": self.file_size_bytes,
            "duration_seconds": self.duration_seconds,
            "transcription_status": self.transcription_status.value,
            "transcript_filename": self.transcript_filename,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AudioEntry":
        """Create from dictionary (JSON deserialization)."""
        return cls(
            sequence=data["sequence"],
            received_at=datetime.fromisoformat(data["received_at"]),
            telegram_file_id=data["telegram_file_id"],
            local_filename=data["local_filename"],
            file_size_bytes=data["file_size_bytes"],
            duration_seconds=data.get("duration_seconds"),
            transcription_status=TranscriptionStatus(data["transcription_status"]),
            transcript_filename=data.get("transcript_filename"),
        )


@dataclass
class ErrorEntry:
    """
    Represents an error that occurred during session processing.

    Attributes:
        timestamp: When the error occurred
        operation: Type of operation that failed (download, transcribe, process)
        target: File or operation reference (optional)
        message: Human-readable error description
        recoverable: Whether the operation can be retried
    """

    timestamp: datetime
    operation: str  # "download" | "transcribe" | "process"
    message: str
    target: Optional[str] = None
    recoverable: bool = False

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "operation": self.operation,
            "target": self.target,
            "message": self.message,
            "recoverable": self.recoverable,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ErrorEntry":
        """Create from dictionary (JSON deserialization)."""
        return cls(
            timestamp=datetime.fromisoformat(data["timestamp"]),
            operation=data["operation"],
            target=data.get("target"),
            message=data["message"],
            recoverable=data.get("recoverable", False),
        )


@dataclass
class Session:
    """
    Represents a voice capture session.

    A session is the fundamental unit of work - it captures a sequence of
    voice messages, transcribes them, and optionally processes them through
    a downstream pipeline.

    Session folders are self-contained and immutable after finalization.

    Attributes:
        id: Unique timestamp-based identifier (YYYY-MM-DD_HH-MM-SS)
        state: Current session state
        created_at: When the session was created
        chat_id: Telegram chat ID associated with this session
        finalized_at: When the session was finalized (None if still collecting)
        audio_entries: List of captured audio messages
        errors: List of errors that occurred during processing
    """

    id: str
    state: SessionState
    created_at: datetime
    chat_id: int
    finalized_at: Optional[datetime] = None
    audio_entries: list[AudioEntry] = field(default_factory=list)
    errors: list[ErrorEntry] = field(default_factory=list)

    def folder_path(self, sessions_root: Path) -> Path:
        """Get the filesystem path for this session's folder."""
        return sessions_root / self.id

    def audio_path(self, sessions_root: Path) -> Path:
        """Get the path to the audio subdirectory."""
        return self.folder_path(sessions_root) / "audio"

    def transcripts_path(self, sessions_root: Path) -> Path:
        """Get the path to the transcripts subdirectory."""
        return self.folder_path(sessions_root) / "transcripts"

    def process_path(self, sessions_root: Path) -> Path:
        """Get the path to the process subdirectory."""
        return self.folder_path(sessions_root) / "process"

    def metadata_path(self, sessions_root: Path) -> Path:
        """Get the path to the metadata.json file."""
        return self.folder_path(sessions_root) / "metadata.json"

    @property
    def audio_count(self) -> int:
        """Get the number of audio entries."""
        return len(self.audio_entries)

    @property
    def next_sequence(self) -> int:
        """Get the next available sequence number."""
        if not self.audio_entries:
            return 1
        return max(e.sequence for e in self.audio_entries) + 1

    @property
    def is_finalized(self) -> bool:
        """Check if session is finalized (past COLLECTING state)."""
        return self.state != SessionState.COLLECTING

    @property
    def can_add_audio(self) -> bool:
        """Check if audio can be added to this session."""
        return self.state == SessionState.COLLECTING

    @property
    def can_finalize(self) -> bool:
        """Check if session can be finalized."""
        return self.state == SessionState.COLLECTING and self.audio_count > 0

    @property
    def can_process(self) -> bool:
        """Check if session can be sent to downstream processing."""
        return self.state == SessionState.TRANSCRIBED

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "state": self.state.value,
            "created_at": self.created_at.isoformat(),
            "chat_id": self.chat_id,
            "finalized_at": self.finalized_at.isoformat() if self.finalized_at else None,
            "audio_entries": [e.to_dict() for e in self.audio_entries],
            "errors": [e.to_dict() for e in self.errors],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Session":
        """Create from dictionary (JSON deserialization)."""
        return cls(
            id=data["id"],
            state=SessionState(data["state"]),
            created_at=datetime.fromisoformat(data["created_at"]),
            chat_id=data["chat_id"],
            finalized_at=(
                datetime.fromisoformat(data["finalized_at"])
                if data.get("finalized_at")
                else None
            ),
            audio_entries=[AudioEntry.from_dict(e) for e in data.get("audio_entries", [])],
            errors=[ErrorEntry.from_dict(e) for e in data.get("errors", [])],
        )
