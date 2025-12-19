# Implementation Plan: Telegram Voice Orchestrator (OATL)

**Branch**: `002-telegram-voice-orchestrator` | **Date**: 2025-12-18 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/002-telegram-voice-orchestrator/spec.md`

## Summary

Enable remote voice-to-text orchestration via Telegram with local-only processing and data sovereignty. The system operates as an event-driven daemon that receives commands and voice messages through Telegram, stores audio files locally in session folders, transcribes using local Whisper model (GPU-accelerated), and integrates with the existing narrative pipeline via file-based communication. Sessions are immutable after finalization, ensuring full auditability and reproducibility.

## Technical Context

**Language/Version**: Python 3.11 (matching existing codebase)  
**Primary Dependencies**: python-telegram-bot (async), openai-whisper, PyTorch (CUDA), pydantic  
**Storage**: Filesystem-based (JSON metadata + binary audio files in session folders)  
**Testing**: pytest (unit + integration), fixtures for session state simulation  
**Target Platform**: Windows 11 with NVIDIA RTX 3050 (CUDA-enabled local execution)  
**Project Type**: Single project (extends existing src/ structure)  
**Performance Goals**: <2 min transcription for typical 5-audio session (1-2 min each)  
**Constraints**: All processing local (no cloud APIs for transcription), single user, continuous daemon operation  
**Scale/Scope**: Single user, <100 sessions/month, <20 min audio per session

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Evidence |
|-----------|--------|----------|
| **I. Soberania dos Dados** | ✅ PASS | All processing local; Telegram is channel only; Whisper runs on local GPU |
| **II. Estado Explícito e Verificável** | ✅ PASS | Session state in `metadata.json`; atomic writes after every transition |
| **III. Imutabilidade de Sessões** | ✅ PASS | Sessions locked after `/finish`; no modifications allowed post-finalization |
| **IV. Acoplamento Mínimo** | ✅ PASS | Telegram adapter isolated; downstream integration via path only; Whisper behind interface |
| **V. Lógica Determinística** | ✅ PASS | Session ID = timestamp; conflict resolution = auto-finalize; no heuristics |

Additional checks:
- ✅ Determinism and replayability: Session folder contains all inputs; state is explicit JSON
- ✅ Auditability: All events logged with timestamps; session folder is self-contained
- ✅ Clear boundaries: Telegram adapter → Session Manager → Transcription Service → Downstream Processor
- ✅ Human-in-the-loop: Explicit commands required for each phase transition
- ✅ Test coverage: Contract tests for each service boundary; integration tests for full workflow
- ✅ Data minimization: Only audio and derived text stored; no Telegram metadata retained

### Post-Design Re-check (Phase 1 Complete)

| Contract | Constitution Alignment |
|----------|------------------------|
| [telegram-bot.md](contracts/telegram-bot.md) | ✅ Adapter pattern isolates Telegram protocol; only events flow inward |
| [session-manager.md](contracts/session-manager.md) | ✅ State transitions explicit; JSON persistence; immutability enforced |
| [transcription-service.md](contracts/transcription-service.md) | ✅ Local Whisper; no cloud; CUDA-only |
| [downstream-processor.md](contracts/downstream-processor.md) | ✅ File-based communication only; no shared state |
| [data-model.md](data-model.md) | ✅ All state in metadata.json; validation rules documented |

**Re-check Result**: All principles satisfied. Design ready for task breakdown.

## Project Structure

### Documentation (this feature)

```text
specs/002-telegram-voice-orchestrator/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── telegram-bot.md
│   ├── session-manager.md
│   ├── transcription-service.md
│   └── downstream-processor.md
└── tasks.md             # Phase 2 output (via /speckit.tasks)
```

### Source Code (repository root)

```text
src/
├── models/
│   ├── __init__.py
│   ├── artifact.py          # existing
│   ├── execution.py         # existing
│   ├── input.py             # existing
│   ├── logs.py              # existing
│   └── session.py           # NEW: Session, AudioEntry, SessionState models
├── services/
│   ├── __init__.py
│   ├── orchestrator.py      # existing narrative pipeline
│   ├── llm/                 # existing LLM providers
│   ├── persistence/         # existing persistence
│   ├── telegram/            # NEW: Telegram bot adapter
│   │   ├── __init__.py
│   │   ├── bot.py           # Bot setup and handlers
│   │   └── adapter.py       # Event normalization layer
│   ├── session/             # NEW: Session management
│   │   ├── __init__.py
│   │   ├── manager.py       # Session lifecycle
│   │   └── storage.py       # Session folder operations
│   └── transcription/       # NEW: Whisper integration
│       ├── __init__.py
│       ├── base.py          # Interface
│       └── whisper.py       # Whisper implementation
├── cli/
│   ├── __init__.py
│   ├── main.py              # existing narrative CLI
│   └── daemon.py            # NEW: Telegram daemon entry point
└── lib/
    ├── __init__.py
    ├── config.py            # existing (extend for telegram/whisper config)
    └── ...

tests/
├── contract/
│   ├── test_llm_provider.py    # existing
│   ├── test_persistence.py     # existing
│   ├── test_session_storage.py # NEW
│   └── test_transcription.py   # NEW
├── integration/
│   ├── test_orchestrator.py    # existing
│   ├── test_telegram_flow.py   # NEW
│   └── test_session_workflow.py # NEW
└── unit/
    ├── test_config.py          # existing
    ├── test_models.py          # existing (extend for session models)
    ├── test_session_manager.py # NEW
    └── test_whisper_adapter.py # NEW
```

**Structure Decision**: Extends existing single-project structure. New modules added under `src/services/` with clear boundaries. Existing `src/cli/main.py` remains untouched; new daemon entry point at `src/cli/daemon.py`.

## Complexity Tracking

> No constitution violations - no entries needed.
