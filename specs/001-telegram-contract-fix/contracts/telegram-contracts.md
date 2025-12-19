# Telegram Interface Contracts

## Commands (must be registered in TelegramBotAdapter and routed in VoiceOrchestrator)
- `/start`: cria sessão COLLECTING, responde com instruções e teclados de ações.
- `/done` `/finish`: finaliza sessão ativa, dispara transcrição, confirma processamento.
- `/status`: retorna estado atual e contagem de áudios; teclados contextuais.
- `/transcripts`: apresenta resumo/transcrições da sessão atual/última finalizada.
- `/process`: enfileira sessão para pipeline downstream; confirma sucesso/erro.
- `/list`: lista sessões recentes (limite configurável); fornece callbacks para abrir sessão.
- `/get <id>`: carrega sessão por id; pode delegar para fluxo de `/session`.
- `/session <id|nome>`: seleciona sessão e atualiza contexto de UI.
- `/preferences [simple|normal]`: ajusta modo simplificado; reflete em teclados/mensagens.
- `/search <query>`: executa busca semântica e retorna resultados paginados.
- `/help`: ajuda completa de comandos/fluxos.

## Callback Prefixes and Routing
- `action:` → `_handle_action_callback`
  - `help`, `status`, `view_full`, `pipeline`, `close_help` (ack), `dismiss` (ack), `resume_session`, `finalize_orphan`, `discard_orphan`
- `help:` → `_handle_help_callback`
  - `session`, `empty`, `processing`, `results`, `error`, `default`
- `recover:` → `_handle_recover_callback` (seguindo mesmos alvos de orphan)
- `confirm:` → `_handle_confirm_callback` (reservado; deve responder ou ack)
- `nav:` → `_handle_nav_callback` (reservado para menus; deve responder ou ack)
- `retry:` → `_handle_retry_callback` (reexecuta busca/ação quando aplicável)
- `page:` → `_handle_page_callback`
  - `<n>` (int) muda página; `current` ack silencioso; inválido → warning + manter estado.
- `search:` → `_handle_search_select_callback`
  - `select:<id>` abre sessão resultante; demais valores inválidos → warning + manter estado.

## Error/Unknown Handling (contractual)
- Comando não mapeado: responder com “❓ Comando desconhecido. Use /help para ver opções.”
- Callback prefix não reconhecido: log warning estruturado e responder callback (sem erro visível); manter UI consistente.
- Payload inválido (ex.: `page:abc`): log warning, mensagem amigável opcional, não quebrar fluxo.

## Observability Fields (for structured logging)
- `chat_id`, `command`, `callback_prefix`, `callback_value`, `session_id`, `state_before`, `state_after`, `error_reason`.

## Configuration (external only)
- `SEARCH_TIMEOUT` (default 5s)
- `PAGINATION_PAGE_SIZE` (default 5)
- `HELP_FALLBACK_ENABLED` (default true)
- `ORPHAN_RECOVERY_PROMPT` (default true)
- Tokens/URLs/limits **must** come from env/config, never hardcoded.
