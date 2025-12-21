"""Session models for Telegram Voice Orchestrator.

This module defines the core data structures for voice capture sessions,
following the data model specification in specs/002-telegram-voice-orchestrator/data-model.md.

All state is persisted as JSON for auditability and reproducibility.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from src.models.ui_state import UIPreferences, CheckpointData


class SessionState(str, Enum):
    """
    Session lifecycle states.

    State transitions:
        COLLECTING → TRANSCRIBING → TRANSCRIBED → EMBEDDING → READY
        READY → COLLECTING (on /reopen)
        COLLECTING → INTERRUPTED (on crash detection)
        INTERRUPTED → COLLECTING (on /recover)
        Any state → ERROR (on unrecoverable failure)
        
    Per data-model.md for 004-resilient-voice-capture.
    """

    # Active states
    COLLECTING = "COLLECTING"  # Session open, accepting audio messages
    
    # Processing states
    TRANSCRIBING = "TRANSCRIBING"  # Finalized, transcription in progress
    TRANSCRIBED = "TRANSCRIBED"  # All audios transcribed, ready for downstream
    EMBEDDING = "EMBEDDING"  # Generating embeddings (NEW for 004)
    PROCESSING = "PROCESSING"  # Downstream processor running
    PROCESSED = "PROCESSED"  # Downstream complete, all artifacts available
    
    # Terminal states
    READY = "READY"  # Fully processed, searchable (NEW for 004)
    ERROR = "ERROR"  # Unrecoverable error, session halted
    
    # Recovery states
    INTERRUPTED = "INTERRUPTED"  # Crash recovery needed (NEW for 004)

    @classmethod
    def allowed_transitions(cls) -> dict["SessionState", list["SessionState"]]:
        """Return allowed state transitions."""
        return {
            cls.COLLECTING: [cls.TRANSCRIBING, cls.INTERRUPTED, cls.ERROR],
            cls.TRANSCRIBING: [cls.TRANSCRIBED, cls.ERROR],
            cls.TRANSCRIBED: [cls.EMBEDDING, cls.PROCESSING, cls.COLLECTING, cls.ERROR],  # Can reopen
            cls.EMBEDDING: [cls.READY, cls.ERROR],
            cls.PROCESSING: [cls.PROCESSED, cls.ERROR],
            cls.PROCESSED: [cls.READY, cls.COLLECTING, cls.ERROR],  # Can reopen
            cls.READY: [cls.COLLECTING, cls.ERROR],  # Can reopen
            cls.INTERRUPTED: [cls.COLLECTING, cls.ERROR],  # Can recover
            cls.ERROR: [],  # Terminal state, no transitions allowed
        }

    def can_transition_to(self, new_state: "SessionState") -> bool:
        """Check if transition to new_state is allowed."""
        return new_state in self.allowed_transitions().get(self, [])


class NameSource(str, Enum):
    """
    Source of session's intelligible_name.

    Transition rules:
        FALLBACK_TIMESTAMP → TRANSCRIPTION (on first transcription complete)
        TRANSCRIPTION → LLM_TITLE (on LLM title extraction)
        Any → USER_ASSIGNED (on explicit user rename command)
    """

    FALLBACK_TIMESTAMP = "FALLBACK_TIMESTAMP"  # Auto-generated from creation time
    TRANSCRIPTION = "TRANSCRIPTION"  # Extracted from first transcription
    LLM_TITLE = "LLM_TITLE"  # Extracted by LLM processing
    USER_ASSIGNED = "USER_ASSIGNED"  # Explicitly named by user


class MatchType(str, Enum):
    """
    How a session reference was matched.

    Used when resolving natural language session references.
    Extended in 004-resilient-voice-capture for search types.
    """

    # Existing match types for session resolution
    EXACT_SUBSTRING = "EXACT_SUBSTRING"  # Name contains reference exactly
    FUZZY_SUBSTRING = "FUZZY_SUBSTRING"  # Name contains reference with edits
    SEMANTIC_SIMILARITY = "SEMANTIC_SIMILARITY"  # Embedding similarity match
    ACTIVE_CONTEXT = "ACTIVE_CONTEXT"  # Implicit (no reference, used active)
    AMBIGUOUS = "AMBIGUOUS"  # Multiple candidates, needs clarification
    NOT_FOUND = "NOT_FOUND"  # No match found
    
    # New match types for search (004-resilient-voice-capture)
    SEMANTIC = "SEMANTIC"  # Embedding similarity search
    TEXT = "TEXT"  # Substring/keyword match
    CHRONOLOGICAL = "CHRONOLOGICAL"  # Date-based listing


class ProcessingStatus(str, Enum):
    """Overall processing status for session.
    
    Tracks the progression of background processing tasks
    from audio capture through embedding generation.
    
    Per data-model.md for 004-resilient-voice-capture.
    """
    
    PENDING = "PENDING"  # Audio collected, not processed
    TRANSCRIPTION_QUEUED = "TRANSCRIPTION_QUEUED"
    TRANSCRIPTION_IN_PROGRESS = "TRANSCRIPTION_IN_PROGRESS"
    TRANSCRIPTION_COMPLETE = "TRANSCRIPTION_COMPLETE"
    EMBEDDING_QUEUED = "EMBEDDING_QUEUED"
    EMBEDDING_IN_PROGRESS = "EMBEDDING_IN_PROGRESS"
    COMPLETE = "COMPLETE"  # All processing done
    PARTIAL_FAILURE = "PARTIAL_FAILURE"  # Some segments failed


@dataclass
class SessionMatch:
    """
    Result of session reference resolution.

    Returned by SessionMatcher.resolve() to indicate how a natural
    language reference was matched to a session.

    Attributes:
        session_id: Matched session ID, or None if not found/ambiguous
        confidence: Match confidence in range [0.0, 1.0]
        match_type: How the match was determined
        candidates: Alternative session IDs if ambiguous (empty otherwise)
    """

    session_id: Optional[str]
    confidence: float
    match_type: MatchType
    candidates: list[str] = field(default_factory=list)


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
        checksum: SHA-256 checksum for integrity verification (NEW for 004)
        reopen_epoch: Which reopen cycle added this segment (0 = original, NEW for 004)
    """

    sequence: int
    received_at: datetime
    telegram_file_id: str
    local_filename: str
    file_size_bytes: int
    duration_seconds: Optional[float] = None
    transcription_status: TranscriptionStatus = TranscriptionStatus.PENDING
    transcript_filename: Optional[str] = None
    checksum: Optional[str] = None  # NEW: SHA-256 integrity checksum
    reopen_epoch: int = 0  # NEW: 0 = original session, increments on reopen

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
            "checksum": self.checksum,
            "reopen_epoch": self.reopen_epoch,
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
            checksum=data.get("checksum"),
            reopen_epoch=data.get("reopen_epoch", 0),
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
class ContextSnapshot:
    """
    Captures the context state at the moment of an LLM request (for auditability).
    
    Per data-model.md for 007-contextual-oracle-feedback.
    
    Attributes:
        transcript_count: Number of transcripts included (>= 0)
        llm_response_count: Number of prior LLM responses included (>= 0)
        include_llm_history: Whether LLM history was enabled
        total_tokens_estimate: Estimated token count (optional, >= 0 or None)
    """
    
    transcript_count: int
    llm_response_count: int
    include_llm_history: bool
    total_tokens_estimate: Optional[int] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "transcript_count": self.transcript_count,
            "llm_response_count": self.llm_response_count,
            "include_llm_history": self.include_llm_history,
            "total_tokens_estimate": self.total_tokens_estimate,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "ContextSnapshot":
        """Create from dictionary (JSON deserialization)."""
        return cls(
            transcript_count=data["transcript_count"],
            llm_response_count=data["llm_response_count"],
            include_llm_history=data["include_llm_history"],
            total_tokens_estimate=data.get("total_tokens_estimate"),
        )


@dataclass
class LlmEntry:
    """
    Represents one LLM response stored in a session.
    
    Per data-model.md for 007-contextual-oracle-feedback.
    
    Attributes:
        sequence: 1-indexed order of LLM responses in session (>= 1)
        created_at: Timestamp when response was generated (UTC)
        oracle_name: Display name of the oracle used (non-empty)
        oracle_id: 8-char hash identifier of the oracle (matches Oracle.id)
        response_filename: Filename in llm_responses/ folder (pattern: {seq}_{name}.txt)
        context_snapshot: State of context at request time (embedded object)
    
    Validation Rules:
        - sequence must be unique within session's llm_entries
        - response_filename must exist in session's llm_responses/ directory
        - oracle_id should match a known oracle (warning if orphaned)
    """
    
    sequence: int
    created_at: datetime
    oracle_name: str
    oracle_id: str
    response_filename: str
    context_snapshot: ContextSnapshot
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "sequence": self.sequence,
            "created_at": self.created_at.isoformat(),
            "oracle_name": self.oracle_name,
            "oracle_id": self.oracle_id,
            "response_filename": self.response_filename,
            "context_snapshot": self.context_snapshot.to_dict(),
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "LlmEntry":
        """Create from dictionary (JSON deserialization)."""
        return cls(
            sequence=data["sequence"],
            created_at=datetime.fromisoformat(data["created_at"]),
            oracle_name=data["oracle_name"],
            oracle_id=data["oracle_id"],
            response_filename=data["response_filename"],
            context_snapshot=ContextSnapshot.from_dict(data["context_snapshot"]),
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
        intelligible_name: Human-readable session name (NEW)
        name_source: Origin of the intelligible name (NEW)
        embedding: Semantic vector for matching (NEW, optional, 384-dim)
        finalized_at: When the session was finalized (None if still collecting)
        audio_entries: List of captured audio messages
        errors: List of errors that occurred during processing
        reopen_count: Number of times session has been reopened (NEW for 004)
        processing_status: Overall processing status (NEW for 004)
    """

    id: str
    state: SessionState
    created_at: datetime
    chat_id: int
    intelligible_name: str = ""
    name_source: NameSource = NameSource.FALLBACK_TIMESTAMP
    embedding: Optional[list[float]] = None
    finalized_at: Optional[datetime] = None
    audio_entries: list[AudioEntry] = field(default_factory=list)
    errors: list[ErrorEntry] = field(default_factory=list)
    llm_entries: list[LlmEntry] = field(default_factory=list)  # NEW for 007-contextual-oracle-feedback
    reopen_count: int = 0  # NEW: How many times session was reopened
    processing_status: ProcessingStatus = ProcessingStatus.PENDING  # NEW
    # UI presentation layer fields (005-telegram-ux-overhaul)
    ui_preferences: Optional["UIPreferences"] = None
    checkpoint_data: Optional["CheckpointData"] = None

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

    def llm_responses_path(self, sessions_root: Path) -> Path:
        """Get the path to the llm_responses subdirectory."""
        return self.folder_path(sessions_root) / "llm_responses"

    def metadata_path(self, sessions_root: Path) -> Path:
        """Get the path to the metadata.json file."""
        return self.folder_path(sessions_root) / "metadata.json"

    @property
    def audio_count(self) -> int:
        """Get the number of audio entries."""
        return len(self.audio_entries)

    @property
    def llm_count(self) -> int:
        """Get the number of LLM response entries."""
        return len(self.llm_entries)

    @property
    def next_llm_sequence(self) -> int:
        """Get the next available LLM sequence number."""
        if not self.llm_entries:
            return 1
        return max(e.sequence for e in self.llm_entries) + 1

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
    
    @property
    def can_reopen(self) -> bool:
        """Check if session can be reopened for additional audio."""
        return self.state == SessionState.READY
    
    @property
    def total_audio_duration(self) -> float:
        """Get total duration of all audio entries in seconds."""
        return sum(
            e.duration_seconds or 0.0 
            for e in self.audio_entries
        )
    
    @property
    def pending_transcription_count(self) -> int:
        """Count audio entries pending transcription."""
        return sum(
            1 for e in self.audio_entries 
            if e.transcription_status == TranscriptionStatus.PENDING
        )

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "state": self.state.value,
            "created_at": self.created_at.isoformat(),
            "chat_id": self.chat_id,
            "intelligible_name": self.intelligible_name,
            "name_source": self.name_source.value,
            "embedding": self.embedding,
            "finalized_at": self.finalized_at.isoformat() if self.finalized_at else None,
            "audio_entries": [e.to_dict() for e in self.audio_entries],
            "errors": [e.to_dict() for e in self.errors],
            "llm_entries": [e.to_dict() for e in self.llm_entries],  # NEW for 007
            "reopen_count": self.reopen_count,
            "processing_status": self.processing_status.value,
            # UI presentation layer fields (005-telegram-ux-overhaul)
            "ui_preferences": self.ui_preferences.to_dict() if self.ui_preferences else None,
            "checkpoint_data": self.checkpoint_data.to_dict() if self.checkpoint_data else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Session":
        """Create from dictionary (JSON deserialization)."""
        # Import here to avoid circular imports
        from src.models.ui_state import UIPreferences, CheckpointData
        
        ui_prefs = None
        if data.get("ui_preferences"):
            ui_prefs = UIPreferences.from_dict(data["ui_preferences"])
        
        checkpoint = None
        if data.get("checkpoint_data"):
            checkpoint = CheckpointData.from_dict(data["checkpoint_data"])
        
        return cls(
            id=data["id"],
            state=SessionState(data["state"]),
            created_at=datetime.fromisoformat(data["created_at"]),
            chat_id=data["chat_id"],
            intelligible_name=data.get("intelligible_name", ""),
            name_source=NameSource(data.get("name_source", "FALLBACK_TIMESTAMP")),
            embedding=data.get("embedding"),
            finalized_at=(
                datetime.fromisoformat(data["finalized_at"])
                if data.get("finalized_at")
                else None
            ),
            audio_entries=[AudioEntry.from_dict(e) for e in data.get("audio_entries", [])],
            errors=[ErrorEntry.from_dict(e) for e in data.get("errors", [])],
            llm_entries=[LlmEntry.from_dict(e) for e in data.get("llm_entries", [])],  # NEW for 007
            reopen_count=data.get("reopen_count", 0),
            processing_status=ProcessingStatus(
                data.get("processing_status", "PENDING")
            ),
            ui_preferences=ui_prefs,
            checkpoint_data=checkpoint,
        )
