# Tasks: Telegram Contract Fix

**Input**: Design documents from `/specs/001-telegram-contract-fix/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Tests are mandatory for all commands/callbacks and key flows. CI pytest gate required.

**Constitution Compliance (Telegram Interface)**:
- Cobrir mapeamento completo de comandos/callbacks sem handlers órfãos
- Seguir SOLID/Object Calisthenics; evitar condicionais dispersas
- Testes automatizados obrigatórios; falha bloqueia entrega
- Observabilidade e caminhos de recuperação para anomalias/sessões órfãs
- Configuração externa (env/config), nunca hardcoded
- Cada fluxo/teclado testável independentemente, sem testes manuais

## Format: `[ID] [P?] [Story] Description`

## Phase 1: Setup (Shared Infrastructure)

- [x] T001 Atualizar .env.example com SEARCH_TIMEOUT, PAGINATION_PAGE_SIZE, HELP_FALLBACK_ENABLED, ORPHAN_RECOVERY_PROMPT (proj root/.env.example)
- [x] T002 Garantir requirements e dev deps instalados (python-telegram-bot, pytest) em requirements*.txt (requirements.txt, requirements-dev.txt)
- [x] T003 Criar/atualizar doc de execução rápida com comandos de testes obrigatórios (specs/001-telegram-contract-fix/quickstart.md)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Estruturar contratos e testes guarda-chuva antes de histórias.

- [x] T004 Documentar contrato de comandos/callbacks final e sincronizar checklist (specs/001-telegram-contract-fix/contracts/telegram-contracts.md)
- [x] T005 [P] Adicionar testes de mapeamento de comandos para o TelegramBotAdapter/VoiceOrchestrator (tests/unit/test_telegram_event.py)
- [x] T006 [P] Adicionar teste de cobertura de prefixos de callback gerados por keyboards e roteados em `_handle_callback` (tests/unit/test_keyboards.py)
- [x] T007 Configurar job de CI local (comando) que roda suíte obrigatória de pytest (specs/001-telegram-contract-fix/quickstart.md, .github/workflows/ if existente ou docs)
- [x] T036 [P] Auditar/ajustar handlers/teclados/busca/recuperação para ler SEARCH_TIMEOUT, PAGINATION_PAGE_SIZE, HELP_FALLBACK_ENABLED, ORPHAN_RECOVERY_PROMPT etc. de env/config; adicionar pytest que falha se houver literais hardcoded

**Checkpoint**: Fundamentos prontos; histórias podem iniciar.

---

## Phase 3: User Story 1 - Sessão gravar/finalizar confiável (Priority: P1) 🎯 MVP

**Goal**: Sessão de gravação inicia, status e finaliza sem comandos desconhecidos; callbacks de ajuda respondem; transcrição inicia.
**Independent Test**: `/start` → enviar áudios mock → `/status` → `/done`/`/finish` → recebe confirmações; ajuda contextual não quebra.

### Tests for User Story 1
- [x] T008 [P] [US1] Teste contrato de comandos `/start|/done|/finish|/status|/transcripts|/process|/list|/get|/help|/preferences|/session` mapeados no orchestrator (tests/unit/test_telegram_event.py)
- [x] T009 [P] [US1] Teste integração de fluxo gravação→status→finalização com teclados contextuais (tests/integration/test_inline_keyboard_flow.py)

### Implementation for User Story 1
- [x] T010 [P] [US1] Registrar todos os CommandHandlers no TelegramBotAdapter.start() (src/services/telegram/bot.py)
- [x] T011 [US1] Consolidar dicionário `_handle_command` com aliases e fallback “Comando desconhecido” (src/cli/daemon.py)
- [x] T012 [US1] Implementar/ajustar `_cmd_start`, `_cmd_status`, `_cmd_finish` (aliases /done,/finish) com mensagens de produto e teclados (src/cli/daemon.py)
- [x] T013 [US1] Implementar `_cmd_transcripts`, `_cmd_process`, `_cmd_list`, `_cmd_get`, `_cmd_session` com rotas mínimas seguras e logs estruturados (src/cli/daemon.py)
- [x] T014 [US1] Tratar comandos `/help` e `/preferences` como entradas válidas (fallback para histórias 3 onde aplicável) sem erro técnico (src/cli/daemon.py)
- [x] T015 [US1] Garantir acknowledgements de callbacks `action:close_help`, `action:dismiss`, `page:current` via `CallbackQuery.answer()` (src/services/telegram/bot.py)

**Checkpoint**: Gravação e comandos base funcionam e são testáveis.

---

## Phase 4: User Story 2 - Busca e navegação de sessões (Priority: P1)

**Goal**: Busca semântica unificada com callbacks `search:*` e `page:*` roteados com segurança.
**Independent Test**: `/search query` → lista paginada → `search:select:<id>` abre sessão; `page:<n>` navega ou avisa input inválido.

### Tests for User Story 2
- [x] T016 [P] [US2] Teste de mapeamento `/search` e estado “aguardando query” (tests/unit/test_daemon_search.py)
- [x] T017 [P] [US2] Teste de roteamento `search:*` e `page:*` (válido, current, inválido) (tests/unit/test_keyboards.py ou novo teste dedicado)
- [x] T018 [US2] Teste integração fluxo de busca end-to-end com seleção de sessão (tests/integration/test_search_flow.py)

### Implementation for User Story 2
- [x] T019 [P] [US2] Unificar `/search <query>` com `_process_search_query` e fluxo conversacional (src/cli/daemon.py)
- [x] T020 [US2] Implementar `_handle_search_action` para marcar estado aguardando query e orientar usuário (src/cli/daemon.py)
- [x] T021 [US2] Implementar `_handle_search_select_callback` carregando sessão e apresentando resumo/ações (src/cli/daemon.py)
- [x] T022 [US2] Implementar `_handle_page_callback` com ack seguro, parsing int, warning em inválido, TODO de estado de página (src/cli/daemon.py)
- [x] T023 [US2] Garantir keyboards com callbacks `search:select:<id>` e `page:<n>/current` coerentes (src/services/telegram/keyboards.py)
- [x] T037 Simular reinício do daemon no meio da busca; reemitir ou substituir callbacks `search:*` / `page:*` pós-restart sem “Unknown action”; adicionar tests/integration/test_search_restart_flow.py

**Checkpoint**: Busca semântica funcional e segura.

---

## Phase 5: User Story 3 - Recuperação, ajuda e preferências (Priority: P2)

**Goal**: Recuperar sessões órfãs, ajuda contextual/fallback confiável, preferências aplicadas ao UI.
**Independent Test**: Detectar órfã → prompt → `action:resume_session` retoma; `help:<topic>` entrega ajuda ou fallback; `/preferences simple` altera teclados.

### Tests for User Story 3
- [x] T024 [P] [US3] Testes de recuperação de sessão órfã e callbacks `recover:/action:*` (tests/integration/test_crash_recovery_ui.py)
- [x] T025 [P] [US3] Teste de ajuda contextual e fallback quando UIService indisponível (tests/unit/test_keyboards.py ou novo teste) 
- [x] T026 [P] [US3] Teste de preferências aplicando modo simplificado nos teclados (tests/unit/test_keyboards.py)

### Implementation for User Story 3
- [x] T027 [US3] Detectar sessões INTERRUPTED no startup e enviar prompt com teclados de recuperação (src/cli/daemon.py)
- [x] T028 [US3] Implementar handlers `action:resume_session`, `action:finalize_orphan`, `action:discard_orphan` com transições e mensagens de produto (src/cli/daemon.py)
- [x] T029 [US3] Implementar `_handle_help_callback` com map de tópicos + fallback `/help` (src/cli/daemon.py)
- [x] T030 [US3] Ajustar UIService para receber UIPreferences e enviar ajuda contextual (src/services/telegram/ui_service.py)
- [x] T031 [US3] Implementar `/preferences` para setar `simplified` e atualizar ui_service.simplified (src/cli/daemon.py)
- [x] T032 [US3] Atualizar keyboards para refletir modo simplificado conforme UIPreferences (src/services/telegram/keyboards.py)

**Checkpoint**: Recuperação/ajuda/preferências operacionais e testadas.

---

## Phase N: Polish & Cross-Cutting Concerns

 [x] T033 [P] Revisar logs estruturados para callbacks/erros (campos chat_id, session_id, prefix) (src/cli/daemon.py)
 [x] T038 [P] Assertar em pytest logs estruturados para callbacks inválidos/busca falha (campos chat_id, session_id, prefix/error_code)
 [x] T039 [US1] Teste de aceitação: gravação→transcrição→transcrições completa em ≤4 interações e p95 ≤3m (mocks/timestamps) conforme SC-003
 [x] T040 [US2] Teste de aceitação: `/search` abre sessão relevante em ≤2 interações após a lista inicial em 95% dos casos; timeout 5s, page size 5 (SC-004)

---

## Dependencies & Execution Order
- Setup → Foundational → US1 → US2 → US3 → Polish.
- US2 depende de US1 concluída para reusar comandos base e contexto de sessão.
- US3 depende de US1 (sessão/ajuda básica) e se beneficia de US2 para callbacks consistentes, mas pode rodar após US1.

## Parallel Opportunities
- [P] marcados em Foundational (T005, T006) podem rodar em paralelo.
- Dentro de US1: T010 pode ocorrer em paralelo a T015; T012–T014 sequenciais.
- Dentro de US2: T019 pode correr em paralelo a T022–T023; T016–T017 em paralelo.
- Dentro de US3: T027–T028 sequenciais; T030–T032 podem rodar em paralelo após T031.

## Implementation Strategy
- MVP primeiro: complete US1 + testes; valide sem “Unknown command/callback”.
- Depois US2 para busca unificada; só então US3 para recuperação/ajuda/preferências.
- Sempre escrever testes antes/ao lado da implementação correspondente; CI pytest como gate.
