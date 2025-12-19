# Data Model: Telegram Voice Orchestrator (OATL)

**Feature Branch**: `002-telegram-voice-orchestrator`  
**Created**: 2025-12-18  
**Purpose**: Define entities, relationships, validation rules, and state transitions

## Entity Diagram

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Session                                         │
│  ═══════════════════════════════════════════════════════════════════════   │
│  id: str (timestamp)           # "2025-12-18_14-30-00"                      │
│  state: SessionState           # COLLECTING | TRANSCRIBING | TRANSCRIBED |   │
│                                # PROCESSING | PROCESSED | ERROR              │
│  created_at: datetime                                                        │
│  finalized_at: datetime | None                                               │
│  chat_id: int                  # Telegram chat for this session             │
│  audio_entries: list[AudioEntry]                                            │
│  errors: list[ErrorEntry]                                                   │
│  ─────────────────────────────────────────────────────────────────────────  │
│  folder_path -> sessions/{id}/                                               │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ 1:N
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            AudioEntry                                        │
│  ═══════════════════════════════════════════════════════════════════════   │
│  sequence: int                 # 1-indexed order                             │
│  received_at: datetime                                                       │
│  telegram_file_id: str         # For re-download if needed                  │
│  local_filename: str           # "001_audio.ogg"                            │
│  file_size_bytes: int                                                       │
│  duration_seconds: float | None                                             │
│  transcription_status: TranscriptionStatus  # PENDING | SUCCESS | FAILED    │
│  transcript_filename: str | None  # "001_audio.txt"                         │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                            ErrorEntry                                        │
│  ═══════════════════════════════════════════════════════════════════════   │
│  timestamp: datetime                                                         │
│  operation: str                # "download" | "transcribe" | "process"       │
│  target: str | None            # File or operation reference                 │
│  message: str                  # Human-readable error                        │
│  recoverable: bool             # Can operation be retried?                   │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Enumerations

### SessionState

```text
COLLECTING    → Session is open, accepting audio messages
TRANSCRIBING  → Finalized, transcription in progress
TRANSCRIBED   → All audios transcribed, ready for downstream
PROCESSING    → Downstream processor running
PROCESSED     → Downstream complete, all artifacts available
ERROR         → Unrecoverable error, session halted
```

### TranscriptionStatus

```text
PENDING   → Audio received, not yet transcribed
SUCCESS   → Transcription completed
FAILED    → Transcription failed (error logged)
```

## State Transitions

```text
                    /start
                       │
                       ▼
               ┌──────────────┐
               │  COLLECTING  │ ◄────────────────┐
               └──────────────┘                  │
                       │                         │
                       │ /finish                 │ /start (auto-finalize)
                       ▼                         │
               ┌──────────────┐                  │
               │ TRANSCRIBING │                  │
               └──────────────┘                  │
                       │                         │
                       │ All audios done         │
                       ▼                         │
               ┌──────────────┐                  │
               │ TRANSCRIBED  │ ─────────────────┘
               └──────────────┘      
                       │
                       │ /process
                       ▼
               ┌──────────────┐
               │  PROCESSING  │
               └──────────────┘
                       │
                       │ Complete
                       ▼
               ┌──────────────┐
               │  PROCESSED   │
               └──────────────┘

Any state → ERROR (on unrecoverable failure)
```

### Transition Rules

| From | To | Trigger | Validation |
|------|----|---------|------------|
| (none) | COLLECTING | `/start` command | No active COLLECTING session |
| COLLECTING | COLLECTING | New session `/start` | Auto-finalize current first |
| COLLECTING | TRANSCRIBING | `/finish` command | At least 1 audio collected |
| TRANSCRIBING | TRANSCRIBED | All audios processed | All transcriptions complete |
| TRANSCRIBED | PROCESSING | `/process` command | State is TRANSCRIBED |
| PROCESSING | PROCESSED | Pipeline completes | Downstream success |
| Any | ERROR | Unrecoverable failure | Logged in errors[] |

## Validation Rules

### Session

- `id` MUST be unique and follow format `YYYY-MM-DD_HH-MM-SS`
- `state` MUST be one of defined SessionState values
- `audio_entries` sequence numbers MUST be contiguous starting from 1
- `finalized_at` MUST be null if state is COLLECTING
- `finalized_at` MUST NOT be null if state is not COLLECTING

### AudioEntry

- `sequence` MUST be positive integer ≥ 1
- `local_filename` MUST match pattern `{sequence:03d}_audio.ogg`
- `transcript_filename` MUST match pattern `{sequence:03d}_audio.txt` when present
- `transcription_status` MUST be PENDING while session is COLLECTING
- File MUST exist at `session_folder/audio/{local_filename}`

### ErrorEntry

- `timestamp` MUST be ISO 8601 format with timezone
- `operation` MUST be one of: "download", "transcribe", "process"
- `message` MUST be non-empty string

## JSON Schema: metadata.json

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["id", "state", "created_at", "chat_id", "audio_entries", "errors"],
  "properties": {
    "id": {
      "type": "string",
      "pattern": "^\\d{4}-\\d{2}-\\d{2}_\\d{2}-\\d{2}-\\d{2}$"
    },
    "state": {
      "type": "string",
      "enum": ["COLLECTING", "TRANSCRIBING", "TRANSCRIBED", "PROCESSING", "PROCESSED", "ERROR"]
    },
    "created_at": {
      "type": "string",
      "format": "date-time"
    },
    "finalized_at": {
      "type": ["string", "null"],
      "format": "date-time"
    },
    "chat_id": {
      "type": "integer"
    },
    "audio_entries": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["sequence", "received_at", "telegram_file_id", "local_filename", "file_size_bytes", "transcription_status"],
        "properties": {
          "sequence": { "type": "integer", "minimum": 1 },
          "received_at": { "type": "string", "format": "date-time" },
          "telegram_file_id": { "type": "string" },
          "local_filename": { "type": "string" },
          "file_size_bytes": { "type": "integer", "minimum": 0 },
          "duration_seconds": { "type": ["number", "null"] },
          "transcription_status": { 
            "type": "string",
            "enum": ["PENDING", "SUCCESS", "FAILED"]
          },
          "transcript_filename": { "type": ["string", "null"] }
        }
      }
    },
    "errors": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["timestamp", "operation", "message", "recoverable"],
        "properties": {
          "timestamp": { "type": "string", "format": "date-time" },
          "operation": { "type": "string", "enum": ["download", "transcribe", "process"] },
          "target": { "type": ["string", "null"] },
          "message": { "type": "string" },
          "recoverable": { "type": "boolean" }
        }
      }
    }
  }
}
```

## Example: metadata.json

```json
{
  "id": "2025-12-18_14-30-00",
  "state": "TRANSCRIBED",
  "created_at": "2025-12-18T14:30:00.000Z",
  "finalized_at": "2025-12-18T14:45:30.000Z",
  "chat_id": 123456789,
  "audio_entries": [
    {
      "sequence": 1,
      "received_at": "2025-12-18T14:31:15.000Z",
      "telegram_file_id": "AgACAgIAAxkBAAI...",
      "local_filename": "001_audio.ogg",
      "file_size_bytes": 245760,
      "duration_seconds": 62.5,
      "transcription_status": "SUCCESS",
      "transcript_filename": "001_audio.txt"
    },
    {
      "sequence": 2,
      "received_at": "2025-12-18T14:35:42.000Z",
      "telegram_file_id": "AgACAgIAAxkBAAJ...",
      "local_filename": "002_audio.ogg",
      "file_size_bytes": 189440,
      "duration_seconds": 48.2,
      "transcription_status": "SUCCESS",
      "transcript_filename": "002_audio.txt"
    }
  ],
  "errors": []
}
```

## Pydantic Models (Implementation Reference)

```python
from enum import Enum
from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional

class SessionState(str, Enum):
    COLLECTING = "COLLECTING"
    TRANSCRIBING = "TRANSCRIBING"
    TRANSCRIBED = "TRANSCRIBED"
    PROCESSING = "PROCESSING"
    PROCESSED = "PROCESSED"
    ERROR = "ERROR"

class TranscriptionStatus(str, Enum):
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"

class AudioEntry(BaseModel):
    sequence: int = Field(ge=1)
    received_at: datetime
    telegram_file_id: str
    local_filename: str
    file_size_bytes: int = Field(ge=0)
    duration_seconds: Optional[float] = None
    transcription_status: TranscriptionStatus = TranscriptionStatus.PENDING
    transcript_filename: Optional[str] = None

class ErrorEntry(BaseModel):
    timestamp: datetime
    operation: str  # "download" | "transcribe" | "process"
    target: Optional[str] = None
    message: str
    recoverable: bool

class Session(BaseModel):
    id: str  # "YYYY-MM-DD_HH-MM-SS"
    state: SessionState
    created_at: datetime
    finalized_at: Optional[datetime] = None
    chat_id: int
    audio_entries: list[AudioEntry] = Field(default_factory=list)
    errors: list[ErrorEntry] = Field(default_factory=list)
```
