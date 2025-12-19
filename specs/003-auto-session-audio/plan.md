# Implementation Plan: Auto-Session Audio Capture

**Branch**: `003-auto-session-audio` | **Date**: 2025-12-18 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/003-auto-session-audio/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

Eliminate the bureaucratic requirement of pre-starting sessions before sending audio. When a user sends audio without an active session, the system automatically creates a new session as a "founding event", guaranteeing zero data loss. Sessions receive intelligible names derived from their content (first words of transcription or fallback timestamp), and users can reference sessions using natural language descriptions that the system resolves via semantic matching.

## Technical Context

**Language/Version**: Python 3.11+  
**Primary Dependencies**: python-telegram-bot[all]>=22.0, openai-whisper>=20231117, pydantic>=2.5.0, sentence-transformers (NEW for semantic matching)  
**Storage**: File-based JSON (sessions/), following existing SessionStorage pattern  
**Testing**: pytest with contract/, integration/, unit/ structure  
**Target Platform**: Local execution (Windows/Linux), Telegram Bot API interface  
**Project Type**: Single project - extends existing `src/` structure  
**Performance Goals**: Session creation within 2 seconds of audio receipt (SC-005)  
**Constraints**: Local-only processing (no cloud), CPU-based embedding for semantic matching  
**Scale/Scope**: Single-user (personal assistant), ~100 sessions, low concurrency

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Evidence |
|-----------|--------|----------|
| **Determinism and replayability** | ✅ PASS | Session creation is deterministic (audio event → session). All state persisted to JSON files. Replay possible from audio input log. |
| **Auditability** | ✅ PASS | Every session creation logged with timestamp. Audio receipt logged before any processing. Session metadata includes creation context. `name_source` field tracks name origin for full audit trail. |
| **Clear boundaries** | ✅ PASS | SessionManager handles audio→session flow. SessionMatcher handles natural language lookup. NameGenerator handles intelligible ID creation. Explicit contracts for each in `contracts/`. |
| **Human-in-the-loop safety** | ✅ PASS | Auto-session is non-destructive (creates, doesn't delete). Ambiguous session references prompt user confirmation via `AMBIGUOUS` match type. No irreversible actions. |
| **Validation and test coverage** | ✅ PASS | Contract tests for each new service interface (NameGenerator, SessionMatcher). Integration tests for audio→session flow. Unit tests for name generation and matching logic. |
| **Data minimization/privacy** | ✅ PASS | Audio stored locally only. Semantic embeddings computed locally via `all-MiniLM-L6-v2`. No external services for content processing. Embeddings are 384-dim floats, not reversible to content. |

**Post-Design Re-evaluation**: ✅ All gates still pass after Phase 1 design. The data model and contracts maintain determinism (explicit state transitions), auditability (NameSource enum), and clear boundaries (three distinct contracts).

## Project Structure

### Documentation (this feature)

```text
specs/003-auto-session-audio/
├── plan.md              # This file
├── research.md          # Phase 0: semantic matching, name generation research
├── data-model.md        # Phase 1: Session handle, SessionReference entities
├── quickstart.md        # Phase 1: How to test the feature
├── contracts/           # Phase 1: Service interfaces
│   ├── auto-session-handler.md  # SessionManager extension
│   ├── session-matcher.md       # Natural language lookup
│   └── name-generator.md        # Intelligible name creation
└── tasks.md             # Phase 2 output (NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
src/
├── models/
│   └── session.py           # Extend with intelligible_name, name_source, embedding
├── services/
│   ├── session/
│   │   ├── manager.py       # Extend: handle_audio_receipt(), update_session_name()
│   │   ├── matcher.py       # NEW: SessionMatcher with resolve(), rebuild_index()
│   │   ├── name_generator.py # NEW: NameGenerator with cascading fallback
│   │   └── storage.py       # Extend: session index for efficient matching
│   └── telegram/
│       └── bot.py           # Extend: voice handler calls handle_audio_receipt()
├── cli/
└── lib/
    └── embedding.py         # NEW: lazy-loaded SentenceTransformer wrapper

tests/
├── contract/
│   ├── test_session_matcher.py  # NEW: SessionMatcher contract
│   └── test_name_generator.py   # NEW: NameGenerator contract
├── integration/
│   └── test_auto_session.py     # NEW: audio→session flow
└── unit/
    ├── test_session.py          # Extend: new fields
    └── test_name_generator.py   # NEW: name extraction logic
```

**Structure Decision**: Single project structure. This feature extends the existing session subsystem (`src/services/session/`) with two new modules (matcher.py, name_generator.py) and modifies the existing manager.py to implement auto-creation behavior.

## Complexity Tracking

> No violations identified. Feature aligns with all Constitution principles.
