# Data Model: Telegram UX Overhaul

**Feature**: 005-telegram-ux-overhaul  
**Date**: 2025-12-19  
**Depends On**: [Session model](../../src/models/session.py)

## Overview

This feature introduces UI-specific entities that extend the existing session model without modifying core business logic. All new entities are presentation-layer concerns, maintaining the separation between channel (Telegram) and processing core.

---

## New Entities

### UIPreferences

User interface preferences stored per-session. Minimal footprint for MVP.

```
UIPreferences
├── simplified_ui: bool           # Default: false
│   └── When true: no decorative emojis, explicit text descriptions
└── (future: language, notification_sound, etc.)
```

**Validation Rules**:
- `simplified_ui` defaults to `false` for new sessions
- Preference persisted in session JSON, survives bot restart

**Storage**: Embedded in Session.metadata or dedicated field

---

### UIState

Transient state for managing Telegram message interactions within a session.

```
UIState
├── status_message_id: Optional[int]    # ID of pinned status message for editing
├── last_keyboard_type: KeyboardType    # Current keyboard being displayed
├── pending_confirmation: Optional[ConfirmationContext]
│   └── For session conflict dialogs
└── progress_message_id: Optional[int]  # ID of progress message being updated
```

**Lifecycle**:
- Created when session becomes active
- Updated on each user interaction
- Cleared when session finalizes or user navigates away

**Note**: Transient - not persisted to disk. Reconstructable from session state.

---

### ProgressState

State for tracking and displaying operation progress.

```
ProgressState
├── operation_id: str              # Unique ID for this operation
├── operation_type: OperationType  # TRANSCRIPTION, EMBEDDING, PROCESSING
├── current_step: int              # Current step number
├── total_steps: int               # Total steps in operation
├── step_description: str          # Human-readable current action
├── started_at: datetime           # For timeout detection
├── estimated_completion: Optional[datetime]  # ETA based on heuristics
└── last_update_at: datetime       # For throttling UI updates
```

**Validation Rules**:
- `current_step` must be >= 0 and <= `total_steps`
- `estimated_completion` calculated from average processing time per audio minute
- Updates throttled to minimum 5-second intervals (configurable)

**State Transitions**:
```
[Created] → ACTIVE → COMPLETED
                  ↘ TIMEOUT (if exceeds threshold)
                  ↘ CANCELLED (user action)
                  ↘ ERROR
```

---

### UserFacingError

Structured error for humanized presentation.

```
UserFacingError
├── error_code: str               # e.g., "ERR_STORAGE_001"
├── message: str                  # User-friendly description
├── suggestions: list[str]        # Actionable recovery hints
├── recovery_actions: list[RecoveryAction]
│   └── RecoveryAction
│       ├── label: str            # Button text
│       └── callback_data: str    # Action identifier
└── severity: ErrorSeverity       # INFO, WARNING, ERROR, CRITICAL
```

**Error Code Format**: `ERR_{DOMAIN}_{NUMBER}`
- Domains: STORAGE, NETWORK, TRANSCRIPTION, SESSION, TELEGRAM, CONFIG
- Numbers: 001-999 per domain

---

### ConfirmationContext

Context for confirmation dialogs (session conflicts, destructive actions).

```
ConfirmationContext
├── confirmation_type: ConfirmationType
│   └── SESSION_CONFLICT, CANCEL_OPERATION, DISCARD_SESSION
├── context_data: dict            # Type-specific context
│   └── For SESSION_CONFLICT: {session_id, audio_count, created_at}
├── options: list[ConfirmationOption]
│   └── ConfirmationOption
│       ├── label: str
│       ├── callback_data: str
│       └── is_destructive: bool
└── expires_at: Optional[datetime]  # Auto-dismiss after timeout
```

---

### KeyboardType (Enum)

Types of inline keyboards displayed to user.

```
KeyboardType
├── SESSION_ACTIVE      # Finalize, Status, Help
├── SESSION_EMPTY       # Start Recording hint, Help
├── PROCESSING          # Cancel only
├── RESULTS             # View Full, Search, Start Pipeline
├── CONFIRMATION        # Dynamic based on ConfirmationContext
├── ERROR_RECOVERY      # Retry, Cancel, Help
├── PAGINATION          # Previous, Next, Close
└── HELP_CONTEXT        # Back, related actions
```

---

### OperationType (Enum)

Types of long-running operations for progress tracking.

```
OperationType
├── TRANSCRIPTION       # Audio → text via Whisper
├── EMBEDDING           # Text → vector via sentence-transformers
├── PROCESSING          # Full artifact pipeline
└── SEARCH              # Semantic search (usually fast, no progress needed)
```

---

## Extended Entities

### Session (Extension)

Add UI-related fields to existing Session model:

```
Session
├── ... (existing fields unchanged) ...
└── ui_preferences: UIPreferences   # NEW - Optional, defaults to UIPreferences()
```

**Migration**: Existing sessions without `ui_preferences` use default values.

**Note**: `UIState` is NOT persisted in Session - it's transient runtime state managed by UIService.

---

## Entity Relationships

```
┌─────────────────────────────────────────────────────────────────┐
│                        Presentation Layer                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   UIService                                                      │
│   ├── manages → UIState (transient, per-session)                │
│   ├── creates → InlineKeyboardMarkup (per KeyboardType)         │
│   └── reads ← UIPreferences (from Session)                      │
│                                                                  │
│   ProgressReporter                                               │
│   ├── manages → ProgressState                                   │
│   └── calls → UIService.update_progress_message()               │
│                                                                  │
│   ErrorPresentationLayer                                         │
│   ├── maps → Exception → UserFacingError                        │
│   └── calls → UIService.send_error_message()                    │
│                                                                  │
├─────────────────────────────────────────────────────────────────┤
│                          Core Layer (UNCHANGED)                  │
├─────────────────────────────────────────────────────────────────┤
│   Session ←──extends── UIPreferences (persisted)                │
│   SessionManager (no changes)                                    │
│   TranscriptionService (no changes)                              │
└─────────────────────────────────────────────────────────────────┘
```

---

## JSON Schema Examples

### UIPreferences (embedded in session JSON)

```json
{
  "ui_preferences": {
    "simplified_ui": false
  }
}
```

### ProgressState (runtime, not persisted)

```json
{
  "operation_id": "tx_2025-12-19_15-30-00",
  "operation_type": "TRANSCRIPTION",
  "current_step": 2,
  "total_steps": 5,
  "step_description": "Transcrevendo áudio 2 de 5...",
  "started_at": "2025-12-19T15:30:00Z",
  "estimated_completion": "2025-12-19T15:32:30Z",
  "last_update_at": "2025-12-19T15:30:45Z"
}
```

### UserFacingError (error catalog entry)

```json
{
  "error_code": "ERR_STORAGE_001",
  "message": "Não foi possível salvar o áudio no momento.",
  "suggestions": [
    "Verifique se há espaço livre no dispositivo.",
    "Tente novamente em alguns instantes."
  ],
  "recovery_actions": [
    {"label": "Tentar novamente", "callback_data": "retry:save_audio"},
    {"label": "Cancelar", "callback_data": "action:cancel"}
  ],
  "severity": "ERROR"
}
```

---

## Validation Summary

| Entity | Persisted | Location | Backward Compatible |
|--------|-----------|----------|---------------------|
| UIPreferences | Yes | Session JSON | Yes (optional field) |
| UIState | No | Runtime memory | N/A |
| ProgressState | No | Runtime memory | N/A |
| UserFacingError | Yes | Error catalog (config) | N/A (new) |
| ConfirmationContext | No | Runtime memory | N/A |

---

## Notes

- All new entities follow existing dataclass patterns with Pydantic validation where needed
- No changes to core Session state machine or business logic
- Error catalog externalized per Constitution Principle V
