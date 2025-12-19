# Quickstart: Semantic Session Search

**Feature**: 006-semantic-session-search  
**Date**: 2025-12-19

## Overview

This guide explains how to integrate the semantic session search feature into the existing Telegram bot.

## Prerequisites

- Existing `SearchService` implementation (`src/services/search/engine.py`)
- Existing `SessionManager` with storage (`src/services/session/manager.py`)
- Existing `UIService` and keyboards (`src/services/telegram/`)
- Working Telegram bot with callback handling (`src/cli/daemon.py`)

## Integration Steps

### Step 1: Add Configuration

Add to `src/lib/config.py`:

```python
class SearchConfig(BaseSettings):
    """Configuration for semantic search."""
    
    min_similarity_score: float = Field(
        default=0.6,
        alias="SEARCH_MIN_SCORE",
    )
    
    max_results: int = Field(
        default=5,
        alias="SEARCH_MAX_RESULTS",
    )
    
    query_timeout_seconds: int = Field(
        default=60,
        alias="SEARCH_QUERY_TIMEOUT",
    )

def get_search_config() -> SearchConfig:
    return SearchConfig()
```

### Step 2: Add Messages

Add to `src/lib/messages.py`:

```python
# Search Flow
SEARCH_PROMPT = "🔍 Descreva o tema da sessão que procura:"
SEARCH_PROMPT_SIMPLIFIED = "Descreva o tema da sessão que procura:"

SEARCH_RESULTS_HEADER = "📋 Sessões encontradas:"
SEARCH_RESULTS_HEADER_SIMPLIFIED = "Sessões encontradas:"

SEARCH_NO_RESULTS = "❌ Nenhuma sessão encontrada.\n\nTente descrever de outra forma."
SEARCH_NO_RESULTS_SIMPLIFIED = "Nenhuma sessão encontrada."

SEARCH_SESSION_RESTORED = "✅ Sessão *{session_name}* restaurada.\n\n🎙️ {audio_count} áudio(s)"
SEARCH_SESSION_RESTORED_SIMPLIFIED = "Sessão {session_name} restaurada. {audio_count} áudio(s)"

SEARCH_TIMEOUT = "⏰ Busca cancelada por inatividade."
SEARCH_TIMEOUT_SIMPLIFIED = "Busca cancelada por inatividade."

BUTTON_NEW_SEARCH = "🔄 Nova Busca"
BUTTON_NEW_SEARCH_SIMPLIFIED = "Nova Busca"
```

### Step 3: Add KeyboardType

Add to `src/models/ui_state.py`:

```python
class KeyboardType(str, Enum):
    # ... existing ...
    SEARCH_RESULTS = "SEARCH_RESULTS"
    SEARCH_NO_RESULTS = "SEARCH_NO_RESULTS"
```

### Step 4: Add Keyboard Builder

Add to `src/services/telegram/keyboards.py`:

```python
from src.models.search_result import SearchResult

def build_search_results_keyboard(
    results: list[SearchResult],
    simplified: bool = False,
) -> InlineKeyboardMarkup:
    """Build keyboard for search results with dynamic session buttons."""
    buttons = []
    
    for result in results:
        if simplified:
            label = f"{result.session_name} ({result.relevance_score:.0%})"
        else:
            label = f"📁 {result.session_name} ({result.relevance_score:.0%})"
        
        callback_data = f"search:select:{result.session_id}"
        buttons.append([InlineKeyboardButton(label, callback_data=callback_data)])
    
    # Footer row
    new_search = BUTTON_NEW_SEARCH_SIMPLIFIED if simplified else BUTTON_NEW_SEARCH
    close = BUTTON_CLOSE_SIMPLIFIED if simplified else BUTTON_CLOSE
    buttons.append([
        InlineKeyboardButton(new_search, callback_data="action:search"),
        InlineKeyboardButton(close, callback_data="action:close"),
    ])
    
    return InlineKeyboardMarkup(buttons)


def build_no_results_keyboard(simplified: bool = False) -> InlineKeyboardMarkup:
    """Build keyboard for no search results."""
    new_search = BUTTON_NEW_SEARCH_SIMPLIFIED if simplified else BUTTON_NEW_SEARCH
    close = BUTTON_CLOSE_SIMPLIFIED if simplified else BUTTON_CLOSE
    
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(new_search, callback_data="action:search"),
            InlineKeyboardButton(close, callback_data="action:close"),
        ]
    ])
```

### Step 5: Add Daemon State and Handlers

Add to `VoiceOrchestrator.__init__()`:

```python
def __init__(self, ...):
    # ... existing ...
    self._awaiting_search_query: dict[int, bool] = {}
    self._search_timeout_tasks: dict[int, asyncio.Task] = {}
    self.search_service = search_service  # Inject via constructor
    self.search_config = get_search_config()
```

Add action handler:

```python
async def _handle_action_callback(self, event: TelegramEvent, action: str) -> None:
    # ... existing handlers ...
    elif action == "search":
        await self._handle_search_action(event)
    elif action == "close":
        await self._handle_close_action(event)
```

Implement search handlers:

```python
async def _handle_search_action(self, event: TelegramEvent) -> None:
    """Handle [Buscar] button tap."""
    chat_id = event.chat_id
    
    # Set awaiting state
    self._awaiting_search_query[chat_id] = True
    
    # Start timeout
    await self._start_search_timeout(chat_id)
    
    # Send prompt
    prompt = SEARCH_PROMPT_SIMPLIFIED if self._simplified_ui else SEARCH_PROMPT
    await self.bot.send_message(chat_id, prompt)


async def _start_search_timeout(self, chat_id: int) -> None:
    """Start timeout task for search query."""
    # Cancel existing
    if chat_id in self._search_timeout_tasks:
        self._search_timeout_tasks[chat_id].cancel()
    
    async def timeout():
        await asyncio.sleep(self.search_config.query_timeout_seconds)
        if self._awaiting_search_query.pop(chat_id, False):
            msg = SEARCH_TIMEOUT_SIMPLIFIED if self._simplified_ui else SEARCH_TIMEOUT
            await self.bot.send_message(chat_id, msg)
    
    self._search_timeout_tasks[chat_id] = asyncio.create_task(timeout())


async def _process_search_query(self, event: TelegramEvent, query: str) -> None:
    """Process search query text."""
    chat_id = event.chat_id
    
    # Clear state
    self._awaiting_search_query.pop(chat_id, None)
    if chat_id in self._search_timeout_tasks:
        self._search_timeout_tasks[chat_id].cancel()
        del self._search_timeout_tasks[chat_id]
    
    # Execute search
    response = self.search_service.search(
        query=query,
        chat_id=chat_id,
        limit=self.search_config.max_results,
        min_score=self.search_config.min_similarity_score,
    )
    
    if response.results:
        keyboard = build_search_results_keyboard(
            response.results,
            simplified=self._simplified_ui,
        )
        header = SEARCH_RESULTS_HEADER_SIMPLIFIED if self._simplified_ui else SEARCH_RESULTS_HEADER
        await self.bot.send_message(chat_id, header, reply_markup=keyboard)
    else:
        keyboard = build_no_results_keyboard(simplified=self._simplified_ui)
        msg = SEARCH_NO_RESULTS_SIMPLIFIED if self._simplified_ui else SEARCH_NO_RESULTS
        await self.bot.send_message(chat_id, msg, reply_markup=keyboard)
```

Add callback routing:

```python
async def _handle_callback(self, event: TelegramEvent) -> None:
    # ... existing routing ...
    elif callback_action == "search":
        await self._handle_search_select_callback(event, callback_value)


async def _handle_search_select_callback(self, event: TelegramEvent, session_id: str) -> None:
    """Handle session selection from search results."""
    chat_id = event.chat_id
    
    try:
        session = self.session_manager.storage.load(session_id)
        self.session_manager.set_active_session(session)
        
        msg = SEARCH_SESSION_RESTORED.format(
            session_name=session.intelligible_name,
            audio_count=session.audio_count,
        )
        keyboard = build_keyboard(KeyboardType.SESSION_ACTIVE, simplified=self._simplified_ui)
        await self.bot.send_message(chat_id, msg, parse_mode="Markdown", reply_markup=keyboard)
        
    except Exception as e:
        logger.error(f"Failed to restore session {session_id}: {e}")
        keyboard = build_no_results_keyboard(simplified=self._simplified_ui)
        await self.bot.send_message(
            chat_id,
            "❌ Erro ao carregar sessão.",
            reply_markup=keyboard,
        )
```

Modify text handler:

```python
async def _handle_text(self, event: TelegramEvent) -> None:
    """Handle text message - check for search query first."""
    chat_id = event.chat_id
    text = event.text.strip() if event.text else ""
    
    # Check if awaiting search query
    if self._awaiting_search_query.get(chat_id):
        if text:
            await self._process_search_query(event, text)
        else:
            # Empty text while awaiting - prompt again
            prompt = SEARCH_PROMPT_SIMPLIFIED if self._simplified_ui else SEARCH_PROMPT
            await self.bot.send_message(chat_id, prompt)
        return
    
    # ... existing text handling ...
```

## Testing

### Unit Test Example

```python
# tests/unit/test_daemon_search.py

@pytest.mark.asyncio
async def test_search_action_sets_awaiting_state():
    orchestrator = VoiceOrchestrator(...)
    event = TelegramEvent(chat_id=123, callback_data="action:search")
    
    await orchestrator._handle_search_action(event)
    
    assert orchestrator._awaiting_search_query.get(123) == True


@pytest.mark.asyncio
async def test_search_query_clears_state():
    orchestrator = VoiceOrchestrator(...)
    orchestrator._awaiting_search_query[123] = True
    event = TelegramEvent(chat_id=123, text="test query")
    
    await orchestrator._process_search_query(event, "test query")
    
    assert 123 not in orchestrator._awaiting_search_query
```

### Integration Test Example

```python
# tests/integration/test_search_flow.py

@pytest.mark.asyncio
async def test_full_search_flow():
    # Given: User has existing sessions
    # When: User taps [Buscar], types query, selects result
    # Then: Session is restored and active
    pass
```

## User Flow

```
1. User sees RESULTS keyboard with [Buscar] button
2. User taps [Buscar]
3. Bot sends: "🔍 Descreva o tema da sessão que procura:"
4. User types: "reunião sobre arquitetura"
5. Bot sends results:
   [📁 Reunião Tech 2024 (85%)]
   [📁 Discussão Arquitetura (72%)]
   [📁 Planning Meeting (65%)]
   [🔄 Nova Busca] [❌ Fechar]
6. User taps "Reunião Tech 2024 (85%)"
7. Bot sends: "✅ Sessão *Reunião Tech 2024* restaurada.\n🎙️ 5 áudio(s)"
   With SESSION_ACTIVE keyboard: [Finalizar] [Status] [Ajuda]
```
