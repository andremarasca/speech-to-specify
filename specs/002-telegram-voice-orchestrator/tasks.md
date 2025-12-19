# Tasks: Telegram Voice Orchestrator (OATL)

**Input**: Design documents from `/specs/002-telegram-voice-orchestrator/`  
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅, quickstart.md ✅

**Tests**: Tests are included as constitution requires auditability and state transitions must be verified.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization, dependencies, and basic structure

- [x] T001 Add python-telegram-bot, openai-whisper, and PyTorch to requirements.txt
- [x] T002 [P] Create .env.example with TELEGRAM_BOT_TOKEN, TELEGRAM_ALLOWED_CHAT_ID, WHISPER_MODEL, WHISPER_DEVICE, SESSIONS_DIR configuration template
- [x] T003 [P] Create sessions/ directory structure at repository root with .gitkeep
- [x] T004 [P] Extend src/lib/config.py with TelegramConfig and WhisperConfig dataclasses
- [x] T005 Create src/cli/daemon.py entry point skeleton with argparse and logging setup

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core models and base infrastructure that ALL user stories depend on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

### Core Models

- [x] T006 Create src/models/session.py with SessionState enum (COLLECTING, TRANSCRIBING, TRANSCRIBED, PROCESSING, PROCESSED, ERROR)
- [x] T007 Create src/models/session.py with TranscriptionStatus enum (PENDING, SUCCESS, FAILED)
- [x] T008 Create src/models/session.py with AudioEntry dataclass (sequence, received_at, telegram_file_id, local_filename, file_size_bytes, duration_seconds, transcription_status, transcript_filename)
- [x] T009 Create src/models/session.py with ErrorEntry dataclass (timestamp, operation, target, message, recoverable)
- [x] T010 Create src/models/session.py with Session dataclass (id, state, created_at, finalized_at, chat_id, audio_entries, errors) with folder_path property

### Session Storage (Atomic JSON)

- [x] T011 Create src/services/session/__init__.py module init
- [x] T012 Create src/services/session/storage.py with SessionStorage base class following contracts/session-manager.md
- [x] T013 Implement atomic JSON write pattern (temp file + os.replace) in src/services/session/storage.py
- [x] T014 Implement load/save methods with validation in src/services/session/storage.py
- [x] T015 Implement list_sessions method scanning sessions/ directory in src/services/session/storage.py

### Session Manager Core

- [x] T016 Create src/services/session/manager.py with SessionManager class following contracts/session-manager.md interface
- [x] T017 Implement get_active_session() scanning for COLLECTING state in src/services/session/manager.py
- [x] T018 Implement state transition validation (allowed transitions per data-model.md) in src/services/session/manager.py
- [x] T019 Implement get_session_path() returning Path to session folder in src/services/session/manager.py

### Contract Tests

- [x] T020 [P] Create tests/contract/test_session_storage.py validating atomic write and load consistency
- [x] T021 [P] Create tests/contract/test_session_manager.py validating state transition rules from data-model.md

**Checkpoint**: Foundation ready - SessionStorage and SessionManager operational with tests passing ✅

---

## Phase 3: User Story 1 - Start New Session (Priority: P1) 🎯 MVP

**Goal**: User can remotely start a new voice capture session via `/start` command

**Independent Test**: Send `/start` command, verify new session folder created with timestamp ID and metadata.json in COLLECTING state

### Tests for User Story 1

- [x] T022 [P] [US1] Unit test for session ID generation (timestamp format YYYY-MM-DD_HH-MM-SS) in tests/unit/test_session.py
- [x] T023 [P] [US1] Unit test for create_session() with folder creation in tests/unit/test_session.py
- [x] T024 [P] [US1] Unit test for auto-finalize when active session exists in tests/unit/test_session.py

### Implementation for User Story 1

- [x] T025 [US1] Implement generate_session_id() using timestamps.py pattern in src/services/session/manager.py
- [x] T026 [US1] Implement create_session() with folder creation and metadata.json initialization in src/services/session/manager.py
- [x] T027 [US1] Implement auto-finalize logic when creating session with existing COLLECTING session in src/services/session/manager.py
- [x] T028 [US1] Create src/services/telegram/__init__.py module init
- [x] T029 [US1] Create src/services/telegram/adapter.py with TelegramEvent dataclass following contracts/telegram-bot.md
- [x] T030 [US1] Create src/services/telegram/bot.py with TelegramBotAdapter skeleton using ApplicationBuilder pattern
- [x] T031 [US1] Implement /start command handler in src/services/telegram/bot.py calling SessionManager.create_session()
- [x] T032 [US1] Implement send_message() for user confirmation in src/services/telegram/bot.py
- [x] T033 [US1] Implement chat_id authorization check (single user whitelist) in src/services/telegram/bot.py
- [x] T034 [US1] Wire daemon.py to initialize TelegramBotAdapter and SessionManager at startup in src/cli/daemon.py

**Checkpoint**: User Story 1 complete - `/start` creates session folder with metadata.json, responds with confirmation ✅

---

## Phase 4: User Story 2 - Collect Voice Messages (Priority: P1)

**Goal**: User can send multiple voice messages during active session, audio stored locally

**Independent Test**: Start session, send 3 voice messages, verify all audio files in session/audio/ folder with sequential naming

### Tests for User Story 2

- [x] T035 [P] [US2] Unit test for add_audio() with sequence numbering in tests/unit/test_session.py
- [x] T036 [P] [US2] Unit test for voice message rejection when no active session in tests/unit/test_session.py
- [x] T037 [P] [US2] Integration test for voice download and storage in tests/integration/test_telegram_flow.py

### Implementation for User Story 2

- [x] T038 [US2] Implement add_audio() with sequence increment and metadata update in src/services/session/manager.py
- [x] T039 [US2] Create audio/ subdirectory inside session folder on first audio in src/services/session/manager.py
- [x] T040 [US2] Implement download_voice() with file_id to local path in src/services/telegram/bot.py
- [x] T041 [US2] Implement voice message handler calling download_voice() and add_audio() in src/services/telegram/bot.py
- [x] T042 [US2] Implement rejection response when voice received without active session in src/services/telegram/bot.py
- [x] T043 [US2] Implement error logging to session errors[] on download failure in src/services/session/manager.py
- [x] T044 [US2] Add user notification on successful audio receipt (sequence number confirmation) in src/services/telegram/bot.py

**Checkpoint**: User Story 2 complete - Voice messages downloaded to session/audio/{sequence:03d}_audio.ogg ✅

---

## Phase 5: User Story 3 - Finalize Session and Transcribe (Priority: P1)

**Goal**: User finalizes session with `/done`, all audio files transcribed locally using Whisper

**Independent Test**: Finalize session with 2 audio files, verify transcription files generated in session folder

### Tests for User Story 3

- [x] T045 [P] [US3] Unit test for finalize_session() state transition (COLLECTING → TRANSCRIBING) in tests/unit/test_session.py
- [x] T046 [P] [US3] Unit test for transcription status update per audio in tests/unit/test_session.py
- [x] T047 [P] [US3] Contract test for TranscriptionService interface in tests/contract/test_transcription.py

### Transcription Service Implementation

- [x] T048 [US3] Create src/services/transcription/__init__.py module init
- [x] T049 [US3] Create src/services/transcription/base.py with TranscriptionService ABC and TranscriptionResult dataclass following contracts/transcription-service.md
- [x] T050 [US3] Create src/services/transcription/whisper.py with WhisperTranscriptionService implementation
- [x] T051 [US3] Implement load_model() with small.en, device=cuda, fp16=True in src/services/transcription/whisper.py
- [x] T052 [US3] Implement transcribe() single file processing in src/services/transcription/whisper.py
- [x] T053 [US3] Implement transcribe_batch() with on_progress callback in src/services/transcription/whisper.py
- [x] T054 [US3] Implement is_ready() and unload_model() for lifecycle management in src/services/transcription/whisper.py

### Session Finalization Implementation

- [x] T055 [US3] Implement finalize_session() with state transition to TRANSCRIBING in src/services/session/manager.py
- [x] T056 [US3] Implement transcription orchestration loop processing all audio_entries in src/services/session/manager.py
- [x] T057 [US3] Implement update_transcription_status() per audio file in src/services/session/manager.py
- [x] T058 [US3] Write transcript files to session/transcripts/{sequence:03d}_audio.txt in src/services/session/manager.py
- [x] T059 [US3] Implement transition to TRANSCRIBED when all audios processed in src/services/session/manager.py

### Telegram Integration for US3

- [x] T060 [US3] Implement /done and /finish command handlers triggering finalize_session() in src/services/telegram/bot.py
- [x] T061 [US3] Implement rejection of voice messages when session not in COLLECTING state in src/services/telegram/bot.py
- [x] T062 [US3] Implement transcription progress notifications to user in src/services/telegram/bot.py
- [x] T063 [US3] Load Whisper model at daemon startup in src/cli/daemon.py

**Checkpoint**: User Story 3 complete - `/done` triggers transcription, transcripts appear in session folder

---

## Phase 6: User Story 4 - Retrieve Transcriptions (Priority: P2)

**Goal**: User can request transcriptions via `/transcripts` command

**Independent Test**: Request transcriptions from TRANSCRIBED session, verify text delivered via Telegram

### Tests for User Story 4

- [x] T064 [P] [US4] Unit test for transcript file reading and concatenation in tests/unit/test_session.py
- [x] T065 [P] [US4] Unit test for message splitting when exceeding Telegram limits in tests/unit/test_telegram.py

### Implementation for User Story 4

- [x] T066 [US4] Implement get_transcripts() method returning concatenated text in src/services/session/manager.py
- [x] T067 [US4] Implement /transcripts command handler in src/services/telegram/bot.py
- [x] T068 [US4] Implement message splitting for Telegram 4096 char limit in src/services/telegram/bot.py
- [x] T069 [US4] Implement state validation (require TRANSCRIBED or later) in /transcripts handler in src/services/telegram/bot.py
- [x] T070 [US4] Implement send_file() for large transcripts as .txt attachment in src/services/telegram/bot.py

**Checkpoint**: User Story 4 complete - `/transcripts` returns session transcriptions via Telegram ✅

---

## Phase 7: User Story 5 - Trigger Downstream Processing (Priority: P2)

**Goal**: User can send transcribed session to narrative pipeline via `/process` command

**Independent Test**: Command processing on TRANSCRIBED session, verify session path passed to downstream pipeline

### Tests for User Story 5

- [x] T071 [P] [US5] Unit test for transcript consolidation format in tests/unit/test_downstream.py
- [x] T072 [P] [US5] Integration test for downstream processor invocation in tests/integration/test_session_workflow.py

### Implementation for User Story 5

- [x] T073 [US5] Create src/services/session/processor.py with DownstreamProcessor following contracts/downstream-processor.md
- [x] T074 [US5] Implement consolidate_transcripts() creating process/input.txt with header and separator format in src/services/session/processor.py
- [x] T075 [US5] Implement process() invoking src.cli.main.run() with consolidated input in src/services/session/processor.py
- [x] T076 [US5] Implement list_outputs() scanning process/output/ directory in src/services/session/processor.py
- [x] T077 [US5] Implement /process command handler in src/services/telegram/bot.py
- [x] T078 [US5] Implement state transition TRANSCRIBED → PROCESSING → PROCESSED in src/services/session/manager.py
- [x] T079 [US5] Implement error handling: remain in TRANSCRIBED state on failure, log error in src/services/session/processor.py
- [x] T080 [US5] Implement processing completion notification to user in src/services/telegram/bot.py

**Checkpoint**: User Story 5 complete - `/process` triggers narrative pipeline, results in session/process/output/ ✅

---

## Phase 8: User Story 6 - Query Session Status (Priority: P3)

**Goal**: User can check current session status at any time via `/status` command

**Independent Test**: Query status at each session state, verify accurate state information returned

### Tests for User Story 6

- [x] T081 [P] [US6] Unit test for status formatting with state and audio count in tests/unit/test_telegram.py

### Implementation for User Story 6

- [x] T082 [US6] Implement get_status_summary() returning formatted status string in src/services/session/manager.py
- [x] T083 [US6] Implement /status command handler in src/services/telegram/bot.py
- [x] T084 [US6] Include available actions based on current state in status response in src/services/telegram/bot.py
- [x] T085 [US6] Implement recent sessions list when no active session in /status handler in src/services/telegram/bot.py

**Checkpoint**: User Story 6 complete - `/status` shows current state, audio count, available actions ✅

---

## Phase 9: User Story 7 - List Session Results (Priority: P3)

**Goal**: User can list and retrieve individual files from session via `/list` and `/get` commands

**Independent Test**: List files from processed session, verify accurate file listing returned

### Tests for User Story 7

- [x] T086 [P] [US7] Unit test for file listing with type detection in tests/unit/test_session.py

### Implementation for User Story 7

- [x] T087 [US7] Implement list_session_files() returning all files with types in src/services/session/manager.py
- [x] T088 [US7] Implement /list command handler in src/services/telegram/bot.py
- [x] T089 [US7] Implement /get <filename> command handler with file validation in src/services/telegram/bot.py
- [x] T090 [US7] Implement send_file() for arbitrary session files in src/services/telegram/bot.py

**Checkpoint**: User Story 7 complete - `/list` shows files, `/get <file>` retrieves specific file ✅

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: Error handling, logging, robustness, and final validation

- [x] T091 Implement graceful shutdown (SIGINT/SIGTERM handling) in src/cli/daemon.py
- [x] T092 [P] Implement comprehensive logging throughout all services with timestamps
- [x] T093 [P] Add /help command listing all available commands in src/services/telegram/bot.py
- [x] T094 Implement unknown command response with help suggestion in src/services/telegram/bot.py
- [x] T095 [P] Add session cleanup/archival for old completed sessions in src/services/session/manager.py
- [x] T096 [P] Create README section for Telegram Voice Orchestrator in README.md
- [x] T097 Run quickstart.md validation end-to-end
- [x] T098 Final integration test: full workflow from /start to /process in tests/integration/test_session_workflow.py

**Checkpoint**: All implementation complete. 197 tests passing. ✅

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-9)**: All depend on Foundational phase completion
  - US1 (Phase 3): Foundation only
  - US2 (Phase 4): Depends on US1 (needs active session)
  - US3 (Phase 5): Depends on US2 (needs audio in session)
  - US4 (Phase 6): Depends on US3 (needs transcripts)
  - US5 (Phase 7): Depends on US3 (needs transcripts)
  - US6 (Phase 8): Can run after US1 (status works at any state)
  - US7 (Phase 9): Can run after US3 (needs files to list)
- **Polish (Phase 10)**: Depends on all user stories

### User Story Dependencies

```text
          ┌──────────────────────────────────────────────────────────────┐
          │                    Foundational (Phase 2)                     │
          └──────────────────────────────────────────────────────────────┘
                                       │
                    ┌──────────────────┼──────────────────┐
                    │                  │                  │
                    ▼                  ▼                  ▼
          ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
          │    US1 P1    │   │    US6 P3    │   │ (blocks US2) │
          │  /start      │   │   /status    │   │              │
          └──────────────┘   └──────────────┘   └──────────────┘
                    │
                    ▼
          ┌──────────────┐
          │    US2 P1    │
          │  Voice Msg   │
          └──────────────┘
                    │
                    ▼
          ┌──────────────┐
          │    US3 P1    │
          │ /done+trans  │
          └──────────────┘
                    │
          ┌─────────┴─────────┐
          │                   │
          ▼                   ▼
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│    US4 P2    │     │    US5 P2    │     │    US7 P3    │
│ /transcripts │     │   /process   │     │  /list /get  │
└──────────────┘     └──────────────┘     └──────────────┘
```

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Models/Storage before services
- Services before Telegram handlers
- Core implementation before integration
- Story complete before moving to next priority

### Parallel Opportunities

- All Setup tasks marked [P] can run in parallel (T002, T003, T004)
- All Contract tests marked [P] can run in parallel (T020, T021)
- Tests within each user story marked [P] can run in parallel
- US6 (/status) can be implemented in parallel with US2-US3 once US1 is done

---

## Parallel Example: Setup Phase

```bash
# Launch all independent Setup tasks together:
Task T002: "Create .env.example configuration template"
Task T003: "Create sessions/ directory structure"
Task T004: "Extend src/lib/config.py with TelegramConfig and WhisperConfig"
```

## Parallel Example: User Story 3 Tests

```bash
# Launch all US3 tests together:
Task T045: "Unit test for finalize_session() state transition"
Task T046: "Unit test for transcription status update"
Task T047: "Contract test for TranscriptionService interface"
```

---

## Implementation Strategy

### MVP First (User Stories 1-3 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1 (/start)
4. Complete Phase 4: User Story 2 (voice collection)
5. Complete Phase 5: User Story 3 (/done + transcription)
6. **STOP and VALIDATE**: Test full workflow: /start → send 3 audios → /done → transcripts generated
7. Deploy/demo if ready - **This is a functional MVP!**

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. Add US1 → Test /start independently → Minimal daemon running
3. Add US2 → Test voice collection → Core data capture working
4. Add US3 → Test transcription → **MVP Complete! Full local workflow!**
5. Add US4 → Test /transcripts → Remote transcript retrieval
6. Add US5 → Test /process → Full pipeline integration
7. Add US6, US7 → Quality of life improvements

### Suggested Commit Strategy

Each task should be a single atomic commit. Suggested commit message format:

```text
T001: Add python-telegram-bot, whisper, PyTorch to requirements.txt
T006: Add SessionState enum to src/models/session.py
T025: Implement generate_session_id() in SessionManager
```

---

## Notes

- [P] tasks = different files, no dependencies - can run in parallel
- [Story] label maps task to specific user story for traceability
- All state persisted to JSON for auditability (Constitution: Estado Explícito)
- Telegram is channel only; all processing local (Constitution: Soberania dos Dados)
- Sessions immutable after finalization (Constitution: Imutabilidade)
- Test Whisper model loading early - downloads ~500MB on first run
- Use existing src/lib/timestamps.py pattern for session ID generation
