# Contract: Session Lifecycle Service

**Feature**: 004-resilient-voice-capture  
**Service**: `SessionLifecycleService`  
**Location**: `src/services/session/lifecycle.py` (extends existing `manager.py`)

## Purpose

Manages session lifecycle including creation, finalization, reopening, and state transitions. Ensures sessions follow valid state machine transitions and supports crash recovery.

## Interface

```python
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

class SessionLifecycleService(ABC):
    """Service for session lifecycle management."""
    
    @abstractmethod
    def create_session(self, chat_id: int) -> Session:
        """
        Create new session in COLLECTING state.
        
        Args:
            chat_id: User/chat identifier
            
        Returns:
            New session ready for audio capture
            
        Raises:
            ActiveSessionExistsError: User already has active session
        """
        pass
    
    @abstractmethod
    def finalize_session(self, session_id: str) -> FinalizeResult:
        """
        Finalize session and queue for processing.
        
        Transitions: COLLECTING → TRANSCRIBING
        
        Args:
            session_id: Session to finalize
            
        Returns:
            FinalizeResult with audio count and processing status
            
        Raises:
            SessionNotFoundError: Session doesn't exist
            InvalidStateError: Session not in COLLECTING state
        """
        pass
    
    @abstractmethod
    def reopen_session(self, session_id: str) -> ReopenResult:
        """
        Reopen a finalized session for additional audio.
        
        Transitions: READY → COLLECTING
        
        Args:
            session_id: Session to reopen
            
        Returns:
            ReopenResult with session info and new reopen_epoch
            
        Raises:
            SessionNotFoundError: Session doesn't exist
            InvalidStateError: Session not in READY state
            SessionCorruptedError: Session data corrupted
        """
        pass
    
    @abstractmethod
    def get_session_status(self, session_id: str) -> SessionStatus:
        """
        Get current session status including processing progress.
        
        Args:
            session_id: Session to query
            
        Returns:
            SessionStatus with state, progress, and any errors
        """
        pass
    
    @abstractmethod
    def list_sessions(
        self,
        chat_id: Optional[int] = None,
        state: Optional[SessionState] = None,
        limit: int = 50
    ) -> list[SessionSummary]:
        """
        List sessions with optional filtering.
        
        Args:
            chat_id: Filter by user (None = all users)
            state: Filter by state (None = all states)
            limit: Maximum results
            
        Returns:
            List of session summaries, newest first
        """
        pass
    
    @abstractmethod
    def get_active_session(self, chat_id: int) -> Optional[Session]:
        """
        Get current active (COLLECTING) session for user.
        
        Args:
            chat_id: User identifier
            
        Returns:
            Active session or None if no active session
        """
        pass
    
    @abstractmethod
    def detect_interrupted_sessions(self) -> list[InterruptedSession]:
        """
        Find sessions that may have been interrupted by crash.
        
        Criteria:
        - State is COLLECTING
        - No audio received in > threshold time
        - Session folder has orphan files
        
        Returns:
            List of interrupted sessions with recovery options
        """
        pass
    
    @abstractmethod
    def recover_session(
        self, 
        session_id: str, 
        action: RecoveryAction
    ) -> RecoverResult:
        """
        Recover an interrupted session.
        
        Args:
            session_id: Interrupted session
            action: RESUME (continue) | FINALIZE (process as-is) | DISCARD
            
        Returns:
            RecoverResult with new session state
        """
        pass
```

## Data Types

```python
@dataclass
class FinalizeResult:
    """Result of session finalization."""
    session_id: str
    audio_count: int
    total_duration_seconds: float
    transcription_queued: bool
    message: str  # User-friendly confirmation

@dataclass
class ReopenResult:
    """Result of session reopen."""
    session_id: str
    reopen_epoch: int  # New epoch number
    previous_audio_count: int
    session_name: str
    message: str

@dataclass
class SessionStatus:
    """Current session status."""
    session_id: str
    state: SessionState
    processing_status: ProcessingStatus
    audio_count: int
    transcribed_count: int
    failed_count: int
    progress_percent: float
    errors: list[str]
    can_reopen: bool
    
@dataclass
class SessionSummary:
    """Brief session info for listings."""
    session_id: str
    intelligible_name: str
    state: SessionState
    created_at: datetime
    audio_count: int
    total_duration_seconds: float

@dataclass
class InterruptedSession:
    """Session potentially interrupted by crash."""
    session_id: str
    last_audio_at: datetime
    audio_count: int
    orphan_files: list[str]
    recovery_options: list[RecoveryAction]

class RecoveryAction(str, Enum):
    RESUME = "RESUME"      # Continue collecting
    FINALIZE = "FINALIZE"  # Process what exists
    DISCARD = "DISCARD"    # Abandon session (audio preserved)
    
@dataclass
class RecoverResult:
    """Result of recovery action."""
    session_id: str
    action_taken: RecoveryAction
    new_state: SessionState
    message: str
```

## State Machine Rules

### Valid Transitions (from data-model.md)

```python
VALID_TRANSITIONS = {
    None: [SessionState.COLLECTING],  # Creation
    SessionState.COLLECTING: [
        SessionState.TRANSCRIBING,    # /close
        SessionState.INTERRUPTED,     # Crash detected
    ],
    SessionState.INTERRUPTED: [
        SessionState.COLLECTING,      # Resume
        SessionState.TRANSCRIBING,    # Finalize as-is
    ],
    SessionState.TRANSCRIBING: [
        SessionState.TRANSCRIBED,     # Transcription complete
        SessionState.ERROR,           # Unrecoverable failure
    ],
    SessionState.TRANSCRIBED: [
        SessionState.EMBEDDING,       # Auto
    ],
    SessionState.EMBEDDING: [
        SessionState.READY,           # Success or fallback
    ],
    SessionState.READY: [
        SessionState.COLLECTING,      # /reopen
    ],
}
```

### Transition Side Effects

| Transition | Side Effect |
|------------|-------------|
| → COLLECTING | Increment `reopen_count` if from READY |
| → TRANSCRIBING | Set `finalized_at`, queue transcription |
| → TRANSCRIBED | Update `processing_status` |
| → EMBEDDING | Queue embedding generation |
| → READY | Mark `processing_status = COMPLETE` |
| → INTERRUPTED | Log interruption, preserve all data |

## Test Cases (Contract Tests)

```python
def test_create_session_collecting_state():
    """New session must be in COLLECTING state."""

def test_finalize_transitions_to_transcribing():
    """Finalize must change state to TRANSCRIBING."""
    
def test_finalize_rejects_non_collecting():
    """Finalize must reject sessions not in COLLECTING."""
    
def test_reopen_increments_epoch():
    """Reopen must increment reopen_count and return new epoch."""
    
def test_reopen_preserves_existing_audio():
    """Reopen must not modify existing audio entries."""
    
def test_detect_interrupted_by_time_gap():
    """Interrupted detection based on time since last audio."""
    
def test_recovery_resume_returns_to_collecting():
    """RESUME action must return session to COLLECTING."""
    
def test_recovery_finalize_queues_processing():
    """FINALIZE action must queue existing audio for processing."""
```

## Feedback Requirements (Constitution: Pillar II)

All operations MUST return user-friendly messages:

| Operation | Success Message |
|-----------|-----------------|
| create | "✅ Session started. Recording active." |
| finalize | "✅ Session finalized. {n} audio files queued for transcription." |
| reopen | "✅ Session '{name}' reopened. You can now add more audio." |
| recover (RESUME) | "✅ Session recovered. Recording resumed." |
| recover (FINALIZE) | "✅ Interrupted session finalized. Processing {n} audio files." |

## Dependencies

- `SessionStorage`: Atomic persistence
- `TranscriptionQueue`: Queue finalized sessions
- `AudioCaptureService`: Verify audio integrity on reopen
