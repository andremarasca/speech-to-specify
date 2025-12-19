# Implementation Plan: Semantic Session Search

**Branch**: `006-semantic-session-search` | **Date**: 2025-12-19 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/006-semantic-session-search/spec.md`

## Summary

Implement the `action:search` callback handler to enable semantic session search via inline buttons. The flow is 100% button-based: user taps [Buscar] → system prompts for description → user types query → system returns sessions as inline buttons → user taps session → session is restored as active context.

**Key integration**: Connects existing `SearchService` and `EmbeddingIndexer` to the Telegram UI flow via `daemon.py` callback handlers.

## Technical Context

**Language/Version**: Python 3.11  
**Primary Dependencies**: python-telegram-bot, sentence-transformers, pydantic-settings  
**Storage**: File-based session storage (`sessions/` directory)  
**Testing**: pytest (unit, contract, integration)  
**Target Platform**: Linux server / local execution  
**Project Type**: Single project  
**Performance Goals**: Search response < 2s, full flow < 10s (per SC-003)  
**Constraints**: Local embedding model (Constitution Principle VI)  
**Scale/Scope**: Single-user bot, ~100 sessions typical

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | How Addressed |
|-----------|---------------|
| **I. Arquitetura de Contexto Persistente** | ✅ Session restoration loads complete session state; no data lost |
| **II. Excelência Estrutural** | ✅ Search logic in `services/search/`, UI in `services/telegram/`, daemon only routes |
| **III. UX Baseada em Botões Inline** | ✅ [Buscar] exists in RESULTS keyboard; results presented as inline buttons |
| **IV. Integridade dos Testes** | ✅ Contract tests for SearchService exist; add integration test for callback flow |
| **V. Configuração Externa** | ✅ Thresholds in config.py; button labels in messages.py |
| **VI. Soberania dos Dados** | ✅ Uses local sentence-transformers; no external API calls |

**All gates PASS** - no violations requiring justification.

## Project Structure

### Documentation (this feature)

```text
specs/006-semantic-session-search/
├── plan.md              # This file
├── research.md          # Phase 0: technical decisions
├── data-model.md        # Phase 1: new entities (SearchQuery, ConversationalState)
├── quickstart.md        # Phase 1: integration guide
├── contracts/           # Phase 1: callback protocol
│   └── search-callback.md
└── tasks.md             # Phase 2: implementation tasks
```

### Source Code (repository root)

```text
src/
├── models/
│   ├── ui_state.py          # Add KeyboardType.SEARCH_RESULTS (existing file)
│   └── search_result.py     # Already implemented ✅
├── services/
│   ├── search/
│   │   ├── engine.py        # SearchService - already implemented ✅
│   │   └── indexer.py       # EmbeddingIndexer - already implemented ✅
│   └── telegram/
│       ├── keyboards.py     # Add _build_search_results() (existing file)
│       └── ui_service.py    # Add send_search_prompt(), send_search_results() (existing file)
├── cli/
│   └── daemon.py            # Add _handle_search_action(), _handle_search_select() (existing file)
└── lib/
    ├── messages.py          # Add SEARCH_PROMPT, SEARCH_NO_RESULTS (existing file)
    └── config.py            # Add SearchConfig class (existing file)

tests/
├── contract/
│   └── test_search_service.py  # Already exists ✅
├── integration/
│   └── test_search_flow.py     # Already exists - extend with callback tests
└── unit/
    └── test_daemon_search.py   # New: unit tests for search callbacks
```

**Structure Decision**: Single project (Option 1). All changes extend existing files; no new modules required beyond test files.

## Implementation Strategy

### Phase 1: Handler do Botão [Buscar]

1. **Add conversational state tracking in `daemon.py`**:
   - Add `_awaiting_search_query: dict[int, bool]` to track chats awaiting search input
   - Add timeout tracking `_search_timeout_tasks: dict[int, asyncio.Task]`

2. **Implement `_handle_search_action()` in daemon.py**:
   - When user taps [Buscar]: send prompt message, set `_awaiting_search_query[chat_id] = True`
   - Start 60s timeout task

3. **Modify `_handle_text()` to check search state**:
   - If `_awaiting_search_query.get(chat_id)`: process as search query
   - Clear state and cancel timeout after processing

### Phase 2: Processamento da Busca

1. **Add new KeyboardType and builder**:
   - `KeyboardType.SEARCH_RESULTS` in `ui_state.py`
   - `_build_search_results()` in `keyboards.py` with dynamic session buttons

2. **Connect SearchService to callback flow**:
   - Call `search_service.search(query, limit=5, min_score=0.6)`
   - Build inline keyboard with results: `search:select:{session_id}`

3. **Add messages for search flow**:
   - `SEARCH_PROMPT`: "🔍 Descreva o tema da sessão que procura:"
   - `SEARCH_NO_RESULTS`: "Nenhuma sessão encontrada"
   - `SEARCH_RESULT_LABEL`: "📁 {name} ({score:.0%})"

### Phase 3: Seleção e Restauração

1. **Implement `_handle_search_select_callback()`**:
   - Parse `search:select:{session_id}` callback
   - Load session via `session_manager.storage.load()`
   - Set as active: `session_manager.set_active_session()`
   - Send confirmation with SESSION_ACTIVE keyboard

2. **Handle edge cases**:
   - Session already active: confirm without action
   - Session corrupted: show error + [Tentar Novamente] [Fechar]

### Phase 4: Tratamento de Erros

1. **No results**: Show message + [Nova Busca] [Fechar] buttons
2. **Corrupted session**: Detect on load, show error with recovery options
3. **Timeout**: Cancel pending state after 60s, send cancellation message

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| In-memory state tracking | Simple dict per chat_id; daemon is single-instance |
| Limit 5 results | Telegram button limit; UX clarity per spec |
| Score threshold 0.6 | Balance precision/recall; configurable in config.py |
| Dynamic keyboard builder | Results vary; can't use static KeyboardType enum |

## Complexity Tracking

> No Constitution violations. All complexity is justified by feature requirements.

| Aspect | Complexity | Justification |
|--------|------------|---------------|
| Conversational state | Low | Simple dict; cleared on action or timeout |
| Dynamic keyboard | Medium | Required for variable search results |
| Session restoration | Low | Reuses existing SessionManager methods |
