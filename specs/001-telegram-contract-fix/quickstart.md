# Quickstart – Telegram Contract Fix

1) **Instalar dependências**
```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

2) **Configurar ambiente**
- Defina variáveis no `.env` (exemplos):
  - `TELEGRAM_BOT_TOKEN=<token>`
  - `TELEGRAM_ALLOWED_CHAT_ID=<chat>`
  - `SEARCH_TIMEOUT=5` (segundos)
  - `PAGINATION_PAGE_SIZE=5`
  - `HELP_FALLBACK_ENABLED=true`
  - `ORPHAN_RECOVERY_PROMPT=true`

3) **Rodar daemon do bot**
```bash
python -m src.cli.daemon --verbose
```

4) **Testes obrigatórios (constituição)**
```bash
pytest tests/unit/test_keyboards.py -v
pytest tests/unit/test_daemon_search.py -v
pytest tests/unit/test_telegram_event.py -v
pytest tests/integration/test_inline_keyboard_flow.py -v
pytest tests/integration/test_search_flow.py -v
pytest tests/integration/test_crash_recovery_ui.py -v
# Comando único para CI/local gate
pytest tests/unit tests/integration -v
```
- Adicione novos testes de contrato para mapeamento de comandos/callbacks ao introduzir novos botões/comandos.

5) **Fluxos para validar MVP**
- `/start` → enviar áudios → `/status` → `/done` → acompanhar transcrição.
- `/search <query>` ou botão “Buscar” → ver resultados paginados → `search:select:<id>` → abrir sessão.
- Reiniciar daemon com sessão ativa → receber prompt de recuperação → `action:resume_session` → continuar.
- `/help` e `help:<topic>` → verificar ajuda contextual e fallback.
- `/preferences simple` → confirmar teclados em modo simplificado.
