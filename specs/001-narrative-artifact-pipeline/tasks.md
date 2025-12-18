---
description: "Task list for Constituidor de Artefatos Narrativos implementation"
---

# Tasks: Constituidor de Artefatos Narrativos

**Input**: Design documents from `/specs/001-narrative-artifact-pipeline/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅

**Tests**: Constitution requires TDD - tests are written first for behavioral validation.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4, US5)
- Setup/Foundational phases: NO story label
- Include exact file paths in descriptions

## Path Conventions

- **Single project**: `src/`, `tests/` at repository root
- Paths follow plan.md structure

---

## Phase 1: Setup (Project Initialization)

**Purpose**: Establish stable project skeleton with semantic folder structure

- [X] T001 Create project directory structure per plan.md in src/, tests/, prompts/
- [X] T002 [P] Initialize Python project with pyproject.toml and requirements.txt
- [X] T003 [P] Create requirements-dev.txt with pytest, pytest-cov, black, mypy
- [X] T004 [P] Configure .gitignore for Python project (venv, __pycache__, .env, output/)
- [X] T005 [P] Create empty __init__.py files in all src/ and tests/ directories
- [X] T006 [P] Create .env.example with documented environment variables template

**Checkpoint**: Project structure complete, `pip install -r requirements.txt` works ✅

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

### 2.1 Configuration & Utilities

- [X] T007 Create Settings class with pydantic-settings in src/lib/config.py
- [X] T008 [P] Create timestamp utilities (generate_id, generate_timestamp) in src/lib/timestamps.py
- [X] T009 [P] Create exception hierarchy (NarrativeError, LLMError, ValidationError, PersistenceError) in src/lib/exceptions.py
- [X] T010 Unit test for config validation in tests/unit/test_config.py

### 2.2 Domain Models (All Entities)

- [X] T011 [P] Create Input model with validation rules in src/models/input.py
- [X] T012 [P] Create Artifact model with validation rules in src/models/artifact.py
- [X] T013 [P] Create Execution model with status enum and transitions in src/models/execution.py
- [X] T014 [P] Create LLMLog and FailureLog models in src/models/logs.py
- [X] T015 [P] Create src/models/__init__.py exporting all models
- [X] T016 Unit tests for all models in tests/unit/test_models.py

### 2.3 LLM Provider Abstraction (Contract Only)

- [X] T017 Create LLMProvider Protocol and LLMError in src/services/llm/base.py
- [X] T018 Create MockProvider for testing in src/services/llm/mock.py
- [X] T019 [P] Create provider registry (get_provider function) in src/services/llm/__init__.py
- [X] T020 Contract test verifying Protocol compliance in tests/contract/test_llm_provider.py

### 2.4 Persistence Abstraction (Contract + Filesystem Implementation)

- [X] T021 Create ArtifactStore Protocol in src/services/persistence/base.py
- [X] T022 Create LogStore Protocol in src/services/persistence/base.py
- [X] T023 Implement FileArtifactStore in src/services/persistence/artifacts.py
- [X] T024 Implement FileLogStore in src/services/persistence/logs.py
- [X] T025 [P] Create persistence factory in src/services/persistence/__init__.py
- [X] T026 Contract test for ArtifactStore in tests/contract/test_persistence.py
- [X] T027 [P] Contract test for LogStore in tests/contract/test_persistence.py

### 2.5 Prompt Templates

- [X] T028 [P] Create constitution.md prompt template in prompts/constitution.md
- [X] T029 [P] Create specification.md prompt template in prompts/specification.md
- [X] T030 [P] Create planning.md prompt template in prompts/planning.md
- [X] T031 Create PromptLoader utility to load and render templates in src/lib/prompts.py

**Checkpoint**: Foundation ready - models, contracts, persistence work with mock data. `pytest tests/unit tests/contract` passes. ✅

---

## Phase 3: User Story 1 - Processar Texto Caótico em Artefato Estruturado (Priority: P1) 🎯 MVP

**Goal**: Transformar texto desestruturado em cadeia de artefatos narrativos estruturados

**Independent Test**: Fornecer arquivo de texto e verificar que sistema produz 3 artefatos sequenciais (constitution → specification → planning)

### Tests for User Story 1

> **NOTE**: Write tests FIRST, ensure they FAIL before implementation

- [X] T032 [US1] Integration test for complete pipeline execution in tests/integration/test_orchestrator.py
- [X] T033 [P] [US1] Unit test for step sequence validation in tests/unit/test_orchestrator.py

### Implementation for User Story 1

- [X] T034 [US1] Create PipelineStep dataclass defining step contract in src/services/orchestrator.py
- [X] T035 [US1] Create NarrativePipeline class with fixed step sequence in src/services/orchestrator.py
- [X] T036 [US1] Implement execute() method that runs all steps sequentially in src/services/orchestrator.py
- [X] T037 [US1] Implement step execution with artifact creation and persistence in src/services/orchestrator.py
- [X] T038 [US1] Add Input validation (reject empty/whitespace) in src/services/orchestrator.py
- [X] T039 [US1] Create CLI entry point with argparse in src/cli/main.py
- [X] T040 [US1] Implement narrate command reading file and invoking pipeline in src/cli/main.py
- [X] T041 [US1] Add stdout progress output per CLI contract in src/cli/main.py

**Checkpoint**: User Story 1 complete. `python -m src.cli.main sample.txt` produces 3 artifacts in output/. ✅

---

## Phase 4: User Story 2 - Rastrear Toda Interação com LLM (Priority: P1)

**Goal**: Registrar 100% dos prompts e respostas com timestamps para auditoria completa

**Independent Test**: Executar pipeline e verificar que llm_traffic.jsonl contém todas interações

### Tests for User Story 2

- [X] T042 [US2] Integration test verifying all LLM calls logged in tests/integration/test_logging.py
- [X] T043 [P] [US2] Unit test for LLMLog creation with timestamps in tests/unit/test_logs.py

### Implementation for User Story 2

- [X] T044 [US2] Add pre-call logging (prompt + timestamp) to orchestrator in src/services/orchestrator.py
- [X] T045 [US2] Add post-call logging (response + timestamp + latency) to orchestrator in src/services/orchestrator.py
- [X] T046 [US2] Integrate LogStore.append_llm_log in pipeline execution in src/services/orchestrator.py
- [X] T047 [US2] Add --verbose flag showing LLM interaction details in src/cli/main.py

**Checkpoint**: User Story 2 complete. Every LLM call produces entry in llm_traffic.jsonl with timestamps. ✅

---

## Phase 5: User Story 3 - Preservar Artefatos em Falhas (Priority: P2)

**Goal**: Falhas encerram explicitamente preservando todos artefatos até ponto de ruptura

**Independent Test**: Simular falha na etapa 2 e verificar que artefato 1 persiste íntegro

### Tests for User Story 3

- [X] T048 [US3] Integration test for partial failure preservation in tests/integration/test_failure_recovery.py
- [X] T049 [P] [US3] Unit test for FailureLog creation in tests/unit/test_logs.py

### Implementation for User Story 3

- [X] T050 [US3] Add try/except per step with partial state preservation in src/services/orchestrator.py
- [X] T051 [US3] Implement FailureLog creation on exception in src/services/orchestrator.py
- [X] T052 [US3] Ensure artifact persistence happens BEFORE next step starts in src/services/orchestrator.py
- [X] T053 [US3] Update Execution status to 'failed' with error_message on failure in src/services/orchestrator.py
- [X] T054 [US3] Add explicit error output to stderr per CLI contract in src/cli/main.py
- [X] T055 [US3] Implement exit codes per contract (3=validation, 4=LLM, 5=internal) in src/cli/main.py

**Checkpoint**: User Story 3 complete. Failures produce failure.json, preserve partial artifacts, exit with correct code. ✅

---

## Phase 6: User Story 4 - Trocar Provedor de LLM sem Reescrita (Priority: P2)

**Goal**: Adicionar/trocar provedor LLM apenas via configuração, zero mudanças no núcleo

**Independent Test**: Configurar provedor diferente via env var e executar mesma entrada

### Tests for User Story 4

- [X] T056 [US4] Contract test for OpenAI adapter in tests/contract/test_llm_provider.py
- [X] T057 [P] [US4] Contract test for Anthropic adapter in tests/contract/test_llm_provider.py
- [X] T058 [US4] Integration test switching providers via config in tests/integration/test_providers.py

### Implementation for User Story 4

- [X] T059 [US4] Implement OpenAIProvider adapter with httpx in src/services/llm/openai.py
- [X] T060 [P] [US4] Implement AnthropicProvider adapter with httpx in src/services/llm/anthropic.py
- [X] T061 [US4] Add provider selection via Settings.llm_provider in src/services/llm/__init__.py
- [X] T062 [US4] Add --provider CLI flag per contract in src/cli/main.py
- [X] T063 [US4] Add ConfigError exit code (2) for missing API key in src/cli/main.py

**Checkpoint**: User Story 4 complete. `NARRATE_PROVIDER=anthropic python -m src.cli.main sample.txt` works. ✅

---

## Phase 7: User Story 5 - Retomar Contexto Semanas Depois (Priority: P3)

**Goal**: Artefatos auto-documentados com metadados suficientes para compreensão futura

**Independent Test**: Ler artefatos gerados e entender cadeia de raciocínio sem contexto externo

### Tests for User Story 5

- [X] T064 [US5] Unit test verifying artifact metadata completeness in tests/unit/test_models.py
- [X] T065 [P] [US5] Unit test verifying execution.json contains full context in tests/unit/test_models.py

### Implementation for User Story 5

- [X] T066 [US5] Add header metadata (id, date, step, predecessor) to artifact markdown in src/services/persistence/artifacts.py
- [X] T067 [US5] Ensure execution.json includes input_id, timestamps, step count in src/services/persistence/artifacts.py
- [X] T068 [US5] Add artifact file naming with zero-padded step numbers in src/services/persistence/artifacts.py

**Checkpoint**: User Story 5 complete. Artifacts contain self-documenting headers, execution.json provides full context. ✅

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [X] T069 [P] Create README.md with project overview and usage in README.md
- [X] T070 [P] Update quickstart.md with actual commands after implementation in specs/001-narrative-artifact-pipeline/quickstart.md
- [X] T071 Run full quickstart.md validation end-to-end
- [X] T072 [P] Add type hints to all public functions and run mypy
- [X] T073 [P] Run black formatter on all Python files
- [X] T074 Verify determinism: same input produces same artifact sequence (conceptual)
- [X] T075 Security review: verify no API keys in logs or artifacts
- [X] T076 Final integration test: complete pipeline with real LLM (manual)

**Checkpoint**: Project ready for production use. All tests pass, documentation complete. ✅

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1 (Setup) ─────────────────────────────────────────────┐
                                                             │
Phase 2 (Foundational) ──────────────────────────────────────┤
         ⚠️ BLOCKS ALL USER STORIES                          │
                                                             ▼
     ┌───────────────────────────────────────────────────────┤
     │                                                       │
Phase 3 (US1: P1) ───► Phase 4 (US2: P1) ──────────────────►│
     │                                                       │
     └───────────────► Phase 5 (US3: P2) ──────────────────►│
     │                                                       │
     └───────────────► Phase 6 (US4: P2) ──────────────────►│
     │                                                       │
     └───────────────► Phase 7 (US5: P3) ──────────────────►│
                                                             │
                                                             ▼
                                                Phase 8 (Polish)
```

### User Story Dependencies

- **US1 (P1)**: Independent - Can start after Foundational
- **US2 (P1)**: Depends on US1 (needs pipeline to log)
- **US3 (P2)**: Depends on US1 (needs pipeline to fail)
- **US4 (P2)**: Independent of US1-3 (only touches LLM layer)
- **US5 (P3)**: Independent (only touches persistence layer)

### Parallel Opportunities per Phase

**Phase 1**:
```
T002, T003, T004, T005, T006 can run in parallel
```

**Phase 2**:
```
After T007: T008, T009 in parallel
Models T011, T012, T013, T014 in parallel
Contract tests T020, T026, T027 in parallel
Prompts T028, T029, T030 in parallel
```

**Phase 3+** (User Stories):
```
US4 and US5 can be developed in parallel with US2 and US3
Within each story: Tests first, then models, then services
```

---

## Implementation Strategy

### MVP First (User Stories 1 + 2 Only)

1. Complete Phase 1: Setup (~30 min)
2. Complete Phase 2: Foundational (~2 hours)
3. Complete Phase 3: US1 - Pipeline básico (~2 hours)
4. Complete Phase 4: US2 - Logging (~1 hour)
5. **STOP and VALIDATE**: Test with mock provider
6. Demo: `python -m src.cli.main sample.txt` produces artifacts + logs

### Full Implementation

1. MVP (above)
2. Phase 5: US3 - Failure handling (~1 hour)
3. Phase 6: US4 - Real LLM providers (~2 hours)
4. Phase 7: US5 - Metadata enrichment (~1 hour)
5. Phase 8: Polish (~1 hour)

### Suggested Commit Sequence

```
feat: create project structure (T001-T006)
feat: add configuration and utilities (T007-T010)
feat: add domain models (T011-T016)
feat: add LLM provider abstraction (T017-T020)
feat: add persistence layer (T021-T027)
feat: add prompt templates (T028-T031)
feat(us1): implement narrative pipeline (T032-T041)
feat(us2): add LLM interaction logging (T042-T047)
feat(us3): add failure preservation (T048-T055)
feat(us4): add OpenAI and Anthropic providers (T056-T063)
feat(us5): enrich artifact metadata (T064-T068)
docs: finalize documentation (T069-T076)
```

---

## Summary

| Phase | Tasks | Parallelizable | Estimated Time |
|-------|-------|----------------|----------------|
| Setup | T001-T006 | 5/6 | 30 min |
| Foundational | T007-T031 | 15/25 | 2 hours |
| US1 (P1) MVP | T032-T041 | 2/10 | 2 hours |
| US2 (P1) | T042-T047 | 1/6 | 1 hour |
| US3 (P2) | T048-T055 | 1/8 | 1 hour |
| US4 (P2) | T056-T063 | 2/8 | 2 hours |
| US5 (P3) | T064-T068 | 1/5 | 1 hour |
| Polish | T069-T076 | 3/8 | 1 hour |
| **Total** | **76 tasks** | **30 parallel** | **~10 hours** |

---

## Notes

- Tasks without [P] must complete sequentially within their phase
- [US#] labels enable story-level tracking and independent testing
- Each checkpoint validates story works in isolation
- MVP = Phase 1 + 2 + 3 + 4 (Setup + Foundational + US1 + US2)
- Commit after each task or logical group
- TDD enforced: write test → verify fail → implement → verify pass
