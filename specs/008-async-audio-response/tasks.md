```markdown
# Tasks: Async Audio Response Pipeline

**Input**: Design documents from `/specs/008-async-audio-response/`
**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓, data-model.md ✓, contracts/tts-service.md ✓

**Tests**: Required per constitution. Testes de orquestração, síntese e persistência são obrigatórios; falha invalida entrega (regra binária).

**Constitution Compliance (Orquestrador de Resposta Multimodal)**:
- ✅ Tarefas de síntese operam assincronamente, sem bloquear canal textual
- ✅ Serviço de síntese é idempotente, com contratos de interface SOLID
- ✅ Testes de orquestração, síntese e persistência incluídos (obrigatórios)
- ✅ Toda configuração externa; hardcoding proibido
- ✅ Tarefas de garbage collection incluídas para ciclo de vida de áudio
- ✅ Tutorial de extensibilidade incluído na fase de documentação

**Organization**: Tasks grouped by user story for independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4)
- Exact file paths included in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization, configuration and models

- [ ] T001 Add `edge-tts>=6.1.0` to requirements.txt
- [ ] T002 [P] Add TTS environment variables to .env.example with documentation
- [ ] T003 [P] Create TTSConfig class in src/lib/config.py with env bindings (TTS_ENABLED, TTS_VOICE, TTS_FORMAT, TTS_TIMEOUT_SECONDS, TTS_MAX_TEXT_LENGTH, TTS_GC_RETENTION_HOURS, TTS_GC_MAX_STORAGE_MB)
- [ ] T004 Create `get_tts_config()` factory function in src/lib/config.py
- [ ] T005 [P] Create TTS models in src/models/tts.py (TTSRequest, TTSResult, TTSArtifact dataclasses)
- [ ] T006 [P] Create src/services/tts/__init__.py with module exports

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core TTS service infrastructure that ALL user stories depend on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T007 Create TTSService abstract base class in src/services/tts/base.py (synthesize, check_health, get_artifact_path methods)
- [ ] T008 [P] Create TextSanitizer in src/services/tts/text_sanitizer.py (strip_markdown, strip_special_characters - reference .local/edge_tts_generate.py)
- [ ] T009 [P] Create MockTTSService in src/services/tts/mock_service.py for testing
- [ ] T010 Create EdgeTTSService implementation in src/services/tts/edge_tts_service.py (implement synthesize, check_health, get_artifact_path)

**Checkpoint**: Foundation ready - TTS service can be instantiated and health-checked

---

## Phase 3: User Story 1 - Receber Resposta em Áudio Sob Demanda (Priority: P1) 🎯 MVP

**Goal**: Usuário recebe texto imediatamente, áudio disponível assincronamente após síntese

**Independent Test**: Enviar mensagem ao bot, verificar (1) texto imediato (2) áudio disponível em <30s

### Tests for User Story 1

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T011 [P] [US1] Unit test for text sanitization in tests/unit/test_text_sanitizer.py (markdown removal, special chars)
- [ ] T012 [P] [US1] Contract test for TTSService.synthesize() in tests/contract/test_tts_service_contract.py (BC-TTS-001 through BC-TTS-004)
- [ ] T013 [P] [US1] Unit test for TTSConfig validation in tests/unit/test_tts_config.py

### Implementation for User Story 1

- [ ] T014 [US1] Implement idempotency check in EdgeTTSService.synthesize() - return cached TTSResult if file exists (BC-TTS-002)
- [ ] T015 [US1] Implement async synthesis with timeout in EdgeTTSService.synthesize() using asyncio.wait_for (BC-TTS-001)
- [ ] T016 [US1] Implement error isolation in EdgeTTSService - catch all exceptions, return TTSResult.error() (BC-TTS-003)
- [ ] T017 [US1] Add `_synthesize_and_send_audio()` method to TelegramDaemon in src/cli/daemon.py
- [ ] T018 [US1] Integrate TTS trigger in `_handle_oracle_callback()` after bot.send_message() using asyncio.create_task()
- [ ] T019 [US1] Implement bot.send_voice() notification when synthesis completes successfully

**Checkpoint**: User Story 1 complete - text arrives immediately, audio follows asynchronously

---

## Phase 4: User Story 2 - Resiliência a Falhas no Pipeline de Áudio (Priority: P2)

**Goal**: Falhas no TTS nunca impactam entrega de texto; usuário recebe feedback sobre indisponibilidade

**Independent Test**: Simular falha de síntese, verificar que chat textual permanece funcional

### Tests for User Story 2

- [ ] T020 [P] [US2] Contract test for error isolation in tests/contract/test_tts_service_contract.py (BC-TTS-003)
- [ ] T021 [P] [US2] Integration test for graceful degradation in tests/integration/test_tts_integration.py

### Implementation for User Story 2

- [ ] T022 [US2] Add try/except wrapper in `_synthesize_and_send_audio()` - never propagate exceptions
- [ ] T023 [US2] Implement logging for synthesis failures with context (session_id, oracle, duration)
- [ ] T024 [US2] Add user notification when TTS fails ("Áudio não disponível nesta resposta")
- [ ] T025 [US2] Add TTSService health check during daemon startup, log warning if unhealthy

**Checkpoint**: User Story 2 complete - TTS failures gracefully handled, text delivery never impacted

---

## Phase 5: User Story 3 - Gerenciamento de Ciclo de Vida de Artefatos (Priority: P3)

**Goal**: Garbage collection automática de arquivos TTS antigos segundo política configurável

**Independent Test**: Gerar arquivos TTS, aguardar expiração, verificar remoção automática

### Tests for User Story 3

- [ ] T026 [P] [US3] Unit test for TTSArtifact.is_expired() in tests/unit/test_tts_models.py
- [ ] T027 [P] [US3] Integration test for garbage collection in tests/integration/test_tts_gc.py

### Implementation for User Story 3

- [ ] T028 [US3] Create TTSGarbageCollector class in src/services/tts/garbage_collector.py
- [ ] T029 [US3] Implement collect() method - scan sessions/*/audio/tts/, remove expired files
- [ ] T030 [US3] Implement storage limit check - remove oldest files if TTS_GC_MAX_STORAGE_MB exceeded
- [ ] T031 [US3] Add GC trigger in daemon startup or periodic background task

**Checkpoint**: User Story 3 complete - TTS artifacts automatically cleaned up

---

## Phase 6: User Story 4 - Idempotência na Geração de Áudio (Priority: P3)

**Goal**: Sínteses repetidas para mesmo texto retornam artefato existente sem reprocessar

**Independent Test**: Solicitar síntese do mesmo texto 2x, verificar apenas 1 arquivo criado

### Tests for User Story 4

- [ ] T032 [P] [US4] Contract test for idempotency in tests/contract/test_tts_service_contract.py (BC-TTS-002)
- [ ] T033 [P] [US4] Unit test for TTSRequest.idempotency_key in tests/unit/test_tts_models.py

### Implementation for User Story 4

- [ ] T034 [US4] Verify idempotency_key generation includes session_id, oracle_id, text hash
- [ ] T035 [US4] Implement concurrent request handling - use file lock or async lock to prevent duplicate synthesis

**Checkpoint**: User Story 4 complete - duplicate requests return cached artifacts

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, validation, and final improvements

- [ ] T036 [P] Create docs/tutorial_tts_extensibility.md (required per constitution)
- [ ] T037 [P] Update .env.example with all TTS variables and documentation
- [ ] T038 [P] Add docstrings to all public methods in src/services/tts/
- [ ] T039 Run quickstart.md validation (4 verification steps)
- [ ] T040 Verify all tests pass: pytest tests/unit/test_tts*.py tests/contract/test_tts*.py tests/integration/test_tts*.py

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-6)**: All depend on Foundational phase completion
  - US1 (P1) can proceed immediately after Foundational
  - US2 (P2) can proceed in parallel with US1 (different files)
  - US3 (P3) and US4 (P3) can proceed in parallel after US1/US2
- **Polish (Phase 7)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - Core MVP
- **User Story 2 (P2)**: Can start after Foundational (Phase 2) - Independent of US1
- **User Story 3 (P3)**: Can start after Foundational (Phase 2) - Independent garbage collection
- **User Story 4 (P3)**: Can start after US1 T014 (idempotency check implemented in US1)

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Foundation services before integration
- Core implementation before daemon integration
- Story complete before moving to next priority

### Parallel Opportunities

**Phase 1 (Setup)**:
```bash
# Launch in parallel:
T002 .env.example
T003 TTSConfig
T005 TTS models
T006 __init__.py
```

**Phase 2 (Foundational)**:
```bash
# After T007 completes, launch in parallel:
T008 TextSanitizer
T009 MockTTSService
```

**User Story 1 Tests**:
```bash
# Launch all tests in parallel:
T011 test_text_sanitizer.py
T012 test_tts_service_contract.py
T013 test_tts_config.py
```

**Cross-Story Parallel**:
```bash
# After Foundational, can work on US1 and US2 simultaneously:
Developer A: US1 (T011-T019)
Developer B: US2 (T020-T025)
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001-T006)
2. Complete Phase 2: Foundational (T007-T010)
3. Complete Phase 3: User Story 1 (T011-T019)
4. **STOP and VALIDATE**: 
   - Run quickstart.md verification steps 1-4
   - Send message to bot, verify text immediate + audio follows
5. Deploy/demo if ready

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. Add User Story 1 → **MVP!** Multimodal response working
3. Add User Story 2 → Resilient to TTS failures
4. Add User Story 3 → Storage managed automatically
5. Add User Story 4 → Optimized resource usage
6. Polish → Production ready

### Success Criteria Mapping

| Success Criteria | User Story | Verified By |
|------------------|------------|-------------|
| SC-001: Audio <30s | US1 | quickstart.md step 4 |
| SC-002: Zero text delay | US1, US2 | Integration test |
| SC-003: <1% failed audio | US2 | Error logging |
| SC-004: 1 action to play | US1 | UX test |
| SC-005: 99% idempotency | US4 | Contract test |
| SC-006: Storage limit | US3 | GC integration test |
| SC-007: <5s recovery | US2 | Health check |

---

## Reference Files

| Reference | Purpose |
|-----------|---------|
| `.local/edge_tts_generate.py` | Working TTS example with sanitization |
| `src/cli/daemon.py:~1017` | Integration point in `_handle_oracle_callback()` |
| `src/services/oracle/` | Pattern for service module structure |
| `specs/008-async-audio-response/contracts/tts-service.md` | TTSService interface contract |

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story independently completable and testable
- Verify tests fail before implementing
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Reference `.local/edge_tts_generate.py` for proven TTS patterns
```
