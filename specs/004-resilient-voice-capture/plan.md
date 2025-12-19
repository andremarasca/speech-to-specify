# Implementation Plan: Resilient Voice Capture

**Branch**: `004-resilient-voice-capture` | **Date**: 2025-12-19 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/004-resilient-voice-capture/spec.md`

## Summary

This feature implements a resilient voice capture system that preserves cognitive flow through session-based audio recording with semantic search capabilities. The architecture centers on immutable audio artifacts with two-layer persistence: raw audio files as inviolable source data, and derived metadata/transcripts as reconstructable derivatives. The system enables session reopening with incremental audio appending, background transcription processing, and semantic search across all transcribed content using local embeddings.

**Primary approach from research**: Event-sourcing model where sessions are expandable timelines of audio events; atomic write operations via temp file + os.replace pattern; local-only processing with sentence-transformers embeddings; graceful degradation to text search when embeddings unavailable.

## Technical Context

**Language/Version**: Python 3.11+  
**Primary Dependencies**: python-telegram-bot, openai-whisper, torch/torchaudio, sentence-transformers, pydantic, httpx  
**Storage**: Filesystem-based with atomic JSON metadata (temp file + os.replace pattern)  
**Testing**: pytest with contract tests, integration tests, and unit tests  
**Target Platform**: Windows/Linux desktop with CUDA GPU (optional, falls back to CPU)  
**Project Type**: Single project (CLI + Telegram bot interface)  
**Performance Goals**: <500ms feedback latency; background transcription; incremental embedding index updates  
**Constraints**: Local-only processing; zero data loss on crash; offline-capable core capture  
**Scale/Scope**: Single user; thousands of sessions; hours of audio per session

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Addressed By |
|-----------|--------------|
| ✅ Determinism and replayability | Explicit state machine with defined transitions; no timing-based decisions; all audio has checksum |
| ✅ Auditability | JSON metadata files human-readable; all state changes logged; error entries tracked in session |
| ✅ Clear boundaries | Separation: AudioCapture → Storage → Transcription → Embedding → Search (contracts defined) |
| ✅ Human-in-the-loop safety | Session finalization requires explicit command; recovery prompts for interrupted sessions |
| ✅ Validation and test coverage | Contract tests for all service interfaces; integration tests for critical flows |
| ✅ Data minimization/privacy | All processing local; no cloud dependency for core functionality; audio never leaves machine |

**Additional Constitution Alignment**:

| Pillar | Implementation |
|--------|----------------|
| I. Integridade | Audio persisted incrementally with checksums; raw files immutable; crash recovery preserves fragments |
| II. Simplicidade | `/help` command exhaustive; feedback <500ms; no silent failures |
| III. Continuidade | Sessions reopenable; new audio appends without modifying original |
| IV. Teste Primeiro | All user stories have acceptance tests; contract tests precede implementation |
| V. Busca | Embeddings mandatory; fallback to text search; chronological index always available |

## Project Structure

### Documentation (this feature)

```text
specs/004-resilient-voice-capture/
├── plan.md              # This file
├── research.md          # Phase 0 output - technology decisions
├── data-model.md        # Phase 1 output - entity definitions
├── quickstart.md        # Phase 1 output - developer onboarding
├── contracts/           # Phase 1 output - service interfaces
│   ├── audio-capture.md
│   ├── session-lifecycle.md
│   ├── transcription-queue.md
│   ├── search-service.md
│   └── help-system.md
├── checklists/
│   └── requirements.md  # Already created
└── tasks.md             # Phase 2 output (by /speckit.tasks)
```

### Source Code (repository root)

```text
src/
├── models/
│   ├── session.py       # Extended: add reopening support, processing status tracking
│   ├── audio_segment.py # NEW: audio segment with checksum and status
│   └── search_result.py # NEW: search result model
├── services/
│   ├── session/
│   │   ├── manager.py   # Extended: reopen_session(), get_processing_status()
│   │   ├── storage.py   # Extended: incremental save, crash recovery
│   │   └── matcher.py   # Already exists: semantic matching
│   ├── transcription/
│   │   ├── whisper.py   # Exists: Whisper transcription
│   │   └── queue.py     # NEW: async transcription queue
│   ├── search/
│   │   ├── engine.py    # NEW: unified search (semantic + text fallback)
│   │   └── indexer.py   # NEW: background embedding indexer
│   └── help/
│       └── registry.py  # NEW: command registry with help generation
├── cli/
│   └── commands.py      # NEW: /help, /sessions, /reopen, /close implementations
└── lib/
    ├── embedding.py     # Exists: EmbeddingService
    └── checksum.py      # NEW: file integrity verification

tests/
├── contract/
│   ├── test_audio_capture.py    # NEW
│   ├── test_session_lifecycle.py # NEW
│   ├── test_transcription_queue.py # NEW
│   └── test_search_service.py   # NEW
├── integration/
│   ├── test_session_workflow.py # Extended: reopen flow
│   ├── test_crash_recovery.py   # NEW
│   └── test_search_flow.py      # NEW
└── unit/
    ├── test_session.py          # Extended
    └── test_checksum.py         # NEW
```

**Structure Decision**: Single project structure maintained. This feature extends the existing codebase with new services (search, help, queue) while enhancing existing services (session manager, storage). No architectural split needed—the domain is cohesive around voice capture and retrieval.

## Complexity Tracking

> No Constitution Check violations requiring justification.

| Aspect | Decision | Rationale |
|--------|----------|-----------|
| Two-layer persistence | Audio files + JSON metadata | Separates immutable source (audio) from reconstructable derivatives (transcripts) |
| Async transcription queue | Background processing | Keeps UI responsive per Pillar II; transcription can take minutes |
| Dual search index | Semantic + chronological | Fallback ensures search always works per Pillar V |
