# Telegram Interface Contracts

## Commands (must be registered in TelegramBotAdapter and routed in VoiceOrchestrator)
- `/start`: cria sessão COLLECTING, responde com instruções e teclados de ações. Mensagem inclui atalho para finalizar (`/done`) e visualizar status.
- `/done` `/finish`: aliases com mesma mensagem. Finaliza sessão ativa, dispara transcrição, confirma processamento e informa próximo passo (acesso às transcrições).
- `/status`: retorna estado atual, contagem de áudios e teclados contextuais alinhados ao estado (COLLECTING → finalizar/ajuda; TRANSCRIBING → progresso; TRANSCRIBED/PROCESSED → transcrições/processar).
- `/transcripts`: apresenta resumo/transcrições da sessão atual ou última finalizada; se inexistente, responde “Nenhuma transcrição disponível ainda.”
- `/process`: enfileira sessão para pipeline downstream; confirma sucesso/erro e mantém teclado consistente com o estado pós-enfileiramento.
- `/list`: lista sessões recentes (limite configurável); fornece callbacks para abrir sessão.
- `/get <id>`: carrega sessão por id; pode delegar para fluxo de `/session`.
- `/session <id|nome>`: seleciona sessão e atualiza contexto de UI; em caso de id inválido, responder com aviso amigável e sugestão de `/list`.
- `/preferences [simple|normal]`: ajusta modo simplificado; reflete imediatamente em teclados/mensagens futuras e persiste em storage externo/config.
- `/search <query>`: executa busca semântica e retorna resultados paginados; se sem query, ativa estado “aguardando query” e pede input.
- `/help`: ajuda completa de comandos/fluxos; se UIService indisponível, entregar fallback com principais comandos.
- Unknown command: responder “❓ Comando desconhecido. Use /help para ver opções.” sem log de erro.

## Callback Prefixes and Routing
- `action:` → `_handle_action_callback`
  - `help`, `status`, `view_full`, `pipeline`, `resume_session`, `finalize_orphan`, `discard_orphan` respondem com mensagem/teclado.
  - `close_help`, `dismiss`, `page:current` são **ack-only**: sempre `CallbackQuery.answer()`; limpar teclado quando aplicável; log level=info.
- `help:` → `_handle_help_callback`
  - `session`, `empty`, `processing`, `results`, `error`, `default`; se tópico desconhecido, usar fallback `/help` completo e log warning.
- `recover:` → `_handle_recover_callback`
  - `resume_session`, `finalize_orphan`, `discard_orphan`; se sessão já tratada ou inexistente, responder “Nenhuma sessão órfã encontrada.” e limpar teclados de recuperação.
- `confirm:` → `_handle_confirm_callback` (reservado; deve ao menos ack e log prefixo).
- `nav:` → `_handle_nav_callback` (reservado para menus; ack obrigatório enquanto não implementado).
- `retry:` → `_handle_retry_callback` (reexecuta busca/ação quando aplicável; caso não suportado, responder com mensagem amigável e manter estado).
- `page:` → `_handle_page_callback`
  - `<n>` (int) muda página; `current` ack silencioso; inválido ou não numérico → warning + manter página corrente + mensagem “Página inválida, continue navegando com os botões.”
- `search:` → `_handle_search_select_callback`
  - `select:<id>` abre sessão resultante; demais valores inválidos → warning + manter estado + mensagem “Seleção inválida, escolha um item da lista.”

All callback prefixes must be registered; nenhum callback gerado pelas keyboards pode retornar “Unknown action”.

## Recovery Flows (orphan/INTERRUPTED)
- Detectar sessões `INTERRUPTED` no startup; enviar prompt com teclado de recuperação.
- `action:resume_session`: reativar sessão (estado volta para COLLECTING), confirmar retomada e restaurar teclados de gravação.
- `action:finalize_orphan`: finalizar sessão, iniciar transcrição, confirmar e limpar teclados de recuperação.
- `action:discard_orphan`: descartar sessão, confirmar descarte e limpar teclados de recuperação.
- Se nenhuma sessão órfã for encontrada ao clicar em recuperar, responder “Nenhuma sessão órfã encontrada.” e remover teclados de recuperação.

## Search and Pagination
- `/search <query>` executa busca imediata. Sem query: marcar `awaiting_search_query=true` por chat e pedir “Envie o termo que deseja buscar.”. Limpar flag ao receber a query ou após timeout de 5 minutos.
- Resultados exibem callbacks `search:select:<id>` e paginação `page:<n>` com `PAGINATION_PAGE_SIZE=5`.
- `page:<n>` inválido: warning log, manter lista atual e avisar usuário; `page:current` apenas ack.
- Reinício do daemon: callbacks antigos devem ser aceitos graciosamente; se estado não existir, responder com mensagem de reemissão (“Teclado expirado, envie /search novamente.”).
- Zero resultados: responder “Nenhum resultado encontrado para '<query>'. Tente outro termo ou /help.” e remover teclados de resultado.

## Help and Preferences
- `/help` sempre disponível; se UIService indisponível, enviar fallback com lista de comandos principais e remover teclados órfãos.
- `help:<topic>` entrega ajuda específica; tópico desconhecido cai em fallback `/help` e log warning.
- `/preferences simple|normal` atualiza `UIPreferences.simplified_ui` (storage externo/config) e passa a gerar teclados/mensagens no modo escolhido.

## Error/Unknown Handling (contractual)
- Comando não mapeado: responder com “❓ Comando desconhecido. Use /help para ver opções.”
- Callback prefix não reconhecido: log warning estruturado e responder callback (sem erro visível); manter UI consistente.
- Payload inválido (ex.: `page:abc`): log warning, mensagem amigável e preservar estado atual.
- Stale callbacks pós-restart: responder com aviso e teclado atualizado ou instrução para reenviar comando.

## Observability Fields (for structured logging)
- Campos mínimos: `chat_id`, `command`, `callback_prefix`, `callback_value`, `session_id`, `state_before`, `state_after`, `error_reason`.
- Níveis: info para ack-only; warning para parâmetros inválidos/prefixo desconhecido; error para falha de backend/busca.

## Configuration (external only)
- `SEARCH_TIMEOUT` (default 5s)
- `PAGINATION_PAGE_SIZE` (default 5)
- `HELP_FALLBACK_ENABLED` (default true)
- `ORPHAN_RECOVERY_PROMPT` (default true)
- Tokens/URLs/limits **must** come from env/config, never hardcoded.

## Performance Targets
- Resposta de comandos/callbacks leves: p95 ≤ 800ms.
- Resposta com consulta a storage local (status/list/session/search render): p95 ≤ 2s.
- Busca semântica: timeout 5s; paginação default 5 itens.

## Success Criteria Coverage
- SC-001 (100% comandos sem "Unknown"): coberto por testes de mapeamento e fluxo base (tests/unit/test_telegram_event.py, tests/integration/test_inline_keyboard_flow.py).
- SC-002 (callbacks aceitos/ack): coberto por testes de keyboards/roteamento (tests/unit/test_keyboards.py) e fluxos de busca/paginação.
- SC-003 (gravação→transcrição ≤4 interações, p95 ≤3m com mocks): validar em tests/integration/test_inline_keyboard_flow.py com timestamps/mocks.
- SC-004 (busca abre sessão em ≤2 interações, timeout 5s, page size 5): validar em tests/integration/test_search_flow.py e unit de paginação.
- SC-005 (recuperação de órfãs 100%): validar em tests/integration/test_crash_recovery_ui.py.
- SC-006 (config externa, zero hardcode): validar via testes de configuração/logs (Tasks T036/T038) e auditoria de código.

## Dependencies and Assumptions
- Bot roda em instância única (asyncio); estado de chat (awaiting_search_query) é in-memory por chat, com limpeza após conclusão/timeout (5 minutos).
- Sessions e transcrições em filesystem conforme pipeline atual; UIService pode estar indisponível → fallback de ajuda obrigatório.
- Backend de busca pode falhar/timeout → devolver mensagem amigável e log warning/error.

## Edge Cases
- Callback inválido ou prefixo desconhecido: ack + log warning; manter estado/teclado.
- Stale callback pós-restart: responder com aviso e sugerir comando atualizado.
- Orphan inexistente ou já tratada: responder “Nenhuma sessão órfã encontrada.” e limpar teclados.
- Zero resultados na busca: mensagem amigável + remover teclados.

## Traceability to Tests (planned)
- Mapeamento de comandos/callbacks: tests/unit/test_telegram_event.py, tests/unit/test_keyboards.py.
- Fluxo gravação/status/finalização: tests/integration/test_inline_keyboard_flow.py.
- Busca + paginação + seleção: tests/unit/test_daemon_search.py, tests/integration/test_search_flow.py.
- Recuperação de órfãs e ajuda contextual: tests/integration/test_crash_recovery_ui.py, tests/unit/test_keyboards.py.
- Logs/config externa/asserts de hardcode: tests targeting Tasks T033, T036, T038.
