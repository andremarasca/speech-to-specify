# Tasks: Semantic Session Search

**Input**: Design documents from `specs/006-semantic-session-search/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅

**Tests**: Integration tests required per Constitution Principle IV. Unit tests for new callback handlers.

**Organization**: Tasks grouped by user story for independent implementation and testing.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Configuration and message templates required by all user stories

- [ ] T001 Add SearchConfig class to src/lib/config.py with min_similarity_score, max_results, query_timeout_seconds
- [ ] T002 [P] Add search flow messages to src/lib/messages.py (SEARCH_PROMPT, SEARCH_RESULTS_HEADER, SEARCH_NO_RESULTS, SEARCH_SESSION_RESTORED, SEARCH_TIMEOUT)
- [ ] T003 [P] Add BUTTON_NEW_SEARCH and BUTTON_NEW_SEARCH_SIMPLIFIED to src/lib/messages.py

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: State management and keyboard infrastructure that ALL user stories depend on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T004 Add KeyboardType.SEARCH_RESULTS and SEARCH_NO_RESULTS enum values to src/models/ui_state.py
- [ ] T005 Add conversational state fields to VoiceOrchestrator.__init__ in src/cli/daemon.py (_awaiting_search_query, _search_timeout_tasks dicts)
- [ ] T006 [P] Add search_service parameter to VoiceOrchestrator constructor in src/cli/daemon.py
- [ ] T007 [P] Add search_config property loading in VoiceOrchestrator.__init__ in src/cli/daemon.py
- [ ] T008 Inject SearchService instance in run_daemon() function in src/cli/daemon.py

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - Search via Button (Priority: P1) 🎯 MVP

**Goal**: User taps [Buscar], types query, sees matching sessions as inline buttons

**Independent Test**: Tap [Buscar], type "microsserviços", verify results appear as clickable buttons

### Implementation for User Story 1

- [ ] T009 [US1] Implement _handle_search_action() method in src/cli/daemon.py (send prompt, set awaiting state, start timeout)
- [ ] T010 [US1] Add "search" case to _handle_action_callback() in src/cli/daemon.py calling _handle_search_action()
- [ ] T011 [US1] Implement _start_search_timeout() async method in src/cli/daemon.py (60s timeout with cancellation)
- [ ] T012 [US1] Add text interception in handle_event() to check _awaiting_search_query before routing in src/cli/daemon.py
- [ ] T013 [US1] Implement _process_search_query() method in src/cli/daemon.py (clear state, call SearchService, present results)
- [ ] T014 [P] [US1] Implement build_search_results_keyboard() function in src/services/telegram/keyboards.py with button format "📁 {session_name} ({score:.0%})"
- [ ] T015 [P] [US1] Implement build_no_results_keyboard() function in src/services/telegram/keyboards.py
- [ ] T016 [US1] Implement _present_search_results() method in src/cli/daemon.py (handle results vs no-results cases)

**Checkpoint**: User can search and see results as buttons - US1 independently functional

---

## Phase 4: User Story 2 - Session Restoration (Priority: P1) 🎯 MVP

**Goal**: User taps session button from results, session is restored as active context

**Independent Test**: From search results, tap session button, verify SESSION_ACTIVE keyboard appears and session is usable

### Implementation for User Story 2

- [ ] T017 [US2] Add "search" case to _handle_callback() routing in src/cli/daemon.py for search:select:{id} callbacks
- [ ] T018 [US2] Implement _handle_search_select_callback() method in src/cli/daemon.py (parse session_id, call _restore_session)
- [ ] T019 [US2] Implement _restore_session() method in src/cli/daemon.py (load session, set active, send confirmation with SESSION_ACTIVE keyboard)
- [ ] T020 [US2] Handle "session already active" edge case in _restore_session() in src/cli/daemon.py

**Checkpoint**: Full search-to-restore flow works - US1 + US2 form complete MVP

---

## Phase 5: User Story 3 - No Results Handling (Priority: P2)

**Goal**: When no sessions match, show clear message with recovery options

**Independent Test**: Search for "xyzabc123", verify "Nenhuma sessão encontrada" message + [Nova Busca] [Fechar] buttons

### Implementation for User Story 3

- [ ] T021 [US3] Ensure _present_search_results() shows SEARCH_NO_RESULTS message when results empty in src/cli/daemon.py
- [ ] T022 [US3] Verify [Nova Busca] button callback restarts search flow (reuses action:search handler)
- [ ] T023 [US3] Implement _handle_close_action() method in src/cli/daemon.py (clear state, dismiss message)
- [ ] T024 [US3] Add "close" case to _handle_action_callback() in src/cli/daemon.py

**Checkpoint**: No-results flow complete with recovery options

---

## Phase 6: User Story 4 - Corrupted Session Handling (Priority: P3)

**Goal**: When selected session is corrupted, show error with recovery options

**Independent Test**: Simulate corrupted session (delete metadata), attempt restore, verify error + buttons

### Implementation for User Story 4

- [ ] T025 [US4] Add try/except around session load in _restore_session() in src/cli/daemon.py
- [ ] T026 [US4] Implement error recovery keyboard with [Tentar Novamente] [Fechar] in src/cli/daemon.py
- [ ] T027 [US4] Add SEARCH_SESSION_LOAD_ERROR message to src/lib/messages.py

**Checkpoint**: Corrupted session case handled gracefully

---

## Phase 7: User Story 5 - Search Timeout (Priority: P3)

**Goal**: Auto-cancel search after 60s of inactivity

**Independent Test**: Tap [Buscar], wait 60s without typing, verify timeout message

### Implementation for User Story 5

- [ ] T028 [US5] Verify _start_search_timeout() sends SEARCH_TIMEOUT message after configured seconds in src/cli/daemon.py
- [ ] T029 [US5] Ensure timeout task is cancelled when query received in _process_search_query() in src/cli/daemon.py
- [ ] T030 [US5] Ensure timeout task is cancelled when [Fechar] pressed in _handle_close_action() in src/cli/daemon.py

**Checkpoint**: Timeout handling complete - system never stuck waiting

---

## Phase 8: Tests

**Purpose**: Contract and integration tests for search callback flow

- [ ] T031 [P] Create tests/unit/test_daemon_search.py with unit tests for search state management
- [ ] T032 [P] Add test_search_action_sets_awaiting_state() to tests/unit/test_daemon_search.py
- [ ] T033 [P] Add test_search_query_clears_state() to tests/unit/test_daemon_search.py
- [ ] T034 [P] Add test_search_timeout_clears_state() to tests/unit/test_daemon_search.py
- [ ] T035 Extend tests/integration/test_search_flow.py with callback flow tests
- [ ] T036 Add test_full_search_restore_flow() to tests/integration/test_search_flow.py
- [ ] T037 Add test_search_no_results_flow() to tests/integration/test_search_flow.py
- [ ] T038 Add test_search_corrupted_session_flow() to tests/integration/test_search_flow.py

**Checkpoint**: All test scenarios covered

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, edge cases, cleanup

- [ ] T039 [P] Handle empty query edge case (user sends whitespace) in _process_search_query() in src/cli/daemon.py
- [ ] T040 [P] Add SEARCH_EMPTY_QUERY message to src/lib/messages.py
- [ ] T041 Verify search works during active transcription (independent operations per spec edge case)
- [ ] T042 Run quickstart.md validation manually
- [ ] T043 Update specs/006-semantic-session-search/checklists/requirements.md with implementation status

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - start immediately
- **Foundational (Phase 2)**: Depends on Setup - BLOCKS all user stories
- **User Stories (Phases 3-7)**: All depend on Foundational completion
  - US1 and US2 are both P1 priority - complete both for MVP
  - US3, US4, US5 can proceed in priority order after MVP
- **Tests (Phase 8)**: Can start after Foundational, run in parallel with implementation
- **Polish (Phase 9)**: After desired user stories complete

### User Story Dependencies

| Story | Priority | Depends On | Independently Testable |
|-------|----------|------------|------------------------|
| US1 - Search via Button | P1 | Foundational | ✅ Yes |
| US2 - Session Restoration | P1 | Foundational + US1 | ✅ Yes (given search results) |
| US3 - No Results | P2 | Foundational | ✅ Yes |
| US4 - Corrupted Session | P3 | Foundational + US2 | ✅ Yes (given session to restore) |
| US5 - Timeout | P3 | Foundational | ✅ Yes |

### Parallel Opportunities

**Within Setup (Phase 1)**:
```
T001 ──┬── T002 (parallel)
       └── T003 (parallel)
```

**Within Foundational (Phase 2)**:
```
T004 ──┬── T005
       │   T006 (parallel with T005)
       │   T007 (parallel with T005, T006)
       └── T008 (depends on T006, T007)
```

**Within User Story 1 (Phase 3)**:
```
T009 → T010 → T011 → T012 → T013 → T016
              T014 (parallel with T011-T013)
              T015 (parallel with T011-T014)
```

**Tests (Phase 8)** - all unit tests parallel:
```
T031 ──┬── T032 (parallel)
       ├── T033 (parallel)
       └── T034 (parallel)
T035 → T036 → T037 → T038 (sequential - same file)
```

---

## Summary

| Phase | Tasks | Priority | MVP? |
|-------|-------|----------|------|
| Setup | T001-T003 | - | Required |
| Foundational | T004-T008 | - | Required |
| US1 - Search | T009-T016 | P1 | ✅ |
| US2 - Restore | T017-T020 | P1 | ✅ |
| US3 - No Results | T021-T024 | P2 | |
| US4 - Corrupted | T025-T027 | P3 | |
| US5 - Timeout | T028-T030 | P3 | |
| Tests | T031-T038 | - | Recommended |
| Polish | T039-T043 | - | |

**Total**: 43 tasks  
**MVP scope**: T001-T020 (20 tasks)  
**Parallel opportunities**: 15 tasks can run in parallel
