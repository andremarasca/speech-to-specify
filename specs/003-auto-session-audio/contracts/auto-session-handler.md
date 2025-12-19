# Contract: Auto-Session Handler

**Module**: `src/services/session/manager.py` (extension)  
**Feature**: 003-auto-session-audio

## Purpose

Handle audio receipt when no active session exists by automatically creating a new session. This extension to `SessionManager` ensures zero data loss by treating every audio message as a "founding event" that creates its own context.

## Interface Extension

```python
from typing import Optional
from src.models.session import Session, AudioEntry


class SessionManager:
    """Extended session manager with auto-creation support."""

    # Existing methods preserved...

    def handle_audio_receipt(
        self,
        chat_id: int,
        audio_data: bytes,
        telegram_file_id: str,
        duration_seconds: Optional[float] = None
    ) -> tuple[Session, AudioEntry]:
        """
        Handle incoming audio with automatic session creation.
        
        Flow:
        1. Persist audio to temp location (guaranteed durable)
        2. Check for active session
        3. If no active session: create one with fallback name
        4. Move audio to session folder
        5. Create and link AudioEntry
        6. Return session and audio entry
        
        This method NEVER discards audio. If session creation fails,
        the audio remains in temp storage for manual recovery.
        
        Args:
            chat_id: Telegram chat ID
            audio_data: Raw audio bytes
            telegram_file_id: Telegram file ID for re-download
            duration_seconds: Audio duration if known
            
        Returns:
            Tuple of (session, audio_entry) - session may be newly created
            
        Raises:
            AudioPersistenceError: If audio cannot be saved (critical)
        """
        pass

    def get_or_create_session(self, chat_id: int) -> tuple[Session, bool]:
        """
        Get active session or create new one.
        
        Args:
            chat_id: Telegram chat ID
            
        Returns:
            Tuple of (session, was_created)
        """
        pass

    def update_session_name(
        self,
        session_id: str,
        new_name: str,
        source: NameSource
    ) -> Session:
        """
        Update session's intelligible name.
        
        Only updates if:
        - source priority > current source priority
        - OR source == USER_ASSIGNED (always wins)
        
        Priority: FALLBACK < TRANSCRIPTION < LLM_TITLE < USER_ASSIGNED
        
        Args:
            session_id: Session to update
            new_name: New intelligible name
            source: Origin of the new name
            
        Returns:
            Updated session
            
        Raises:
            SessionStorageError: If session not found
        """
        pass
```

## Behavior Specification

### Audio Receipt Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    handle_audio_receipt()                        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │ Save audio to   │
                    │ temp location   │
                    │ (MUST succeed)  │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │ Get active      │
                    │ session         │
                    └────────┬────────┘
                             │
              ┌──────────────┴──────────────┐
              │                             │
              ▼                             ▼
     Active exists?               No active session
              │                             │
              │                             ▼
              │                   ┌─────────────────┐
              │                   │ Create session  │
              │                   │ with fallback   │
              │                   │ name            │
              │                   └────────┬────────┘
              │                            │
              └──────────────┬─────────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │ Move audio to   │
                    │ session/audio/  │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │ Create          │
                    │ AudioEntry      │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │ Link to session │
                    │ & persist       │
                    └────────┬────────┘
                             │
                             ▼
                     Return (session, entry)
```

### Name Update Priority

| Current Source | New Source | Update? |
|---------------|------------|---------|
| `FALLBACK_TIMESTAMP` | `TRANSCRIPTION` | ✅ Yes |
| `FALLBACK_TIMESTAMP` | `LLM_TITLE` | ✅ Yes |
| `FALLBACK_TIMESTAMP` | `USER_ASSIGNED` | ✅ Yes |
| `TRANSCRIPTION` | `TRANSCRIPTION` | ❌ No (same) |
| `TRANSCRIPTION` | `LLM_TITLE` | ✅ Yes |
| `TRANSCRIPTION` | `USER_ASSIGNED` | ✅ Yes |
| `LLM_TITLE` | `TRANSCRIPTION` | ❌ No (lower) |
| `LLM_TITLE` | `USER_ASSIGNED` | ✅ Yes |
| `USER_ASSIGNED` | any | ❌ No (user wins) |

## Error Handling

### Critical Errors (Raise Exception)

- **AudioPersistenceError**: Audio cannot be saved to temp or session folder
  - This is the only critical error
  - User is notified immediately
  - Telegram message should be retried

### Recoverable Scenarios

| Scenario | Behavior |
|----------|----------|
| Session creation fails after audio saved | Audio remains in temp, log error, return error to user |
| Name generation fails | Use fallback timestamp name |
| Embedding computation fails | Continue without embedding, log warning |

## Testing Requirements

### Contract Tests

```python
def test_audio_receipt_creates_session_when_none():
    """Audio with no active session creates new session."""

def test_audio_receipt_uses_active_session():
    """Audio with active session adds to that session."""

def test_audio_persisted_before_session_creation():
    """Audio is durable before session operation."""

def test_session_created_with_fallback_name():
    """New session has fallback timestamp name."""

def test_name_update_respects_priority():
    """Higher priority source overwrites lower."""

def test_user_assigned_name_never_overwritten():
    """USER_ASSIGNED name is final."""
```

### Integration Tests

```python
def test_end_to_end_auto_session():
    """Full flow: send audio, session created, name assigned."""

def test_failure_recovery():
    """Audio survives session creation failure."""
```
