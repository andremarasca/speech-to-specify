# Implementation Plan: Telegram UX Overhaul

**Branch**: `005-telegram-ux-overhaul` | **Date**: 2025-12-19 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/005-telegram-ux-overhaul/spec.md`

## Summary

Implement a recognition-based interaction layer over the existing Telegram Voice Orchestrator that replaces command-based interaction with inline keyboards, auto-session creation, real-time progress feedback, and humanized error messages. The MVP focuses on a linear flow where sending audio auto-creates a session, with subsequent actions accessible via inline buttons, while maintaining absolute data sovereignty and clear separation between channel (Telegram) and processing core.

## Technical Context

**Language/Version**: Python 3.11+ (per pyproject.toml requires-python = ">=3.11")
**Primary Dependencies**: python-telegram-bot[all]>=22.0 (InlineKeyboardMarkup, CallbackQueryHandler), openai-whisper, pydantic>=2.5.0
**Storage**: Local JSON files (session metadata in ./sessions directory per existing architecture)
**Testing**: pytest (existing test structure in tests/contract/, tests/integration/, tests/unit/)
**Target Platform**: Local server with GPU for Whisper, Telegram as transport channel
**Project Type**: Single project (existing src/ structure)
**Performance Goals**: <2 seconds UI response time, progress updates every 5 seconds during transcription
**Constraints**: Telegram message limit 4096 chars, all processing local, no external notification services
**Scale/Scope**: Single user (TELEGRAM_ALLOWED_CHAT_ID), ~50 interaction patterns

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | How This Plan Addresses It | Status |
|-----------|---------------------------|--------|
| **I. Absolute Data Sovereignty** | All UI improvements occur in presentation layer; no external notification services; Telegram remains transport-only channel | ✅ PASS |
| **II. User Autonomy & Low Cognitive Load** | Recognition-over-recall via inline keyboards; auto-session creation; contextual help; humanized errors with recovery suggestions | ✅ PASS |
| **III. Immutable Structural Excellence** | New UIService layer isolated from core business logic; ErrorPresentationLayer wraps exceptions; SOLID compliance via adapter pattern | ✅ PASS |
| **IV. Binary Operational Integrity** | Contract tests for UIService; integration tests for inline keyboard flows; existing tests remain unaffected by interface refactoring | ✅ PASS |
| **V. Externalized Configuration** | Message templates, character limits (4096), timeouts, progress intervals in config files; no hardcoded UI strings | ✅ PASS |

**Restrictions Compliance:**
- ❌ External Processing: All processing remains local (Whisper on local GPU)
- ❌ Implementation Exposure: ErrorPresentationLayer hides stack traces, shows humanized messages
- ❌ Rigid UI Lock-in: CLI commands continue working alongside inline keyboards (backward compatible)
- ❌ Channel-Core Violation: UIService is adapter layer; core SessionManager/TranscriptionService unchanged

## Project Structure

### Documentation (this feature)

```text
specs/005-telegram-ux-overhaul/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── ui-service.md
│   ├── error-presentation.md
│   ├── error-catalog.md
│   └── progress-reporter.md
└── tasks.md             # Phase 2 output (NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
src/
├── models/
│   ├── session.py           # Extended: add ui_preferences and checkpoint_data fields
│   └── ui_state.py          # NEW: UIState, ProgressState models
├── services/
│   ├── telegram/
│   │   ├── bot.py           # Extended: CallbackQueryHandler registration, orphan detection
│   │   ├── adapter.py       # Extended: TelegramEvent callback support
│   │   ├── ui_service.py    # NEW: Inline keyboard generation, message formatting
│   │   └── keyboards.py     # NEW: InlineKeyboardMarkup builders
│   ├── session/
│   │   ├── manager.py       # Unchanged (core logic preserved)
│   │   └── checkpoint.py    # NEW: Checkpoint persistence helper
│   └── presentation/
│       ├── __init__.py      # NEW
│       ├── error_handler.py # NEW: ErrorPresentationLayer
│       └── progress.py      # NEW: ProgressReporter
├── cli/
│   └── commands.py          # Unchanged (backward compatibility)
└── lib/
    ├── config.py            # Extended: UIConfig class
    ├── messages.py          # NEW: Externalized message templates
    └── error_catalog.py     # NEW: Externalized error definitions

tests/
├── contract/
│   ├── test_ui_service.py        # NEW
│   ├── test_error_presentation.py # NEW
│   ├── test_error_catalog.py      # NEW
│   ├── test_progress_reporter.py  # NEW
│   └── test_checkpoint.py         # NEW
├── integration/
│   ├── test_inline_keyboard_flow.py # NEW
│   └── test_crash_recovery_ui.py    # NEW
└── unit/
    ├── test_keyboards.py          # NEW
    ├── test_messages.py           # NEW
    └── test_audio_validation.py   # NEW
```

**Structure Decision**: Single project structure (Option 1) maintained. New presentation layer added under `src/services/presentation/` following existing service organization. UI-specific Telegram components grouped under `src/services/telegram/`.

## Complexity Tracking

No constitution violations requiring justification. Design follows existing patterns.

---

## Post-Design Constitution Re-evaluation

*Re-checked after Phase 1 design completion.*

| Principle | Design Artifact | Compliance Verified |
|-----------|-----------------|---------------------|
| **I. Data Sovereignty** | UIService uses Telegram API only for message delivery; no data leaves local system | ✅ |
| **II. Low Cognitive Load** | data-model.md defines UIPreferences.simplified_ui; contracts define contextual help | ✅ |
| **III. Structural Excellence** | Contracts define clear interfaces (UIServiceProtocol, ErrorPresentationProtocol); adapter pattern preserved | ✅ |
| **IV. Operational Integrity** | Contract tests defined in each contract file; test locations specified in project structure | ✅ |
| **V. Externalized Config** | research.md lists all config parameters; messages.py for templates | ✅ |

**Design Decisions Validated:**
- ✅ No push notification service introduced (uses standard Telegram messages)
- ✅ Accessibility is default behavior, not optional mode
- ✅ Backward compatibility with CLI commands preserved
- ✅ Error catalog externalized, not hardcoded
- ✅ All UI strings externalized to messages.py

**Ready for Phase 2**: `/speckit.tasks` command
