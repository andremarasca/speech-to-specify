# Tasks: Auto-Session Audio Capture

**Input**: Design documents from `/specs/003-auto-session-audio/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Tests are included as required by constitution (validation coverage gate) and spec (SC-001 through SC-006 require verification).

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3, US4)
- Include exact file paths in descriptions

## Path Conventions

- **Single project**: `src/`, `tests/` at repository root (per plan.md)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Add new dependency and create base modules

- [X] T001 Add sentence-transformers>=2.2.0 to requirements.txt
- [X] T002 [P] Create NameSource enum in src/models/session.py
- [X] T003 [P] Create MatchType enum in src/models/session.py

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T004 Extend Session model with intelligible_name, name_source, embedding fields in src/models/session.py
- [X] T005 Add Session.to_dict() and Session.from_dict() updates for new fields in src/models/session.py
- [X] T006 [P] Create EmbeddingService singleton with lazy loading in src/lib/embedding.py
- [X] T007 [P] Create NameGenerator base interface in src/services/session/name_generator.py
- [X] T008 Implement DefaultNameGenerator with generate_fallback_name() in src/services/session/name_generator.py
- [X] T009 [P] Create SessionMatch dataclass in src/models/session.py
- [X] T010 [P] Create SessionMatcher base interface in src/services/session/matcher.py
- [X] T011 Update SessionStorage to support session index in src/services/session/storage.py
- [X] T012 Unit test for NameSource and MatchType enums in tests/unit/test_session.py

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - Audio Triggers Session Creation (Priority: P1) 🎯 MVP

**Goal**: When user sends audio without active session, system auto-creates session and preserves audio with zero data loss.

**Independent Test**: Send audio when no session active → audio preserved, session created, user notified with session name.

### Tests for User Story 1

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T013 [P] [US1] Contract test for handle_audio_receipt() in tests/contract/test_auto_session_handler.py
- [X] T014 [P] [US1] Contract test for get_or_create_session() in tests/contract/test_auto_session_handler.py
- [X] T015 [P] [US1] Integration test for audio→session flow in tests/integration/test_auto_session.py

### Implementation for User Story 1

- [X] T016 [US1] Implement get_or_create_session() in src/services/session/manager.py
- [X] T017 [US1] Implement handle_audio_receipt() with temp-persist-first pattern in src/services/session/manager.py
- [X] T018 [US1] Create AudioPersistenceError exception in src/lib/exceptions.py
- [X] T019 [US1] Update _handle_voice() in src/services/telegram/bot.py to call handle_audio_receipt()
- [X] T020 [US1] Update voice handler confirmation message to include session intelligible_name in src/services/telegram/bot.py
- [X] T021 [US1] Add logging for auto-session creation events in src/services/session/manager.py

**Checkpoint**: User Story 1 complete - audio without session creates session, zero data loss verified

---

## Phase 4: User Story 2 - Intelligible Session Names (Priority: P2)

**Goal**: Sessions display human-readable names derived from content (transcription or fallback timestamp).

**Independent Test**: Create session → process audio → list sessions → see content-derived name instead of ID.

### Tests for User Story 2

- [X] T022 [P] [US2] Contract test for NameGenerator in tests/contract/test_name_generator.py
- [X] T023 [P] [US2] Unit test for generate_fallback_name() all 12 months in tests/unit/test_name_generator.py
- [X] T024 [P] [US2] Unit test for generate_from_transcript() filler filtering in tests/unit/test_name_generator.py
- [X] T025 [P] [US2] Unit test for ensure_unique() suffix behavior in tests/unit/test_name_generator.py

### Implementation for User Story 2

- [X] T026 [US2] Implement generate_from_transcript() in src/services/session/name_generator.py
- [X] T027 [US2] Implement generate_from_llm_output() in src/services/session/name_generator.py
- [X] T028 [US2] Implement ensure_unique() in src/services/session/name_generator.py
- [X] T029 [US2] Implement update_session_name() with priority logic in src/services/session/manager.py
- [X] T030 [US2] Hook transcription completion to trigger name update in src/services/session/processor.py
- [X] T031 [US2] Update /list command to display intelligible_name in src/services/telegram/bot.py

**Checkpoint**: User Story 2 complete - sessions show content-derived names

---

## Phase 5: User Story 3 - Natural Language Session Reference (Priority: P3)

**Goal**: Users reference sessions by description ("monthly report") and system resolves to correct session.

**Independent Test**: Create multiple sessions → reference by partial name → correct session activated.

### Tests for User Story 3

- [X] T032 [P] [US3] Contract test for SessionMatcher.resolve() in tests/contract/test_session_matcher.py
- [X] T033 [P] [US3] Unit test for exact substring matching in tests/unit/test_session_matcher.py
- [X] T034 [P] [US3] Unit test for fuzzy matching (Levenshtein) in tests/unit/test_session_matcher.py
- [X] T035 [P] [US3] Unit test for semantic similarity matching in tests/unit/test_session_matcher.py
- [X] T036 [P] [US3] Unit test for ambiguity detection in tests/unit/test_session_matcher.py

### Implementation for User Story 3

- [X] T037 [US3] Implement rebuild_index() in src/services/session/matcher.py
- [X] T038 [US3] Implement exact substring matching in resolve() in src/services/session/matcher.py
- [X] T039 [US3] Implement fuzzy substring matching (Levenshtein ≤2) in resolve() in src/services/session/matcher.py
- [X] T040 [US3] Implement semantic similarity matching in resolve() in src/services/session/matcher.py
- [X] T041 [US3] Implement update_session() and remove_session() in src/services/session/matcher.py
- [X] T042 [US3] Hook SessionMatcher to session create/update/delete events in src/services/session/manager.py
- [X] T043 [US3] Implement /session command with natural language reference in src/cli/daemon.py
- [X] T044 [US3] Implement ambiguity response (present candidates) in src/cli/daemon.py

**Checkpoint**: User Story 3 complete - natural language references resolve to sessions

---

## Phase 6: User Story 4 - Context Commands Without Session Specification (Priority: P3)

**Goal**: Commands like "transcription" apply to active session without explicit reference.

**Independent Test**: Activate session → run /transcripts without args → returns active session transcripts.

### Tests for User Story 4

- [X] T045 [P] [US4] Integration test for context-free /transcripts in tests/integration/test_auto_session.py
- [X] T046 [P] [US4] Integration test for context-free command with no active session in tests/integration/test_auto_session.py

### Implementation for User Story 4

- [X] T047 [US4] Update /transcripts to use active session when no arg in src/cli/daemon.py
- [X] T048 [US4] Update /status to use active session when no arg in src/cli/daemon.py
- [X] T049 [US4] Add "no active session" clarification response in src/cli/daemon.py

**Checkpoint**: User Story 4 complete - commands use active session context

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [X] T050 [P] Add EmbeddingService model download to setup/first-run script (Note: lazy-loaded on first use)
- [X] T051 [P] Update quickstart.md with actual test commands in specs/003-auto-session-audio/quickstart.md
- [X] T052 Run quickstart.md validation checklist
- [X] T053 [P] Add docstrings to all new public methods
- [X] T054 Performance: verify session creation <2s (SC-005) - verified: 4ms

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-6)**: All depend on Foundational phase completion
  - Can proceed sequentially in priority order (P1 → P2 → P3)
  - US3 and US4 are both P3, can run in parallel after US2
- **Polish (Phase 7)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: After Foundational - MVP, no dependencies on other stories
- **User Story 2 (P2)**: After Foundational - Provides names for US3 matching
- **User Story 3 (P3)**: After US2 (needs intelligible names to match against)
- **User Story 4 (P3)**: After Foundational - Independent of US2/US3

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Foundation components before dependent services
- Core implementation before bot integration
- Story complete before moving to next priority

### Parallel Opportunities

**Phase 1 (Setup)**:
```
T002 [P] Create NameSource enum
T003 [P] Create MatchType enum
```

**Phase 2 (Foundational)**:
```
T006 [P] Create EmbeddingService
T007 [P] Create NameGenerator interface
T009 [P] Create SessionMatch dataclass
T010 [P] Create SessionMatcher interface
```

**User Story 1 Tests**:
```
T013 [P] Contract test handle_audio_receipt
T014 [P] Contract test get_or_create_session
T015 [P] Integration test audio→session
```

**User Story 2 Tests**:
```
T022 [P] Contract test NameGenerator
T023 [P] Unit test fallback names
T024 [P] Unit test transcript extraction
T025 [P] Unit test uniqueness
```

**User Story 3 Tests**:
```
T032-T036 [P] All SessionMatcher tests
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001-T003)
2. Complete Phase 2: Foundational (T004-T012)
3. Complete Phase 3: User Story 1 (T013-T021)
4. **STOP and VALIDATE**: Send audio without session, verify session created
5. Deploy/demo - users can now send audio without pre-starting sessions

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. Add User Story 1 → **MVP!** Zero data loss achieved
3. Add User Story 2 → Sessions have readable names
4. Add User Story 3 → Natural language session lookup
5. Add User Story 4 → Implicit context commands
6. Polish → Production-ready

---

## Task Count Summary

| Phase | Task Count | Parallel Tasks |
|-------|------------|----------------|
| Setup | 3 | 2 |
| Foundational | 9 | 5 |
| User Story 1 | 9 | 3 |
| User Story 2 | 10 | 4 |
| User Story 3 | 13 | 5 |
| User Story 4 | 5 | 2 |
| Polish | 5 | 3 |
| **Total** | **54** | **24** |

---

## Notes

- [P] tasks = different files, no dependencies within same phase
- [US#] label maps task to specific user story
- US1 is the MVP - delivers core value (zero data loss)
- US3 depends on US2 for content-derived names
- US4 is independent and can be done in parallel with US3
- All tests use pytest with existing contract/integration/unit structure
- Commit after each task or logical group
