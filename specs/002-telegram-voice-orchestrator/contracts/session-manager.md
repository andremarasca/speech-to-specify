# Contract: Session Manager

**Module**: `src/services/session/`  
**Purpose**: Manage session lifecycle, state transitions, and folder structure

## Interface

### SessionManager

```python
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

class SessionManager(ABC):
    @abstractmethod
    def get_active_session(self) -> Optional[Session]:
        """Return current session in COLLECTING state, or None."""
        pass
    
    @abstractmethod
    def create_session(self, chat_id: int) -> Session:
        """
        Create new session. 
        If active session exists, finalize it first (auto-finalize).
        Returns the new session.
        """
        pass
    
    @abstractmethod
    def finalize_session(self, session_id: str) -> Session:
        """
        Finalize session (COLLECTING → TRANSCRIBING).
        Raises: InvalidStateError if not in COLLECTING state.
        """
        pass
    
    @abstractmethod
    def add_audio(self, session_id: str, audio_entry: AudioEntry) -> Session:
        """
        Add audio entry to session.
        Raises: InvalidStateError if session not in COLLECTING state.
        """
        pass
    
    @abstractmethod
    def update_transcription_status(
        self, 
        session_id: str, 
        sequence: int, 
        status: TranscriptionStatus,
        transcript_filename: Optional[str] = None
    ) -> Session:
        """Update transcription status for specific audio entry."""
        pass
    
    @abstractmethod
    def transition_state(self, session_id: str, new_state: SessionState) -> Session:
        """
        Transition session to new state.
        Validates transition is allowed.
        Raises: InvalidStateError if transition not allowed.
        """
        pass
    
    @abstractmethod
    def add_error(self, session_id: str, error: ErrorEntry) -> Session:
        """Add error entry to session."""
        pass
    
    @abstractmethod
    def get_session(self, session_id: str) -> Optional[Session]:
        """Get session by ID."""
        pass
    
    @abstractmethod
    def list_sessions(self, limit: int = 10) -> list[Session]:
        """List recent sessions, newest first."""
        pass
    
    @abstractmethod
    def get_session_path(self, session_id: str) -> Path:
        """Get filesystem path for session folder."""
        pass
```

### SessionStorage

```python
class SessionStorage(ABC):
    @abstractmethod
    def save(self, session: Session) -> None:
        """Persist session state atomically."""
        pass
    
    @abstractmethod
    def load(self, session_id: str) -> Optional[Session]:
        """Load session from storage."""
        pass
    
    @abstractmethod
    def create_folder_structure(self, session_id: str) -> Path:
        """Create session folder with subdirectories."""
        pass
    
    @abstractmethod
    def list_all(self) -> list[str]:
        """List all session IDs."""
        pass
```

## State Transition Validation

| Current State | Allowed Transitions |
|---------------|---------------------|
| COLLECTING | TRANSCRIBING, ERROR |
| TRANSCRIBING | TRANSCRIBED, ERROR |
| TRANSCRIBED | PROCESSING, ERROR |
| PROCESSING | PROCESSED, ERROR |
| PROCESSED | (terminal) |
| ERROR | (terminal) |

## Folder Structure

```text
{sessions_base_dir}/
└── {session_id}/           # e.g., 2025-12-18_14-30-00/
    ├── metadata.json       # Session state (atomic writes)
    ├── audio/              # Downloaded voice messages
    │   ├── 001_audio.ogg
    │   ├── 002_audio.ogg
    │   └── ...
    ├── transcripts/        # Generated text files
    │   ├── 001_audio.txt
    │   ├── 002_audio.txt
    │   └── ...
    └── process/            # Downstream integration
        ├── input.txt       # Consolidated transcripts
        └── output/         # Narrative pipeline results
```

## Configuration

```python
class SessionConfig:
    base_dir: Path = Path("sessions")  # SESSIONS_DIR env var
    max_audio_duration_seconds: int = 1200  # 20 minutes
```

## Errors

| Error | When |
|-------|------|
| `InvalidStateError` | State transition not allowed |
| `SessionNotFoundError` | Session ID does not exist |
| `SessionImmutableError` | Attempt to modify finalized session |

## Events

Session operations emit events for logging/notification:

```python
class SessionEvent:
    event_type: str  # "created" | "finalized" | "audio_added" | "state_changed" | "error"
    session_id: str
    timestamp: datetime
    details: dict
```
