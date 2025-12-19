# Tasks: Resilient Voice Capture

**Input**: Design documents from `/specs/004-resilient-voice-capture/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅

**Tests**: Constitution (Pillar IV - Teste Primeiro) requires tests. Contract tests defined in each service contract.

**Organization**: Tasks grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2)
- Include exact file paths in descriptions

## Path Conventions

- **Single project**: `src/`, `tests/` at repository root (per plan.md)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and foundational utilities

- [x] T001 Create directory structure: src/services/audio/, src/services/search/, src/services/help/ per plan.md
- [x] T002 [P] Create ChecksumService in src/lib/checksum.py with SHA-256 file hashing
- [x] T003 [P] Add ProcessingStatus enum to src/models/session.py per data-model.md
- [x] T004 [P] Add READY, EMBEDDING, INTERRUPTED states to SessionState enum in src/models/session.py
- [x] T005 [P] Create SearchResult model in src/models/search_result.py per data-model.md
- [x] T006 [P] Unit test for ChecksumService in tests/unit/test_checksum.py

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T007 Extend Session model with reopen_count, processing_status fields in src/models/session.py
- [x] T008 Extend AudioEntry with checksum and reopen_epoch fields in src/models/session.py
- [x] T009 Add state transition validation methods to SessionState (can_transition_to) in src/models/session.py
- [x] T010 [P] Create base HelpSystem interface in src/services/help/registry.py per contracts/help-system.md
- [x] T011 [P] Create base TranscriptionQueueService interface in src/services/transcription/queue.py per contracts/transcription-queue.md
- [x] T012 [P] Create base SearchService interface in src/services/search/engine.py per contracts/search-service.md
- [x] T013 Unit tests for extended Session model in tests/unit/test_session.py

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - Start and Record Voice Session (Priority: P1) 🎯 MVP

**Goal**: User can start a session and record audio with visible status indicator. Audio persisted incrementally with checksums.

**Independent Test**: Start session, record audio chunks, verify all segments stored with checksums and correct metadata.

### Tests for User Story 1

- [x] T014 [P] [US1] Contract test for AudioCaptureService.add_audio_chunk in tests/contract/test_audio_capture.py
- [x] T015 [P] [US1] Contract test for AudioCaptureService.verify_integrity in tests/contract/test_audio_capture.py
- [x] T016 [P] [US1] Contract test for session creation in tests/contract/test_audio_capture.py
- [x] T017 [P] [US1] Integration test for start-record flow in tests/integration/test_session_workflow.py

### Implementation for User Story 1

- [x] T018 [P] [US1] Create AudioCaptureService interface in src/services/audio/capture.py per contracts/audio-capture.md
- [x] T019 [P] [US1] Create CaptureContext, IntegrityReport, OrphanRecovery dataclasses in src/services/audio/capture.py
- [x] T020 [US1] Implement AudioCaptureService.add_audio_chunk with atomic persistence in src/services/audio/capture.py
- [x] T021 [US1] Implement AudioCaptureService.verify_integrity with checksum validation in src/services/audio/capture.py
- [x] T022 [US1] Extend SessionManager.create_session to initialize reopen_count=0 in src/services/session/manager.py
- [x] T023 [US1] Add status indicator feedback messages to session creation in src/services/session/manager.py
- [x] T024 [US1] Implement /start command handler in src/cli/commands.py

**Checkpoint**: User Story 1 complete - can start sessions and record audio with integrity guarantees

---

## Phase 4: User Story 2 - Finalize Session with Background Processing (Priority: P1)

**Goal**: User can finalize session, receive confirmation, and transcription starts asynchronously.

**Independent Test**: Finalize active session, verify confirmation message, audio count, and transcription queue populated.

### Tests for User Story 2

- [x] T025 [P] [US2] Contract test for finalize_session in tests/contract/test_session_lifecycle.py
- [x] T026 [P] [US2] Contract test for TranscriptionQueueService.queue_session in tests/contract/test_transcription_queue.py
- [x] T027 [P] [US2] Contract test for TranscriptionQueueService.get_session_progress in tests/contract/test_transcription_queue.py
- [x] T028 [P] [US2] Integration test for finalize-and-queue flow in tests/integration/test_session_workflow.py

### Implementation for User Story 2

- [x] T029 [P] [US2] Create QueueResult, QueueStatus, SessionProgress dataclasses in src/services/transcription/queue.py
- [x] T030 [P] [US2] Create TranscriptionEvent, TranscriptionEventType in src/services/transcription/queue.py
- [x] T031 [US2] Implement TranscriptionQueueService.queue_session in src/services/transcription/queue.py
- [x] T032 [US2] Implement TranscriptionQueueService.get_session_progress in src/services/transcription/queue.py
- [x] T033 [US2] Implement TranscriptionQueueService.start_worker with background loop in src/services/transcription/queue.py
- [x] T034 [US2] Extend SessionManager.finalize_session to set finalized_at and trigger queue in src/services/session/manager.py
- [x] T035 [US2] Create FinalizeResult dataclass with user-friendly confirmation message in src/services/session/manager.py
- [x] T036 [US2] Implement /close command handler in src/cli/commands.py
- [x] T037 [US2] Implement /status command handler in src/cli/commands.py

**Checkpoint**: User Stories 1+2 complete - full capture-and-finalize cycle works as MVP

---

## Phase 5: User Story 3 - Reopen and Extend Previous Session (Priority: P2)

**Goal**: User can reopen finalized session, add new audio, and re-finalize with only new audio processed.

**Independent Test**: Reopen READY session, add new audio, finalize, verify only new segments queued for transcription.

### Tests for User Story 3

- [x] T038 [P] [US3] Contract test for reopen_session in tests/contract/test_session_lifecycle.py
- [x] T039 [P] [US3] Contract test verifying original audio unchanged after reopen in tests/contract/test_session_lifecycle.py
- [x] T040 [P] [US3] Integration test for reopen-add-finalize flow in tests/integration/test_session_workflow.py

### Implementation for User Story 3

- [x] T041 [P] [US3] Create ReopenResult dataclass in src/services/session/manager.py
- [x] T042 [US3] Implement SessionManager.reopen_session with epoch increment in src/services/session/manager.py
- [x] T043 [US3] Add reopen_epoch tracking to AudioCaptureService.add_audio_chunk in src/services/audio/capture.py
- [x] T044 [US3] Modify queue_session to filter segments by transcription_status=PENDING in src/services/transcription/queue.py
- [x] T045 [US3] Implement /reopen command handler with session resolution in src/cli/commands.py

**Checkpoint**: User Story 3 complete - sessions can be extended without losing original content

---

## Phase 6: User Story 4 - Semantic Search Across Sessions (Priority: P2)

**Goal**: User can search sessions by meaning, receive ranked results with preview fragments.

**Independent Test**: Create sessions with known content, search conceptually, verify semantic matches returned with context.

### Tests for User Story 4

- [x] T046 [P] [US4] Contract test for SearchService.search with semantic results in tests/contract/test_search_service.py
- [x] T047 [P] [US4] Contract test for SearchService.list_chronological in tests/contract/test_search_service.py
- [x] T048 [P] [US4] Contract test for fallback to text search in tests/contract/test_search_service.py
- [x] T049 [P] [US4] Integration test for search flow in tests/integration/test_search_flow.py

### Implementation for User Story 4

- [x] T050 [P] [US4] Create SearchResponse, PreviewFragment, IndexStatus dataclasses in src/services/search/engine.py
- [x] T051 [P] [US4] Create EmbeddingIndexer in src/services/search/indexer.py for session embedding generation
- [x] T052 [US4] Implement SearchService.search with semantic + text fallback in src/services/search/engine.py
- [x] T053 [US4] Implement SearchService.list_chronological in src/services/search/engine.py
- [x] T054 [US4] Implement SearchService.get_index_status in src/services/search/engine.py
- [x] T055 [US4] Implement fragment extraction with highlight_ranges in src/services/search/engine.py
- [x] T056 [US4] Integrate embedding generation into transcription completion callback in src/services/transcription/queue.py
- [x] T057 [US4] Implement /sessions command handler (search + list) in src/cli/commands.py

**Checkpoint**: User Story 4 complete - sessions searchable by semantic meaning

---

## Phase 7: User Story 5 - Help Command with Exhaustive Documentation (Priority: P3)

**Goal**: User can invoke /help and see all commands documented exhaustively.

**Independent Test**: Invoke help, verify all registered commands appear with descriptions, params, examples.

### Tests for User Story 5

- [x] T058 [P] [US5] Contract test for HelpSystem.get_help in tests/contract/test_help_system.py
- [x] T059 [P] [US5] Contract test for HelpSystem.validate_completeness in tests/contract/test_help_system.py
- [x] T060 [P] [US5] Test that all commands are registered (no undocumented handlers) in tests/contract/test_help_system.py

### Implementation for User Story 5

- [x] T061 [P] [US5] Create CommandInfo, CommandHandler, HelpResponse dataclasses in src/services/help/registry.py
- [x] T062 [P] [US5] Create ValidationResult dataclass in src/services/help/registry.py
- [x] T063 [US5] Implement HelpSystem.register with duplicate detection in src/services/help/registry.py
- [x] T064 [US5] Implement HelpSystem.get_help with category grouping in src/services/help/registry.py
- [x] T065 [US5] Implement HelpSystem.validate_completeness in src/services/help/registry.py
- [x] T066 [US5] Register all existing commands (/start, /close, /status, /reopen, /sessions) in src/cli/commands.py
- [x] T067 [US5] Implement /help command handler in src/cli/commands.py

**Checkpoint**: User Story 5 complete - help system ensures no undocumented commands

---

## Phase 8: User Story 6 - Graceful Degradation on Failures (Priority: P3)

**Goal**: System handles failures gracefully with diagnostic messages and recovery options.

**Independent Test**: Simulate crash during recording, restart, verify partial audio preserved and recovery offered.

### Tests for User Story 6

- [x] T068 [P] [US6] Contract test for detect_interrupted_sessions in tests/contract/test_session_lifecycle.py
- [x] T069 [P] [US6] Contract test for recover_session with RESUME action in tests/contract/test_session_lifecycle.py
- [x] T070 [P] [US6] Contract test for AudioCaptureService.recover_orphans in tests/contract/test_audio_capture.py
- [x] T071 [P] [US6] Integration test for crash recovery flow in tests/integration/test_crash_recovery.py

### Implementation for User Story 6

- [x] T072 [P] [US6] Create InterruptedSession, RecoveryAction, RecoverResult dataclasses in src/services/session/manager.py
- [x] T073 [US6] Implement SessionManager.detect_interrupted_sessions in src/services/session/manager.py
- [x] T074 [US6] Implement SessionManager.recover_session with RESUME/FINALIZE/DISCARD in src/services/session/manager.py
- [x] T075 [US6] Implement AudioCaptureService.recover_orphans in src/services/audio/capture.py
- [x] T076 [US6] Add startup check for interrupted sessions in application initialization
- [x] T077 [US6] Implement TranscriptionQueueService.retry_failed in src/services/transcription/queue.py
- [x] T078 [US6] Implement /recover command handler in src/cli/commands.py
- [x] T079 [US6] Implement /retry command handler in src/cli/commands.py

**Checkpoint**: User Story 6 complete - system resilient to failures

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [x] T080 [P] Add comprehensive logging across all services
- [x] T081 [P] Run all quickstart.md test scenarios to validate full workflow
- [x] T082 [P] Documentation cleanup and README updates
- [x] T083 Performance profiling for search latency (<30s requirement from SC-001)
- [x] T084 Verify feedback latency <500ms (SC-003) across all commands
- [x] T085 Security review: ensure audio files have restricted permissions

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - start immediately
- **Foundational (Phase 2)**: Depends on Setup - BLOCKS all user stories
- **User Story 1 (Phase 3)**: Depends on Foundational - MVP start
- **User Story 2 (Phase 4)**: Depends on Foundational; can parallel with US1 but logically follows
- **User Story 3 (Phase 5)**: Depends on US1+US2 (needs finalized sessions to reopen)
- **User Story 4 (Phase 6)**: Depends on US2 (needs transcriptions for search)
- **User Story 5 (Phase 7)**: Depends on Foundational; can parallel with US1-4
- **User Story 6 (Phase 8)**: Depends on US1+US2 (needs sessions to recover)
- **Polish (Phase 9)**: Depends on all user stories

### User Story Dependencies

| Story | Can Start After | Notes |
|-------|-----------------|-------|
| US1 (Start/Record) | Phase 2 | MVP foundation |
| US2 (Finalize) | Phase 2 | Can parallel US1; uses US1's audio capture |
| US3 (Reopen) | US1+US2 | Needs completed sessions |
| US4 (Search) | US2 | Needs transcriptions |
| US5 (Help) | Phase 2 | Independent; integrate commands as built |
| US6 (Recovery) | US1+US2 | Needs sessions to recover |

### Within Each User Story

1. Contract tests FIRST (must FAIL before implementation)
2. Models and dataclasses
3. Service implementation
4. Command handlers
5. Integration tests PASS

### Parallel Opportunities

**Phase 1 (all parallel)**:
- T002, T003, T004, T005, T006 can run simultaneously

**Phase 2**:
- T010, T011, T012 (interfaces) can parallel after T007-T009

**Per User Story**:
- All contract tests marked [P] can parallel
- Dataclass creation marked [P] can parallel
- After services complete, command handlers can parallel

---

## Parallel Example: User Story 1

```bash
# Launch all tests in parallel:
T014: Contract test for add_audio_chunk
T015: Contract test for verify_integrity
T016: Contract test for session creation
T017: Integration test for start-record flow

# Launch interface + dataclasses in parallel:
T018: AudioCaptureService interface
T019: CaptureContext, IntegrityReport dataclasses
```

---

## Implementation Strategy

### MVP First (User Stories 1+2)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: User Story 1 (Start/Record)
4. Complete Phase 4: User Story 2 (Finalize)
5. **STOP and VALIDATE**: Full capture cycle works
6. Demo: User can start → record → finalize → see transcription progress

### Incremental Delivery

| Increment | Stories | Capability |
|-----------|---------|------------|
| MVP | US1 + US2 | Basic capture and processing |
| v1.1 | + US3 | Session reopening |
| v1.2 | + US4 | Semantic search |
| v1.3 | + US5 | Help system |
| v1.4 | + US6 | Crash recovery |

---

## Notes

- All tasks follow checklist format: `- [ ] [TaskID] [P?] [Story?] Description with file path`
- Constitution requires tests (Pillar IV) - contract tests included for each service
- Semantic search fallback ensures Pillar V compliance (search always works)
- Help completeness test ensures Pillar II compliance (no undocumented commands)
- Verify tests FAIL before implementation per TDD
- Commit after each logical task group
