# Data Model: Resilient Voice Capture

**Feature**: 004-resilient-voice-capture  
**Date**: 2025-12-19  
**Source**: [spec.md](spec.md) Key Entities + [research.md](research.md) decisions

## Entity Relationship Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                           Session                                │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ id: str (unique, timestamp-based)                           ││
│  │ chat_id: int                                                 ││
│  │ state: SessionState                                          ││
│  │ created_at: datetime                                         ││
│  │ finalized_at: datetime | None                                ││
│  │ intelligible_name: str                                       ││
│  │ name_source: NameSource                                      ││
│  │ processing_status: ProcessingStatus (NEW)                    ││
│  │ reopen_count: int (NEW)                                      ││
│  │ embedding_vector: list[float] | None (NEW)                   ││
│  └─────────────────────────────────────────────────────────────┘│
│                              │                                   │
│                              │ 1:N                               │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                      AudioSegment                            ││
│  │  ┌───────────────────────────────────────────────────────┐  ││
│  │  │ sequence: int (1-indexed within session)              │  ││
│  │  │ received_at: datetime                                  │  ││
│  │  │ local_filename: str                                    │  ││
│  │  │ file_size_bytes: int                                   │  ││
│  │  │ duration_seconds: float | None                         │  ││
│  │  │ checksum: str (SHA-256) (NEW)                         │  ││
│  │  │ transcription_status: TranscriptionStatus             │  ││
│  │  │ transcript_filename: str | None                        │  ││
│  │  │ reopen_epoch: int (NEW - which open cycle added this) │  ││
│  │  └───────────────────────────────────────────────────────┘  ││
│  └─────────────────────────────────────────────────────────────┘│
│                              │                                   │
│                              │ 1:1                               │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                       Transcript                             ││
│  │  ┌───────────────────────────────────────────────────────┐  ││
│  │  │ audio_sequence: int (links to AudioSegment)           │  ││
│  │  │ text: str                                              │  ││
│  │  │ language: str                                          │  ││
│  │  │ confidence: float | None                               │  ││
│  │  │ created_at: datetime                                   │  ││
│  │  └───────────────────────────────────────────────────────┘  ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                        SearchResult                              │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ session_id: str                                              ││
│  │ session_name: str                                            ││
│  │ relevance_score: float (0.0 - 1.0)                          ││
│  │ match_type: MatchType (SEMANTIC | TEXT | CHRONOLOGICAL)     ││
│  │ preview_fragments: list[str]                                 ││
│  │ session_created_at: datetime                                 ││
│  │ total_audio_duration: float                                  ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

## Enumerations

### SessionState (extended)

```python
class SessionState(str, Enum):
    # Active states
    COLLECTING = "COLLECTING"      # Accepting audio
    
    # Processing states
    TRANSCRIBING = "TRANSCRIBING"  # Transcription in progress
    TRANSCRIBED = "TRANSCRIBED"    # All audio transcribed
    EMBEDDING = "EMBEDDING"        # Generating embeddings (NEW)
    
    # Terminal states
    READY = "READY"                # Fully processed, searchable (NEW)
    ERROR = "ERROR"                # Unrecoverable error
    
    # Recovery states
    INTERRUPTED = "INTERRUPTED"    # Crash recovery needed (NEW)
```

### ProcessingStatus (NEW)

```python
class ProcessingStatus(str, Enum):
    """Overall processing status for session."""
    PENDING = "PENDING"           # Audio collected, not processed
    TRANSCRIPTION_QUEUED = "TRANSCRIPTION_QUEUED"
    TRANSCRIPTION_IN_PROGRESS = "TRANSCRIPTION_IN_PROGRESS"
    TRANSCRIPTION_COMPLETE = "TRANSCRIPTION_COMPLETE"
    EMBEDDING_QUEUED = "EMBEDDING_QUEUED"
    EMBEDDING_IN_PROGRESS = "EMBEDDING_IN_PROGRESS"
    COMPLETE = "COMPLETE"         # All processing done
    PARTIAL_FAILURE = "PARTIAL_FAILURE"  # Some segments failed
```

### TranscriptionStatus (existing)

```python
class TranscriptionStatus(str, Enum):
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
```

### MatchType (extended)

```python
class MatchType(str, Enum):
    SEMANTIC = "SEMANTIC"           # Embedding similarity (NEW)
    TEXT = "TEXT"                   # Substring/keyword match (NEW)
    CHRONOLOGICAL = "CHRONOLOGICAL" # Date-based listing (NEW)
    EXACT_SUBSTRING = "EXACT_SUBSTRING"  # Existing
    FUZZY_SUBSTRING = "FUZZY_SUBSTRING"  # Existing
    SEMANTIC_SIMILARITY = "SEMANTIC_SIMILARITY"  # Existing (alias for SEMANTIC)
```

## State Transitions

### Session Lifecycle

```
                    ┌──────────────────────────────────────┐
                    │                                      │
    ┌───────────────▼───────────────┐                      │
    │         COLLECTING            │◄─────────────────────┤ /reopen
    └───────────────┬───────────────┘                      │
                    │ /close                               │
                    ▼                                      │
    ┌───────────────────────────────┐                      │
    │        TRANSCRIBING           │                      │
    └───────────────┬───────────────┘                      │
                    │ all segments done                    │
                    ▼                                      │
    ┌───────────────────────────────┐                      │
    │        TRANSCRIBED            │                      │
    └───────────────┬───────────────┘                      │
                    │ auto                                 │
                    ▼                                      │
    ┌───────────────────────────────┐                      │
    │         EMBEDDING             │                      │
    └───────────────┬───────────────┘                      │
                    │ embedding complete                   │
                    ▼                                      │
    ┌───────────────────────────────┐                      │
    │           READY               │──────────────────────┘
    └───────────────────────────────┘
                    
    Any state ──────► ERROR (on unrecoverable failure)
    
    COLLECTING ────► INTERRUPTED (on crash detection)
    INTERRUPTED ───► COLLECTING (on /recover)
```

### Valid Transitions

| From | To | Trigger |
|------|----|---------|
| (none) | COLLECTING | Session creation |
| COLLECTING | TRANSCRIBING | `/close` command |
| COLLECTING | INTERRUPTED | Crash detected on restart |
| TRANSCRIBING | TRANSCRIBED | All segments transcribed |
| TRANSCRIBING | ERROR | Unrecoverable transcription failure |
| TRANSCRIBED | EMBEDDING | Auto after transcription |
| EMBEDDING | READY | Embedding complete |
| EMBEDDING | READY | Embedding failed (fallback to text search) |
| READY | COLLECTING | `/reopen` command |
| INTERRUPTED | COLLECTING | `/recover` command |
| Any | ERROR | Unrecoverable failure |

## Filesystem Layout

```
sessions/
└── {session_id}/
    ├── metadata.json          # Session state + audio entries
    ├── embeddings.json        # Session embedding vector (NEW)
    ├── audio/
    │   ├── 001_{timestamp}.ogg
    │   ├── 002_{timestamp}.ogg
    │   └── ...
    └── transcripts/
        ├── 001_{timestamp}.txt
        ├── 002_{timestamp}.txt
        └── combined.txt       # All transcripts concatenated (NEW)
```

### metadata.json Structure

```json
{
  "id": "2025-12-19_14-30-00",
  "chat_id": 123456789,
  "state": "READY",
  "created_at": "2025-12-19T14:30:00.000000+00:00",
  "finalized_at": "2025-12-19T15:00:00.000000+00:00",
  "intelligible_name": "project-brainstorm",
  "name_source": "TRANSCRIPTION",
  "processing_status": "COMPLETE",
  "reopen_count": 1,
  "audio_entries": [
    {
      "sequence": 1,
      "received_at": "2025-12-19T14:30:15.000000+00:00",
      "local_filename": "001_14-30-15.ogg",
      "file_size_bytes": 24576,
      "duration_seconds": 12.5,
      "checksum": "sha256:abc123...",
      "transcription_status": "SUCCESS",
      "transcript_filename": "001_14-30-15.txt",
      "reopen_epoch": 0
    },
    {
      "sequence": 2,
      "received_at": "2025-12-19T16:00:05.000000+00:00",
      "local_filename": "002_16-00-05.ogg",
      "file_size_bytes": 18432,
      "duration_seconds": 8.2,
      "checksum": "sha256:def456...",
      "transcription_status": "SUCCESS",
      "transcript_filename": "002_16-00-05.txt",
      "reopen_epoch": 1
    }
  ],
  "errors": []
}
```

### embeddings.json Structure

```json
{
  "session_id": "2025-12-19_14-30-00",
  "model": "all-MiniLM-L6-v2",
  "dimension": 384,
  "vector": [0.123, -0.456, ...],
  "source_text_hash": "sha256:...",
  "created_at": "2025-12-19T15:01:00.000000+00:00"
}
```

## Validation Rules

### Session

| Field | Rule |
|-------|------|
| id | Non-empty, matches timestamp pattern `YYYY-MM-DD_HH-MM-SS` |
| state | Valid SessionState enum value |
| reopen_count | >= 0, increments on each reopen |
| finalized_at | Must be set when state leaves COLLECTING |

### AudioSegment

| Field | Rule |
|-------|------|
| sequence | Positive integer, unique within session, sequential |
| checksum | SHA-256 hash matching file content |
| reopen_epoch | 0 for original session, increments on each reopen |
| local_filename | Must exist in session's audio/ directory |

### SearchResult

| Field | Rule |
|-------|------|
| relevance_score | In range [0.0, 1.0] |
| preview_fragments | Non-empty when match found |

## Invariants

1. **Audio Immutability**: Once an AudioSegment is created, its `local_filename`, `checksum`, and `received_at` MUST NOT change
2. **Append-Only**: Reopening a session MUST only add new AudioSegments; existing segments are read-only
3. **Checksum Integrity**: File content MUST match stored checksum; mismatch indicates corruption
4. **Sequential Ordering**: AudioSegments within a session MUST have sequential, gapless sequence numbers
5. **Epoch Consistency**: All segments added in same reopen cycle share the same `reopen_epoch`
6. **State Consistency**: Session state MUST reflect actual processing status of audio segments
