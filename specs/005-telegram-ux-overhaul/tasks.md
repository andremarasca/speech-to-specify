# Tasks: Telegram UX Overhaul

**Input**: Design documents from `/specs/005-telegram-ux-overhaul/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅

**Tests**: Mandatory per Constitution Principle IV (Binary Operational Integrity). Contract tests required for all new services.

**Organization**: Tasks grouped by user story for independent implementation and testing.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3...)
- Exact file paths included in descriptions

## Path Conventions

Single project structure per plan.md:
- Source: `src/`
- Tests: `tests/contract/`, `tests/integration/`, `tests/unit/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project structure and configuration for new presentation layer

- [X] T001 Create presentation layer package structure in src/services/presentation/__init__.py
- [X] T002 [P] Add UIConfig class to src/lib/config.py with externalized parameters (TELEGRAM_MESSAGE_LIMIT, UI_PROGRESS_INTERVAL_SECONDS, OPERATION_TIMEOUT_SECONDS)
- [X] T003 [P] Create message templates module in src/lib/messages.py with externalized UI strings
- [X] T004 [P] Create error catalog module in src/lib/error_catalog.py with ERROR_CATALOG dict per contracts/error-catalog.md
- [X] T005 Update .env.example with new UI configuration parameters
- [X] T005a [P] Create contract tests for error catalog in tests/contract/test_error_catalog.py

**Checkpoint**: Configuration and structure ready for implementation ✅

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core models and base components that ALL user stories depend on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T006 [P] Create UIPreferences dataclass in src/models/ui_state.py
- [X] T007 [P] Create UIState dataclass in src/models/ui_state.py
- [X] T008 [P] Create ProgressState dataclass in src/models/ui_state.py
- [X] T009 [P] Create KeyboardType enum in src/models/ui_state.py
- [X] T010 [P] Create OperationType enum in src/models/ui_state.py
- [X] T011 [P] Create ErrorSeverity enum in src/models/ui_state.py
- [X] T012 [P] Create UserFacingError dataclass in src/models/ui_state.py
- [X] T013 [P] Create RecoveryAction dataclass in src/models/ui_state.py
- [X] T014 [P] Create ConfirmationContext dataclass in src/models/ui_state.py
- [X] T015 Extend Session model with ui_preferences field in src/models/session.py
- [X] T015a Add checkpoint_data field to Session model for crash recovery state in src/models/session.py
- [X] T015b [P] Implement checkpoint persistence helper in src/services/session/checkpoint.py (save/load checkpoint state)
- [X] T015c [P] Create contract tests for checkpoint persistence in tests/contract/test_checkpoint.py
- [X] T016 Create keyboard builder module in src/services/telegram/keyboards.py with build_keyboard() for all KeyboardType values
- [X] T017 [P] Create unit tests for keyboard builders in tests/unit/test_keyboards.py
- [X] T018 [P] Create unit tests for message templates in tests/unit/test_messages.py

**Checkpoint**: Foundation ready - user story implementation can now begin ✅

---

## Phase 3: User Story 1 - Zero-Command Voice Capture (Priority: P1) 🎯 MVP

**Goal**: Send voice message → auto-create session → inline buttons → finalize with taps only

**Independent Test**: Send voice message with no active session; complete full transcription flow using only button taps

### Tests for User Story 1

- [X] T019 [P] [US1] Contract test for UIService.send_session_created() in tests/contract/test_ui_service.py
- [X] T020 [P] [US1] Contract test for UIService.send_audio_received() in tests/contract/test_ui_service.py
- [X] T021 [P] [US1] Contract test for UIService.build_keyboard(SESSION_ACTIVE) in tests/contract/test_ui_service.py
- [X] T022 [P] [US1] Integration test for voice message → auto-session flow in tests/integration/test_inline_keyboard_flow.py

### Implementation for User Story 1

- [X] T023 [US1] Create UIServiceProtocol and UIService class in src/services/telegram/ui_service.py
- [X] T024 [US1] Implement UIService.send_session_created() with inline keyboard in src/services/telegram/ui_service.py
- [X] T025 [US1] Implement UIService.send_audio_received() in src/services/telegram/ui_service.py
- [X] T026 [US1] Implement UIService.send_results() with action buttons in src/services/telegram/ui_service.py
- [X] T027 [US1] Implement UIService.send_paginated_text() for long transcriptions in src/services/telegram/ui_service.py
- [X] T028 [US1] Register CallbackQueryHandler in src/services/telegram/bot.py for action: callbacks
- [X] T029 [US1] Implement _handle_callback() router in src/services/telegram/bot.py delegating to existing handlers
- [X] T030 [US1] Extend TelegramEvent in src/services/telegram/adapter.py to support callback_query events
- [X] T031 [US1] Integrate UIService into voice message handler to send session created message with keyboard
- [X] T031a [US1] Add checkpoint save after each audio receipt in voice handler
- [X] T031b [US1] Implement orphaned session detection on bot startup in src/services/telegram/bot.py
- [X] T031c [US1] Implement UIService.send_recovery_prompt() for orphaned sessions with Resume/Finalize options
- [X] T031d [US1] Integration test for crash recovery flow in tests/integration/test_crash_recovery_ui.py

**Checkpoint**: User Story 1 complete - zero-command voice capture working with inline buttons, crash recovery supported
### Edge Cases for User Story 1

- [X] T031e [US1] Detect empty/silent voice messages and send ERR_TRANSCRIPTION_002 warning with continue option
- [X] T031f [US1] Implement audio queue with position feedback when rate limit exceeded (ERR_TELEGRAM_002)
- [X] T031g [P] [US1] Unit test for empty audio detection in tests/unit/test_audio_validation.py
---

## Phase 4: User Story 2 - Real-Time Progress Feedback (Priority: P2)

**Goal**: Visual progress indicator during transcription that updates in real-time

**Independent Test**: Finalize session with multiple audios; verify progress updates at least 3 times

### Tests for User Story 2

- [X] T032 [P] [US2] Contract test for ProgressReporter.start_operation() in tests/contract/test_progress_reporter.py
- [X] T033 [P] [US2] Contract test for ProgressReporter.update_progress() with throttling in tests/contract/test_progress_reporter.py
- [X] T034 [P] [US2] Contract test for UIService.send_progress() in tests/contract/test_ui_service.py
- [X] T035 [P] [US2] Contract test for UIService.update_progress() message editing in tests/contract/test_ui_service.py

### Implementation for User Story 2

- [X] T036 [US2] Create ProgressReporterProtocol and ProgressReporter class in src/services/presentation/progress.py
- [X] T037 [US2] Implement ProgressReporter.start_operation() in src/services/presentation/progress.py
- [X] T038 [US2] Implement ProgressReporter.update_progress() with throttling logic in src/services/presentation/progress.py
- [X] T039 [US2] Implement ProgressReporter.complete_operation() in src/services/presentation/progress.py
- [X] T040 [US2] Implement ProgressReporter.is_timed_out() in src/services/presentation/progress.py
- [X] T041 [US2] Implement format_progress_bar() helper in src/services/presentation/progress.py
- [X] T042 [US2] Implement UIService.send_progress() in src/services/telegram/ui_service.py
- [X] T043 [US2] Implement UIService.update_progress() with message.edit_text() in src/services/telegram/ui_service.py
- [X] T044 [US2] Integrate ProgressReporter into transcription workflow to emit progress updates

**Checkpoint**: User Story 2 complete - progress feedback visible during transcription ✅

---

## Phase 5: User Story 3 - Humanized Error Recovery (Priority: P2)

**Goal**: User-friendly error messages with actionable recovery buttons, no stack traces

**Independent Test**: Simulate storage error; verify message is humanized with retry button

### Tests for User Story 3

- [X] T045 [P] [US3] Contract test for ErrorPresentationLayer.translate_exception() in tests/contract/test_error_presentation.py
- [X] T046 [P] [US3] Contract test for ErrorPresentationLayer.format_for_telegram() in tests/contract/test_error_presentation.py
- [X] T047 [P] [US3] Contract test verifying no stack traces in user messages in tests/contract/test_error_presentation.py

### Implementation for User Story 3

- [X] T048 [US3] Create ErrorPresentationProtocol and ErrorPresentationLayer class in src/services/presentation/error_handler.py
- [X] T049 [US3] Implement ErrorPresentationLayer.translate_exception() with logging in src/services/presentation/error_handler.py
- [X] T050 [US3] Implement ErrorPresentationLayer.get_error_by_code() in src/services/presentation/error_handler.py
- [X] T051 [US3] Implement ErrorPresentationLayer.register_exception_mapping() in src/services/presentation/error_handler.py
- [X] T052 [US3] Implement ErrorPresentationLayer.format_for_telegram() in src/services/presentation/error_handler.py
- [X] T053 [US3] Register default exception mappings (FileNotFoundError, PermissionError, TimeoutError, etc.)
- [X] T054 [US3] Implement UIService.send_error() using ErrorPresentationLayer in src/services/telegram/ui_service.py
- [X] T055 [US3] Wrap bot handlers with error presentation layer to catch and translate exceptions
- [X] T056 [US3] Register CallbackQueryHandler for retry: callbacks in src/services/telegram/bot.py

**Checkpoint**: User Story 3 complete - errors are humanized with recovery options ✅

---

## Phase 6: User Story 4 - Session Conflict Protection (Priority: P3)

**Goal**: Confirmation dialog when new session would overwrite active session

**Independent Test**: With active session + audio, trigger new session; verify confirmation dialog

### Tests for User Story 4

- [X] T057 [P] [US4] Contract test for UIService.send_confirmation_dialog() in tests/contract/test_ui_service.py
- [X] T058 [P] [US4] Integration test for session conflict flow in tests/integration/test_inline_keyboard_flow.py

### Implementation for User Story 4

- [X] T059 [US4] Implement UIService.send_confirmation_dialog() in src/services/telegram/ui_service.py
- [X] T060 [US4] Add SESSION_CONFLICT keyboard type handling in src/services/telegram/keyboards.py
- [X] T061 [US4] Implement confirmation callback handlers (confirm:session_conflict:*) in src/services/telegram/bot.py
- [X] T062 [US4] Modify /start and voice handler to check for active session and trigger confirmation

**Checkpoint**: User Story 4 complete - session conflicts prompt user confirmation ✅

---

## Phase 7: User Story 5 - Contextual Help Discovery (Priority: P3)

**Goal**: Help button in all keyboards; contextual help relevant to current state

**Independent Test**: Navigate through flow; verify help button present and help content contextual

### Tests for User Story 5

- [X] T063 [P] [US5] Contract test for UIService.send_contextual_help() in tests/contract/test_ui_service.py
- [X] T064 [P] [US5] Unit test verifying all keyboards include help option in tests/unit/test_keyboards.py

### Implementation for User Story 5

- [X] T065 [US5] Add contextual help templates to src/lib/messages.py for each KeyboardType context
- [X] T066 [US5] Implement UIService.send_contextual_help() in src/services/telegram/ui_service.py
- [X] T067 [US5] Ensure all keyboard builders include help button in src/services/telegram/keyboards.py
- [X] T068 [US5] Register CallbackQueryHandler for action:help callbacks in src/services/telegram/bot.py
- [X] T069 [US5] Implement help callback that tracks context and returns to previous state

**Checkpoint**: User Story 5 complete - contextual help available throughout flow ✅

---

## Phase 8: User Story 6 - Long Operation Timeout Handling (Priority: P3)

**Goal**: Timeout notification with continue/cancel options for long operations

**Independent Test**: Trigger transcription exceeding timeout; verify notification with options

### Tests for User Story 6

- [X] T070 [P] [US6] Contract test for ProgressReporter timeout detection in tests/contract/test_progress_reporter.py
- [X] T071 [P] [US6] Contract test for timeout notification with options in tests/contract/test_ui_service.py

### Implementation for User Story 6

- [X] T072 [US6] Implement UIService.send_timeout_warning() in src/services/telegram/ui_service.py
- [X] T073 [US6] Add TIMEOUT keyboard type with continue/cancel options in src/services/telegram/keyboards.py
- [X] T074 [US6] Implement timeout check loop in ProgressReporter in src/services/presentation/progress.py
- [X] T075 [US6] Implement ProgressReporter.cancel_operation() in src/services/presentation/progress.py
- [X] T076 [US6] Register CallbackQueryHandler for action:continue_wait and action:cancel_operation in src/services/telegram/bot.py

**Checkpoint**: User Story 6 complete - user controls long-running operations ✅

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Accessibility verification, documentation, final validation

- [X] T077 [P] Verify all buttons have descriptive text labels (accessibility audit) per FR-013
- [X] T078 [P] Verify progress updates include text descriptions per FR-015
- [X] T079 [P] Add simplified_ui preference toggle via /preferences command
- [X] T080 [P] Implement onboarding flow for first-time users
- [X] T081 Run quickstart.md validation checklist
- [X] T082 [P] Update README.md with new UX features documentation
- [X] T083 Run full test suite and verify all tests pass

**Checkpoint**: Phase 9 complete - all polish tasks done, 730 tests passing ✅

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1 (Setup)
    ↓
Phase 2 (Foundational) ← BLOCKS all user stories
    ↓
┌───────────────────────────────────────────────────┐
│  User Stories can proceed in parallel or sequential│
│  ┌─────────┐  ┌─────────┐  ┌─────────┐           │
│  │ Phase 3 │  │ Phase 4 │  │ Phase 5 │           │
│  │  US1    │  │  US2    │  │  US3    │           │
│  │  P1 🎯  │  │  P2     │  │  P2     │           │
│  └────┬────┘  └────┬────┘  └────┬────┘           │
│       ↓            ↓            ↓                 │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐           │
│  │ Phase 6 │  │ Phase 7 │  │ Phase 8 │           │
│  │  US4    │  │  US5    │  │  US6    │           │
│  │  P3     │  │  P3     │  │  P3     │           │
│  └─────────┘  └─────────┘  └─────────┘           │
└───────────────────────────────────────────────────┘
    ↓
Phase 9 (Polish)
```

### User Story Dependencies

| Story | Depends On | Can Parallel With |
|-------|------------|-------------------|
| US1 (P1) | Phase 2 | None (MVP core) |
| US2 (P2) | Phase 2 | US1, US3 |
| US3 (P2) | Phase 2 | US1, US2 |
| US4 (P3) | Phase 2, US1 (session flow) | US5, US6 |
| US5 (P3) | Phase 2 | US4, US6 |
| US6 (P3) | Phase 2, US2 (progress) | US4, US5 |

### Parallel Opportunities by Phase

**Phase 2 (Foundational)**: T006-T014 all parallel (different files)
**Phase 3 (US1)**: T019-T022 tests parallel, then T023 sequential
**Phase 4 (US2)**: T032-T035 tests parallel
**Phase 5 (US3)**: T045-T047 tests parallel
**Phase 6-8**: Tests marked [P] can run in parallel

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (~5 tasks)
2. Complete Phase 2: Foundational (~13 tasks)
3. Complete Phase 3: User Story 1 (~13 tasks)
4. **STOP and VALIDATE**: Run tests, demo zero-command flow
5. Deploy if ready - users can now send voice → get transcription via buttons

### Incremental Delivery

| Increment | Phases | Delivers |
|-----------|--------|----------|
| MVP | 1 + 2 + 3 | Zero-command voice capture |
| +Progress | + 4 | Real-time progress feedback |
| +Errors | + 5 | Humanized error recovery |
| +Protection | + 6 | Session conflict prevention |
| +Help | + 7 | Contextual help |
| +Timeout | + 8 | Long operation control |
| Complete | + 9 | Polish, docs, validation |

### Task Count Summary

| Phase | Tasks | Parallel Tasks |
|-------|-------|----------------|
| 1. Setup | 6 | 4 |
| 2. Foundational | 16 | 13 |
| 3. US1 (P1) | 20 | 6 |
| 4. US2 (P2) | 13 | 4 |
| 5. US3 (P2) | 12 | 3 |
| 6. US4 (P3) | 6 | 2 |
| 7. US5 (P3) | 7 | 2 |
| 8. US6 (P3) | 7 | 2 |
| 9. Polish | 7 | 5 |
| **Total** | **94** | **41** |

---

## Notes

- All UI strings externalized to src/lib/messages.py (Constitution Principle V)
- Error catalog externalized to src/lib/error_catalog.py
- Tests validate behavior, not message text (avoid brittleness)
- Existing CLI commands remain functional (backward compatibility)
- `simplified_ui` preference modifies presentation, not functionality
- All buttons have text labels for accessibility (FR-013, FR-014)
