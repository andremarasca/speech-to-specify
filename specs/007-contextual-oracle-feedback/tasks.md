# Tasks: Contextual Oracle Feedback

**Input**: Design documents from `/specs/007-contextual-oracle-feedback/`
**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓, data-model.md ✓, contracts/ ✓

**Tests**: Required by Constitution (Principle III: Integridade de Testes). All behavior contracts (BC-*) must have corresponding tests.

**Constitution Compliance (Telegram Interface)**:
- ✓ Tarefas cobrem mapeamento completo de comandos/callbacks (BC-TC-*)
- ✓ Estrutura segue SOLID (OracleManager, ContextBuilder isolados)
- ✓ Testes automatizados são obrigatórios (contract tests para cada componente)
- ✓ Observabilidade incluída (logging, error handling)
- ✓ Toda configuração é externa (OracleConfig via env vars)
- ✓ Cada fluxo/teclado é testável de forma independente

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and environment configuration

- [ ] T001 Create `prompts/oracles/` directory structure
- [ ] T002 [P] Add OracleConfig to `src/lib/config.py` with ORACLES_DIR, ORACLE_PLACEHOLDER, ORACLE_CACHE_TTL, LLM_TIMEOUT_SECONDS
- [ ] T003 [P] Add sample oracle files: `prompts/oracles/cetico.md`, `prompts/oracles/visionario.md`, `prompts/oracles/otimista.md`
- [ ] T004 Update `.env.example` with new oracle configuration variables

**Checkpoint**: Environment configured, sample oracles available

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core models and entities that ALL user stories depend on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T005 Create Oracle dataclass in `src/models/oracle.py` per data-model.md
- [ ] T006 [P] Create LlmEntry dataclass in `src/models/session.py` (extend existing)
- [ ] T007 [P] Create ContextSnapshot dataclass in `src/models/session.py`
- [ ] T008 Extend UIPreferences with `include_llm_history: bool` in `src/models/ui_state.py`
- [ ] T009 Extend Session with `llm_entries: list[LlmEntry]` in `src/models/session.py`
- [ ] T010 Add `llm_responses/` directory creation to session storage in `src/services/session/storage.py`
- [ ] T011 Add serialization/deserialization for LlmEntry in Session.to_dict() and from_dict()

**Checkpoint**: Foundation ready - all models exist, session can store LLM entries

---

## Phase 3: User Story 1 - Solicitar Feedback de Oráculo (Priority: P1) 🎯 MVP

**Goal**: User can click oracle button after transcription and receive contextual LLM feedback

**Independent Test**: Send audio → see transcription → click oracle button → receive feedback that references transcript content

### Tests for User Story 1

- [ ] T012 [P] [US1] Contract test for ContextBuilder (BC-CB-001 to BC-CB-005) in `tests/contract/test_context_builder_contract.py`
- [ ] T013 [P] [US1] Unit test for prompt injection in `tests/unit/test_prompt_injector.py`
- [ ] T014 [US1] Integration test for oracle feedback flow in `tests/integration/test_oracle_feedback_flow.py`

### Implementation for User Story 1

- [ ] T015 [P] [US1] Create ContextBuilder service in `src/services/llm/context_builder.py` (BC-CB-001 to BC-CB-009)
- [ ] T016 [P] [US1] Create PromptInjector in `src/services/llm/prompt_injector.py` — FR-005: inject context into oracle placeholder (default `{{CONTEXT}}`); fallback: append context at end if placeholder missing
- [ ] T017 [US1] Implement LLM request with timeout in `src/services/llm/oracle_client.py`
- [ ] T018 [US1] Implement response persistence to `llm_responses/` in `src/services/session/storage.py`
- [ ] T019 [US1] Implement oracle callback handler `handle_oracle_callback` in `src/cli/daemon.py` (BC-TC-003, BC-TC-006)
- [ ] T020 [US1] Add typing indicator during LLM request (BC-TC-006)
- [ ] T021 [US1] Wire oracle callback to daemon event loop

**Checkpoint**: US1 complete - user can request and receive oracle feedback with context

---

## Phase 4: User Story 2 - Botões Dinâmicos de Personalidades (Priority: P1) 🎯 MVP

**Goal**: Oracle buttons are dynamically generated from filesystem and appear after transcription

**Independent Test**: Add new .md file to oracles/ → next transcription shows new button

### Tests for User Story 2

- [ ] T022 [P] [US2] Contract test for OracleManager (BC-OM-001 to BC-OM-009) in `tests/contract/test_oracle_manager_contract.py`
- [ ] T023 [P] [US2] Unit test for oracle loader (title extraction) in `tests/unit/test_oracle_loader.py`

### Implementation for User Story 2

- [ ] T024 [P] [US2] Create OracleLoader in `src/services/oracle/loader.py` (markdown parsing, title extraction, ID generation)
- [ ] T025 [US2] Create OracleManager in `src/services/oracle/manager.py` (caching, list_oracles, get_oracle)
- [ ] T026 [US2] Implement `build_oracle_keyboard()` in `src/services/telegram/keyboards.py` (BC-TC-001, BC-TC-002)
- [ ] T027 [US2] Add oracle keyboard to transcription message in `src/cli/daemon.py`
- [ ] T028 [US2] Handle empty oracles directory (BC-OM-005, BC-OM-006, BC-TC-002)
- [ ] T029 [US2] Handle invalid/corrupted oracle files with warning log (BC-OM-004)

**Checkpoint**: US2 complete - dynamic oracle buttons work, new files auto-detected

---

## Phase 5: User Story 3 - Feedback em Espiral com Histórico LLM (Priority: P2)

**Goal**: Subsequent oracle requests include previous LLM responses in context

**Independent Test**: Request feedback from Cético → request from Otimista → verify Otimista's response acknowledges Cético's feedback

### Tests for User Story 3

- [ ] T030 [P] [US3] Contract test for ContextBuilder with LLM history (BC-CB-001, BC-CB-003, BC-CB-004) in `tests/contract/test_context_builder_contract.py`
- [ ] T031 [US3] Integration test for spiral feedback in `tests/integration/test_oracle_feedback_flow.py`

### Implementation for User Story 3

- [ ] T032 [US3] Extend ContextBuilder.build() to include llm_entries when `include_llm_history=True` (BC-CB-001)
- [ ] T033 [US3] Add oracle name delimiter `[ORÁCULO: {name} - {timestamp}]` to context format (BC-CB-008)
- [ ] T034 [US3] Create ContextSnapshot on each oracle request for auditability
- [ ] T035 [US3] Handle missing LLM response files gracefully (BC-CB-007)

**Checkpoint**: US3 complete - LLM responses feed into subsequent contexts

---

## Phase 6: User Story 4 - Configuração de Inclusão de Histórico LLM (Priority: P2)

**Goal**: User can toggle whether LLM responses are included in context

**Independent Test**: Toggle setting OFF → request oracle → verify only transcripts in context (no prior LLM responses)

### Tests for User Story 4

- [ ] T036 [P] [US4] Contract test for toggle behavior in `tests/contract/test_context_builder_contract.py` (BC-CB-002, BC-CB-003, BC-CB-004)
- [ ] T037 [US4] Unit test for preference persistence in `tests/unit/test_ui_preferences.py`

### Implementation for User Story 4

- [ ] T038 [US4] Implement toggle callback handler `handle_toggle_llm_history` in `src/cli/daemon.py` (BC-TC-011)
- [ ] T039 [US4] Add toggle button to oracle keyboard (BC-TC-012)
- [ ] T040 [US4] Persist preference to session metadata
- [ ] T041 [US4] Update button label based on current state ("🔗 Histórico: ON/OFF") (BC-TC-012)
- [ ] T042 [US4] Wire ContextBuilder to respect session preference (BC-CB-003)

**Checkpoint**: US4 complete - user controls LLM history inclusion

---

## Phase 7: User Story 5 - Resiliência a Falhas (Priority: P3)

**Goal**: System continues operating gracefully when subsystems fail

**Independent Test**: Simulate LLM timeout → verify retry button appears → session state intact

### Tests for User Story 5

- [ ] T043 [P] [US5] Unit test for error handling in oracle client `tests/unit/test_oracle_client.py`
- [ ] T044 [US5] Integration test for resilience scenarios `tests/integration/test_oracle_resilience.py`

### Implementation for User Story 5

- [ ] T045 [US5] Implement LLM timeout handling with retry button (BC-TC-007)
- [ ] T046 [US5] Implement LLM error handling with error summary (BC-TC-008)
- [ ] T047 [US5] Handle stale oracle button clicks (BC-TC-005)
- [ ] T048 [US5] Handle session with no transcripts on oracle click (BC-TC-004)
- [ ] T049 [US5] Implement volatile memory mode alert (FR-013, BC-TC-013)
- [ ] T050 [US5] Add structured logging for all error conditions

**Checkpoint**: US5 complete - errors handled gracefully, system resilient

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, cleanup, and final validation

- [ ] T051 Create `docs/tutorial_adding_oracles.md` per Constitution Tutorial requirement
- [ ] T052 Create `docs/tutorial_context_management.md` per Constitution Tutorial requirement
- [ ] T053 Update `README.md` with oracle configuration section
- [ ] T054 Run full test suite and verify all BC-* contracts pass
- [ ] T055 Performance validation: verify <200ms oracle button rendering (SC-001)

**Checkpoint**: Feature complete, documented, tested

---

## Dependencies

```text
Phase 1 (Setup)
    │
    ▼
Phase 2 (Foundation) ──────────────────────────────────────┐
    │                                                       │
    ├──────────────────┬────────────────┐                  │
    ▼                  ▼                ▼                  │
Phase 3 (US1)     Phase 4 (US2)    [Parallel P1 MVPs]     │
    │                  │                                   │
    └──────────────────┴──────────────────┐               │
                                          ▼               │
                          Phase 5 (US3) ◄─────────────────┘
                               │          [Depends on US1 persistence]
                               ▼
                          Phase 6 (US4)
                               │
                               ▼
                          Phase 7 (US5)
                               │
                               ▼
                          Phase 8 (Polish)
```

## Parallel Execution Opportunities

| Phase | Parallel Tasks | Reason |
|-------|----------------|--------|
| Phase 1 | T002, T003 | Different files, no dependencies |
| Phase 2 | T006, T007 | Both in session.py but independent dataclasses |
| Phase 3 | T012, T013, T015, T016 | Tests and services in different files |
| Phase 4 | T022, T023, T024 | Tests and loader in different files |
| Phase 3+4 | T012-T021 ∥ T022-T029 | US1 and US2 are independent P1 stories |
| Phase 5 | T030 | Independent contract test |
| Phase 6 | T036 | Independent contract test |
| Phase 7 | T043 | Independent unit test |

## Summary

| Metric | Value |
|--------|-------|
| **Total Tasks** | 55 |
| **Setup Tasks** | 4 |
| **Foundation Tasks** | 7 |
| **US1 Tasks (P1)** | 10 |
| **US2 Tasks (P1)** | 8 |
| **US3 Tasks (P2)** | 6 |
| **US4 Tasks (P2)** | 7 |
| **US5 Tasks (P3)** | 8 |
| **Polish Tasks** | 5 |
| **Parallelizable** | ~20 tasks with [P] marker |

## MVP Scope (Recommended)

**Minimum Viable Product**: Phase 1 + Phase 2 + Phase 3 + Phase 4

- **Tasks**: T001-T029 (29 tasks)
- **Stories**: US1 + US2 (both P1)
- **Deliverable**: Dynamic oracle buttons + contextual feedback (transcripts only)
- **Value**: User can transform monologue into dialogue with AI personas

**Incremental Delivery**:
1. MVP (US1+US2) → Core value
2. +US3 (spiral feedback) → Enhanced context
3. +US4 (toggle) → User control
4. +US5 (resilience) → Production hardening
