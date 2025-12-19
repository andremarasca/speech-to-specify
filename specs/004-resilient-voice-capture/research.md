# Research: Resilient Voice Capture

**Feature**: 004-resilient-voice-capture  
**Date**: 2025-12-19  
**Purpose**: Resolve all NEEDS CLARIFICATION items and document technology decisions

## Research Tasks Completed

### 1. Session Reopening Architecture

**Context**: How to implement expandable sessions that preserve original audio while allowing new additions?

**Decision**: Event-sourcing model with append-only audio segments

**Rationale**: 
- Sessions are timelines of immutable events (audio segments)
- Reopening creates new segments in the same timeline without modifying existing ones
- State derives from the full event history, ensuring auditability
- Transcription tracks which segments are processed via `processing_status` field

**Alternatives Considered**:
- Copy-on-write sessions: Rejected—violates constitution (copies original audio)
- Session versioning: Rejected—unnecessary complexity; append-only is simpler

### 2. Incremental Audio Persistence

**Context**: How to prevent audio loss during recording, including crash scenarios?

**Decision**: Periodic flush with atomic metadata updates

**Rationale**:
- Audio is written to disk every N seconds (configurable, default: 5s)
- Each segment has checksum computed at write time
- Metadata.json updated atomically via temp file + os.replace
- On crash recovery, system detects incomplete sessions by:
  1. Session state is COLLECTING
  2. Last modified timestamp vs current time gap
  3. Orphan audio files without metadata entries

**Implementation Pattern**:
```python
# Incremental save pattern
1. Write audio chunk to disk: audio/{sequence:03d}_{timestamp}.ogg
2. Compute checksum
3. Update in-memory session.audio_entries
4. Atomic write metadata.json
```

**Alternatives Considered**:
- WAL (Write-Ahead Log): Rejected—overkill for single-user system
- SQLite: Rejected—JSON files more auditable per constitution

### 3. Async Transcription Queue

**Context**: How to handle long-running transcription without blocking UI?

**Decision**: In-process async queue with status tracking

**Rationale**:
- Simple queue using asyncio.Queue or threading.Queue
- TranscriptionWorker processes items in background
- Session metadata tracks transcription status per audio segment
- Progress queryable via `/status` command

**Implementation**:
- Queue items: `(session_id, audio_sequence, audio_path)`
- Worker: Picks item, runs Whisper, updates session metadata atomically
- Failure: Marks segment as FAILED, preserves audio, logs error

**Alternatives Considered**:
- Celery/Redis: Rejected—external dependency overhead for single-user
- Separate process: Rejected—complicates state synchronization

### 4. Semantic Search with Fallback

**Context**: How to ensure search always returns useful results?

**Decision**: Dual-index architecture with graceful fallback

**Rationale**:
- Primary: Semantic search via sentence-transformers embeddings
- Fallback: Full-text search on raw transcripts
- Chronological: Always available as navigation baseline

**Search Flow**:
```
1. Query arrives
2. If embeddings available:
   a. Embed query
   b. Cosine similarity against session embeddings
   c. Return top-K with fragments
3. Else (embeddings unavailable or building):
   a. Simple text search in transcripts
   b. Return matches with surrounding context
4. Always: Offer chronological listing option
```

**Embedding Storage**:
- Per-session embedding stored in `session/embeddings.json`
- Combined session text → single embedding vector
- On session extension: Re-embed entire session (incremental embedding problematic for semantic coherence)

**Alternatives Considered**:
- Per-segment embeddings: Rejected—search should find sessions, not fragments
- External vector DB: Rejected—file-based simpler for single-user

### 5. Help System Architecture

**Context**: How to ensure `/help` is always exhaustive and accurate?

**Decision**: Command registry with auto-generated help

**Rationale**:
- All commands registered in central registry with:
  - Name, description, parameters, examples
- Help text generated from registry at runtime
- Compile-time check ensures all commands are registered
- Adding command without registration = test failure

**Implementation**:
```python
@command_registry.register(
    name="/reopen",
    description="Reopen a previous session to add more audio",
    params={"id": "Session identifier (partial match allowed)"},
    examples=["/reopen yesterday-meeting", "/reopen 2025-12-19"]
)
async def cmd_reopen(ctx: Context, id: str):
    ...
```

**Alternatives Considered**:
- Static help file: Rejected—falls out of sync with code
- Docstring parsing: Rejected—less explicit than registry

### 6. Error Recovery Protocol

**Context**: What happens when things go wrong?

**Decision**: Structured error handling with recovery guidance

| Failure | System Response | User Action |
|---------|-----------------|-------------|
| Recording interrupted | Preserve saved chunks, mark session as INTERRUPTED | `/recover` shows options |
| Transcription fails | Audio preserved, segment marked FAILED | `/retry` re-queues failed |
| Corrupted session | Backup metadata exists, attempt restore | Diagnostic + suggested fix |
| Storage full | Immediate pause + notification | Clear space guidance |
| Embedding fails | Session remains searchable via text | Automatic retry on next finalize |

**Recovery Commands**:
- `/status`: Show system health, pending transcriptions, failed items
- `/recover`: List interrupted sessions with recovery options
- `/retry <session>`: Re-queue failed transcriptions for session

### 7. Existing Code Integration

**Context**: How does this feature integrate with existing 002/003 implementations?

**Decision**: Extension over replacement

| Existing Component | Integration Approach |
|-------------------|---------------------|
| `Session` model | Add `processing_status`, `can_reopen()`, segment tracking |
| `SessionManager` | Add `reopen_session()`, `get_processing_status()` |
| `SessionStorage` | Add crash recovery detection, orphan cleanup |
| `EmbeddingService` | Use as-is for session-level embeddings |
| `WhisperTranscriptionService` | Wrap with queue for async operation |
| `SessionMatcher` | Reuse for `/reopen` session resolution |

**Migration**: No breaking changes to existing functionality. All additions are additive.

## Technology Stack Confirmation

| Component | Choice | Version |
|-----------|--------|---------|
| Language | Python | 3.11+ |
| Audio capture | python-telegram-bot | 22.0+ |
| Transcription | openai-whisper | 20231117+ |
| Embeddings | sentence-transformers | 2.2.0+ (all-MiniLM-L6-v2) |
| Async | asyncio | stdlib |
| Testing | pytest | 8.0+ |
| Config | pydantic-settings | 2.1+ |

## Open Questions Resolved

| Question | Resolution |
|----------|------------|
| Session identification | Timestamp-based ID (existing pattern) + intelligible name |
| Audio format | OGG from Telegram, converted as-needed by Whisper |
| Embedding model size | all-MiniLM-L6-v2 (~90MB) - fits in RAM |
| GPU requirement | Optional - CPU fallback available |
| Concurrent sessions | Single active session per user (existing pattern) |

## Performance Estimates

| Operation | Expected Time |
|-----------|---------------|
| Session start | <100ms |
| Audio segment save | <50ms (5s chunk) |
| Session finalize | <200ms (queue submission) |
| Transcription | ~1x realtime (Whisper small.en on GPU) |
| Embedding generation | <1s per session |
| Semantic search | <200ms (in-memory) |

## Next Steps

→ Phase 1: Generate data-model.md, contracts/, quickstart.md
