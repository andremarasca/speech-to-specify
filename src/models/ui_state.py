"""UI state models for Telegram UX presentation layer.

Per data-model.md for 005-telegram-ux-overhaul.

This module defines presentation-layer entities that extend the existing
session model without modifying core business logic. All entities here
are for managing Telegram UI interactions.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Any


# =============================================================================
# Enums
# =============================================================================


class KeyboardType(str, Enum):
    """Types of inline keyboards displayed to user.
    
    Per data-model.md for 005-telegram-ux-overhaul.
    """
    
    SESSION_ACTIVE = "SESSION_ACTIVE"      # Finalize, Status, Help
    SESSION_EMPTY = "SESSION_EMPTY"        # Start Recording hint, Help
    PROCESSING = "PROCESSING"              # Cancel only
    RESULTS = "RESULTS"                    # View Full, Search, Start Pipeline
    CONFIRMATION = "CONFIRMATION"          # Dynamic based on ConfirmationContext
    SESSION_CONFLICT = "SESSION_CONFLICT"  # Finalize Current, Start New, Return
    ERROR_RECOVERY = "ERROR_RECOVERY"      # Retry, Cancel, Help
    PAGINATION = "PAGINATION"              # Previous, Next, Close
    HELP_CONTEXT = "HELP_CONTEXT"          # Back, related actions
    TIMEOUT = "TIMEOUT"                    # Continue, Cancel
    SEARCH_RESULTS = "SEARCH_RESULTS"      # Dynamic search results (006-semantic-session-search)
    SEARCH_NO_RESULTS = "SEARCH_NO_RESULTS"  # No results found + retry options


class OperationType(str, Enum):
    """Types of long-running operations for progress tracking.
    
    Per data-model.md for 005-telegram-ux-overhaul.
    """
    
    TRANSCRIPTION = "TRANSCRIPTION"   # Audio → text via Whisper
    EMBEDDING = "EMBEDDING"           # Text → vector via sentence-transformers
    PROCESSING = "PROCESSING"         # Full artifact pipeline
    SEARCH = "SEARCH"                 # Semantic search (usually fast)


class ErrorSeverity(str, Enum):
    """Severity level for user-facing errors.
    
    Per data-model.md for 005-telegram-ux-overhaul.
    """
    
    INFO = "INFO"           # Informational, no action required
    WARNING = "WARNING"     # Warning, operation can continue
    ERROR = "ERROR"         # Error, operation failed but recoverable
    CRITICAL = "CRITICAL"   # Critical, system-level issue


class ConfirmationType(str, Enum):
    """Types of confirmation dialogs.
    
    Per data-model.md for 005-telegram-ux-overhaul.
    """
    
    SESSION_CONFLICT = "SESSION_CONFLICT"     # New session would overwrite active
    CANCEL_OPERATION = "CANCEL_OPERATION"     # Cancel in-progress operation
    DISCARD_SESSION = "DISCARD_SESSION"       # Discard session with data
    DISCARD_ORPHAN = "DISCARD_ORPHAN"         # Discard orphaned session


class ProgressStatus(str, Enum):
    """Status of a progress tracking operation.
    
    Per data-model.md for 005-telegram-ux-overhaul.
    """
    
    ACTIVE = "ACTIVE"       # Operation in progress
    COMPLETED = "COMPLETED" # Operation finished successfully
    TIMEOUT = "TIMEOUT"     # Operation exceeded timeout threshold
    CANCELLED = "CANCELLED" # User cancelled operation
    ERROR = "ERROR"         # Operation failed


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class UIPreferences:
    """User interface preferences stored per-session.
    
    Per data-model.md for 005-telegram-ux-overhaul.
    Extended for 007-contextual-oracle-feedback.
    
    Attributes:
        simplified_ui: When true, no decorative emojis, explicit text descriptions
        include_llm_history: When true, prior LLM responses are included in context (default: True)
    """
    
    simplified_ui: bool = False
    include_llm_history: bool = True  # NEW for 007-contextual-oracle-feedback
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "simplified_ui": self.simplified_ui,
            "include_llm_history": self.include_llm_history,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "UIPreferences":
        """Create from dictionary (JSON deserialization)."""
        return cls(
            simplified_ui=data.get("simplified_ui", False),
            include_llm_history=data.get("include_llm_history", True),
        )


@dataclass
class RecoveryAction:
    """An actionable recovery option for an error.
    
    Per data-model.md for 005-telegram-ux-overhaul.
    
    Attributes:
        label: Button text shown to user
        callback_data: Callback data for button handler
    """
    
    label: str
    callback_data: str
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "label": self.label,
            "callback_data": self.callback_data,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "RecoveryAction":
        """Create from dictionary (JSON deserialization)."""
        return cls(
            label=data["label"],
            callback_data=data["callback_data"],
        )


@dataclass
class UserFacingError:
    """Structured error for humanized presentation.
    
    Per data-model.md for 005-telegram-ux-overhaul.
    
    Attributes:
        error_code: Unique error identifier (e.g., "ERR_STORAGE_001")
        message: User-friendly description (no technical jargon)
        suggestions: List of actionable recovery hints
        recovery_actions: List of buttons with callback handlers
        severity: Error severity level
    """
    
    error_code: str
    message: str
    suggestions: list[str] = field(default_factory=list)
    recovery_actions: list[RecoveryAction] = field(default_factory=list)
    severity: ErrorSeverity = ErrorSeverity.ERROR
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "error_code": self.error_code,
            "message": self.message,
            "suggestions": self.suggestions,
            "recovery_actions": [a.to_dict() for a in self.recovery_actions],
            "severity": self.severity.value,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "UserFacingError":
        """Create from dictionary (JSON deserialization)."""
        return cls(
            error_code=data["error_code"],
            message=data["message"],
            suggestions=data.get("suggestions", []),
            recovery_actions=[
                RecoveryAction.from_dict(a) for a in data.get("recovery_actions", [])
            ],
            severity=ErrorSeverity(data.get("severity", "ERROR")),
        )


@dataclass
class ConfirmationOption:
    """An option in a confirmation dialog.
    
    Per data-model.md for 005-telegram-ux-overhaul.
    
    Attributes:
        label: Button text shown to user
        callback_data: Callback data for button handler
        is_destructive: Whether this action is destructive (for UI styling)
    """
    
    label: str
    callback_data: str
    is_destructive: bool = False
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "label": self.label,
            "callback_data": self.callback_data,
            "is_destructive": self.is_destructive,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "ConfirmationOption":
        """Create from dictionary (JSON deserialization)."""
        return cls(
            label=data["label"],
            callback_data=data["callback_data"],
            is_destructive=data.get("is_destructive", False),
        )


@dataclass
class ConfirmationContext:
    """Context for confirmation dialogs.
    
    Per data-model.md for 005-telegram-ux-overhaul.
    
    Attributes:
        confirmation_type: Type of confirmation dialog
        context_data: Type-specific context (e.g., session_id, audio_count)
        options: List of confirmation options
        expires_at: Optional auto-dismiss timeout
    """
    
    confirmation_type: ConfirmationType
    context_data: dict[str, Any] = field(default_factory=dict)
    options: list[ConfirmationOption] = field(default_factory=list)
    expires_at: Optional[datetime] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "confirmation_type": self.confirmation_type.value,
            "context_data": self.context_data,
            "options": [o.to_dict() for o in self.options],
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "ConfirmationContext":
        """Create from dictionary (JSON deserialization)."""
        expires_at = None
        if data.get("expires_at"):
            expires_at = datetime.fromisoformat(data["expires_at"])
        return cls(
            confirmation_type=ConfirmationType(data["confirmation_type"]),
            context_data=data.get("context_data", {}),
            options=[ConfirmationOption.from_dict(o) for o in data.get("options", [])],
            expires_at=expires_at,
        )


@dataclass
class UIState:
    """Transient state for managing Telegram message interactions.
    
    Per data-model.md for 005-telegram-ux-overhaul.
    
    Note: This is transient - not persisted to disk. 
    Can be reconstructed from session state.
    
    Attributes:
        status_message_id: ID of pinned status message for editing
        last_keyboard_type: Current keyboard being displayed
        pending_confirmation: For confirmation dialogs
        progress_message_id: ID of progress message being updated
    """
    
    status_message_id: Optional[int] = None
    last_keyboard_type: KeyboardType = KeyboardType.SESSION_EMPTY
    pending_confirmation: Optional[ConfirmationContext] = None
    progress_message_id: Optional[int] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "status_message_id": self.status_message_id,
            "last_keyboard_type": self.last_keyboard_type.value,
            "pending_confirmation": (
                self.pending_confirmation.to_dict() 
                if self.pending_confirmation else None
            ),
            "progress_message_id": self.progress_message_id,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "UIState":
        """Create from dictionary (JSON deserialization)."""
        pending = None
        if data.get("pending_confirmation"):
            pending = ConfirmationContext.from_dict(data["pending_confirmation"])
        return cls(
            status_message_id=data.get("status_message_id"),
            last_keyboard_type=KeyboardType(
                data.get("last_keyboard_type", "SESSION_EMPTY")
            ),
            pending_confirmation=pending,
            progress_message_id=data.get("progress_message_id"),
        )


@dataclass
class ProgressState:
    """State for tracking and displaying operation progress.
    
    Per data-model.md for 005-telegram-ux-overhaul.
    
    Attributes:
        operation_id: Unique ID for this operation
        operation_type: Type of operation (TRANSCRIPTION, etc.)
        current_step: Current step number (0-indexed)
        total_steps: Total number of steps
        step_description: Human-readable current action
        started_at: Timestamp when operation started
        estimated_completion: ETA based on heuristics
        last_update_at: For throttling UI updates
        status: Current status of the operation
    """
    
    operation_id: str
    operation_type: OperationType
    current_step: int
    total_steps: int
    step_description: str
    started_at: datetime
    last_update_at: datetime
    estimated_completion: Optional[datetime] = None
    status: ProgressStatus = ProgressStatus.ACTIVE
    
    @property
    def percentage(self) -> int:
        """Calculate completion percentage."""
        if self.total_steps == 0:
            return 0
        return min(100, int((self.current_step / self.total_steps) * 100))
    
    @property
    def is_complete(self) -> bool:
        """Check if operation is complete."""
        return self.status in (ProgressStatus.COMPLETED, ProgressStatus.ERROR)
    
    @property
    def elapsed_seconds(self) -> float:
        """Calculate elapsed time in seconds."""
        return (datetime.now() - self.started_at).total_seconds()
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "operation_id": self.operation_id,
            "operation_type": self.operation_type.value,
            "current_step": self.current_step,
            "total_steps": self.total_steps,
            "step_description": self.step_description,
            "started_at": self.started_at.isoformat(),
            "last_update_at": self.last_update_at.isoformat(),
            "estimated_completion": (
                self.estimated_completion.isoformat() 
                if self.estimated_completion else None
            ),
            "status": self.status.value,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "ProgressState":
        """Create from dictionary (JSON deserialization)."""
        estimated = None
        if data.get("estimated_completion"):
            estimated = datetime.fromisoformat(data["estimated_completion"])
        return cls(
            operation_id=data["operation_id"],
            operation_type=OperationType(data["operation_type"]),
            current_step=data["current_step"],
            total_steps=data["total_steps"],
            step_description=data["step_description"],
            started_at=datetime.fromisoformat(data["started_at"]),
            last_update_at=datetime.fromisoformat(data["last_update_at"]),
            estimated_completion=estimated,
            status=ProgressStatus(data.get("status", "ACTIVE")),
        )


@dataclass
class CheckpointData:
    """Checkpoint data for crash recovery.
    
    Per plan.md for 005-telegram-ux-overhaul.
    
    Attributes:
        last_checkpoint_at: When the last checkpoint was saved
        last_audio_sequence: Sequence number of last received audio
        processing_state: State of processing at checkpoint
        ui_state: UI state at checkpoint (optional)
    """
    
    last_checkpoint_at: datetime
    last_audio_sequence: int = 0
    processing_state: Optional[str] = None
    ui_state: Optional[UIState] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "last_checkpoint_at": self.last_checkpoint_at.isoformat(),
            "last_audio_sequence": self.last_audio_sequence,
            "processing_state": self.processing_state,
            "ui_state": self.ui_state.to_dict() if self.ui_state else None,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "CheckpointData":
        """Create from dictionary (JSON deserialization)."""
        ui_state = None
        if data.get("ui_state"):
            ui_state = UIState.from_dict(data["ui_state"])
        return cls(
            last_checkpoint_at=datetime.fromisoformat(data["last_checkpoint_at"]),
            last_audio_sequence=data.get("last_audio_sequence", 0),
            processing_state=data.get("processing_state"),
            ui_state=ui_state,
        )
