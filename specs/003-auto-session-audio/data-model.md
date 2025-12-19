# Data Model: Auto-Session Audio Capture

**Feature**: 003-auto-session-audio  
**Date**: 2025-12-18  
**Based on**: [research.md](research.md)

## Entity Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                          Session                                 │
│  (Container for user work context)                              │
├─────────────────────────────────────────────────────────────────┤
│  id: str                    # Timestamp-based unique ID         │
│  intelligible_name: str     # Human-readable name (NEW)         │
│  name_source: NameSource    # Origin of the name (NEW)          │
│  embedding: list[float]?    # Semantic vector (NEW, optional)   │
│  state: SessionState        # Lifecycle state                   │
│  created_at: datetime       # Creation timestamp                │
│  chat_id: int               # Telegram chat ID                  │
│  audio_entries: list[AudioEntry]                                │
│  errors: list[ErrorEntry]                                       │
└─────────────────────────────────────────────────────────────────┘
           │
           │ contains
           ▼
┌─────────────────────────────────────────────────────────────────┐
│                        AudioEntry                                │
│  (Raw audio input from user)                                    │
├─────────────────────────────────────────────────────────────────┤
│  sequence: int              # 1-indexed order of receipt        │
│  received_at: datetime      # When audio was received           │
│  telegram_file_id: str      # For re-download if needed         │
│  local_filename: str        # Path in session/audio/            │
│  file_size_bytes: int                                           │
│  duration_seconds: float?                                       │
│  transcription_status: TranscriptionStatus                      │
│  transcript_filename: str?                                      │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                     SessionReference                             │
│  (User's natural language attempt to identify a session) (NEW)  │
├─────────────────────────────────────────────────────────────────┤
│  original_text: str         # What user typed/said              │
│  resolved_session_id: str?  # Matched session (if any)          │
│  confidence: float          # Match confidence [0.0, 1.0]       │
│  match_type: MatchType      # How the match was found           │
│  candidates: list[str]      # Alternative session IDs (if amb.) │
└─────────────────────────────────────────────────────────────────┘
```

## New Enumerations

### NameSource

Tracks the origin of a session's intelligible name for auditability.

```python
class NameSource(str, Enum):
    """Source of session's intelligible_name."""
    
    FALLBACK_TIMESTAMP = "FALLBACK_TIMESTAMP"  # Auto-generated from creation time
    TRANSCRIPTION = "TRANSCRIPTION"            # Extracted from first transcription
    LLM_TITLE = "LLM_TITLE"                    # Extracted by LLM processing
    USER_ASSIGNED = "USER_ASSIGNED"            # Explicitly named by user
```

**Transition rules**:
- `FALLBACK_TIMESTAMP` → `TRANSCRIPTION` (on first transcription complete)
- `TRANSCRIPTION` → `LLM_TITLE` (on LLM title extraction)
- Any → `USER_ASSIGNED` (on explicit user rename command)

### MatchType

Describes how a session reference was resolved.

```python
class MatchType(str, Enum):
    """How a session reference was matched."""
    
    EXACT_SUBSTRING = "EXACT_SUBSTRING"        # Name contains reference exactly
    FUZZY_SUBSTRING = "FUZZY_SUBSTRING"        # Name contains reference with edits
    SEMANTIC_SIMILARITY = "SEMANTIC_SIMILARITY"  # Embedding similarity match
    ACTIVE_CONTEXT = "ACTIVE_CONTEXT"          # Implicit (no reference, used active)
    AMBIGUOUS = "AMBIGUOUS"                    # Multiple candidates, needs clarification
    NOT_FOUND = "NOT_FOUND"                    # No match found
```

## Session Model Extensions

### New Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `intelligible_name` | `str` | Yes | Generated | Human-readable session name |
| `name_source` | `NameSource` | Yes | `FALLBACK_TIMESTAMP` | Origin of the name |
| `embedding` | `list[float]` | No | `None` | 384-dim vector for semantic matching |

### Validation Rules

1. **intelligible_name**:
   - Must be non-empty after stripping whitespace
   - Maximum 100 characters
   - Must be unique within active sessions (uniqueness enforced by suffix)

2. **embedding**:
   - If present, must be exactly 384 floats (all-MiniLM-L6-v2 dimension)
   - Values must be in range [-1.0, 1.0]

### Name Generation Rules

```python
def generate_fallback_name(created_at: datetime) -> str:
    """Generate Portuguese locale timestamp name."""
    # "Áudio de 18 de Dezembro"
    day = created_at.day
    month_names = [
        "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
        "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"
    ]
    month = month_names[created_at.month - 1]
    return f"Áudio de {day} de {month}"

def generate_transcription_name(transcript: str) -> str:
    """Extract first meaningful words from transcript."""
    # Remove filler words, take first 5 words, truncate at 50 chars
    filler_words = {"um", "uma", "o", "a", "é", "eh", "então", "tipo", "né"}
    words = transcript.split()
    meaningful = [w for w in words if w.lower() not in filler_words]
    name = " ".join(meaningful[:5])
    return name[:50].strip()
```

### Uniqueness Enforcement

When a name collision occurs:
```python
def ensure_unique_name(base_name: str, existing_names: set[str]) -> str:
    """Add suffix to ensure uniqueness."""
    if base_name not in existing_names:
        return base_name
    
    counter = 2
    while f"{base_name} ({counter})" in existing_names:
        counter += 1
    
    return f"{base_name} ({counter})"
```

## SessionReference Model

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `original_text` | `str` | Yes | User's reference text |
| `resolved_session_id` | `str` | No | Matched session ID |
| `confidence` | `float` | Yes | Match confidence [0.0, 1.0] |
| `match_type` | `MatchType` | Yes | How match was determined |
| `candidates` | `list[str]` | No | Alternative session IDs if ambiguous |

### Resolution Algorithm

```
Input: reference_text, session_index
Output: SessionReference

1. IF reference_text is empty:
   - Check for active session
   - IF active exists: return (active.id, 1.0, ACTIVE_CONTEXT)
   - ELSE: return (None, 0.0, NOT_FOUND)

2. Exact substring search:
   - FOR each session in index:
     - IF session.intelligible_name contains reference_text (case-insensitive):
       - Add to exact_matches

3. IF len(exact_matches) == 1:
   - return (match.id, 1.0, EXACT_SUBSTRING)

4. IF len(exact_matches) > 1:
   - return (None, 0.9, AMBIGUOUS, candidates=exact_matches)

5. Fuzzy substring search:
   - FOR each session in index:
     - IF levenshtein(session.intelligible_name, reference_text) <= 2:
       - Add to fuzzy_matches

6. IF len(fuzzy_matches) == 1:
   - return (match.id, 0.9, FUZZY_SUBSTRING)

7. Semantic similarity search:
   - reference_embedding = embed(reference_text)
   - FOR each session with embedding:
     - similarity = cosine(session.embedding, reference_embedding)
     - IF similarity > 0.7: Add to semantic_matches

8. IF len(semantic_matches) >= 1:
   - Sort by similarity descending
   - IF top similarity > 0.85 AND gap to second > 0.15:
     - return (best.id, similarity, SEMANTIC_SIMILARITY)
   - ELSE:
     - return (None, best_sim, AMBIGUOUS, candidates=top_3)

9. return (None, 0.0, NOT_FOUND)
```

## State Transitions

### Session State Machine (Updated)

```
                    ┌──────────────┐
    Audio received  │              │
    (no session)    │  [created]   │
         ──────────►│  COLLECTING  │◄──────────────────────────────────┐
                    │              │                                    │
                    └──────┬───────┘                                    │
                           │                                            │
                           │ /done or /finish                           │
                           ▼                                            │
                    ┌──────────────┐                                    │
                    │              │                                    │
                    │ TRANSCRIBING │                                    │
                    │              │                                    │
                    └──────┬───────┘                                    │
                           │                                            │
                           │ All transcriptions complete                │
                           │ ► Update intelligible_name                 │
                           ▼                                            │
                    ┌──────────────┐                                    │
                    │              │                                    │
                    │ TRANSCRIBED  │                                    │
                    │              │                                    │
                    └──────┬───────┘                                    │
                           │                                            │
                           │ /process                                   │
                           │ ► May update name from LLM title           │
                           ▼                                            │
                    ┌──────────────┐      New session                   │
                    │              │      auto-created                  │
                    │  PROCESSING  │──────────────────────────────────┘
                    │              │
                    └──────┬───────┘
                           │
                           │ Processing complete
                           ▼
                    ┌──────────────┐
                    │              │
                    │  PROCESSED   │ (Terminal)
                    │              │
                    └──────────────┘

    Any State ─────► ERROR (Terminal, on unrecoverable failure)
```

### Name Update Events

| Event | Condition | Name Update |
|-------|-----------|-------------|
| Session created | Always | Set fallback timestamp name |
| First transcription complete | `name_source == FALLBACK_TIMESTAMP` | Update from transcript |
| LLM processing complete | Title extracted AND `name_source != USER_ASSIGNED` | Update from LLM title |
| User rename command | Always | Update to user value |

## Storage Schema

### Session JSON (Updated)

```json
{
  "id": "2025-12-18_22-30-28",
  "intelligible_name": "Áudio de 18 de Dezembro",
  "name_source": "FALLBACK_TIMESTAMP",
  "embedding": null,
  "state": "COLLECTING",
  "created_at": "2025-12-18T22:30:28.123456+00:00",
  "chat_id": 123456789,
  "audio_entries": [],
  "errors": []
}
```

### Session Index File (New)

For efficient matching, maintain an index file:

```json
// sessions/_index.json
{
  "sessions": [
    {
      "id": "2025-12-18_22-30-28",
      "intelligible_name": "relatório mensal de dezembro",
      "state": "PROCESSED",
      "created_at": "2025-12-18T22:30:28.123456+00:00"
    }
  ],
  "last_updated": "2025-12-18T23:00:00.000000+00:00"
}
```

The index is rebuilt on startup and updated on session changes.
