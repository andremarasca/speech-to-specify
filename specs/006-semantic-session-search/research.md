# Research: Semantic Session Search

**Feature**: 006-semantic-session-search  
**Date**: 2025-12-19  
**Status**: Complete

## Overview

This document captures research findings for implementing semantic session search via Telegram inline buttons.

## Research Tasks

### 1. Conversational State Management

**Question**: How to track that a chat is "awaiting search query" after [Buscar] tap?

**Decision**: In-memory dictionary in `VoiceOrchestrator`

**Rationale**:
- Daemon is single-instance per deployment
- State is short-lived (max 60s until timeout)
- No persistence needed across restarts
- Pattern already established for other features (see `_simplified_ui` in daemon.py)

**Alternatives Considered**:
- **Redis/external cache**: Overkill for single-instance bot
- **Session model extension**: Would pollute domain model with UI concerns
- **Database state**: Unnecessary persistence for ephemeral state

**Implementation**:
```python
class VoiceOrchestrator:
    def __init__(self, ...):
        ...
        self._awaiting_search_query: dict[int, bool] = {}
        self._search_timeout_tasks: dict[int, asyncio.Task] = {}
```

---

### 2. Dynamic Keyboard Generation

**Question**: How to present variable search results as inline buttons?

**Decision**: New `_build_search_results()` function in keyboards.py with dynamic button generation

**Rationale**:
- Existing pattern uses static `KeyboardType` enum + builder functions
- Search results are dynamic (0-5 sessions) with varying labels
- Button callback data must include session ID

**Alternatives Considered**:
- **Static KeyboardType per result count**: Would need SEARCH_RESULTS_0, _1, _2, etc. - not scalable
- **Custom Message class with keyboard**: Over-engineering for simple use case

**Implementation**:
```python
def build_search_results_keyboard(
    results: list[SearchResult],
    simplified: bool = False,
) -> InlineKeyboardMarkup:
    """Build dynamic keyboard for search results."""
    buttons = []
    for result in results:
        label = f"📁 {result.session_name} ({result.relevance_score:.0%})"
        callback = f"search:select:{result.session_id}"
        buttons.append([InlineKeyboardButton(label, callback_data=callback)])
    
    # Add footer buttons
    new_search = "Nova Busca" if simplified else "🔄 Nova Busca"
    close = "Fechar" if simplified else "❌ Fechar"
    buttons.append([
        InlineKeyboardButton(new_search, callback_data="action:search"),
        InlineKeyboardButton(close, callback_data="action:close"),
    ])
    
    return InlineKeyboardMarkup(buttons)
```

---

### 3. Session Restoration Flow

**Question**: How to restore a session from search results?

**Decision**: Use existing `SessionManager.set_active_session()` method

**Rationale**:
- SessionManager already handles active session tracking
- No new domain logic needed
- Separation of concerns: daemon handles UI, manager handles state

**Research Findings**:
- `SessionManager.get_active_session()` returns current active session
- `SessionManager.set_active_session(session)` sets session as active
- Session loaded via `storage.load(session_id)` returns complete Session object

**Edge Cases**:
- If selected session is already active: confirm without change
- If session files corrupted: `storage.load()` raises exception → catch and show error

---

### 4. Timeout Mechanism

**Question**: How to implement 60s search query timeout?

**Decision**: `asyncio.Task` with cancellation

**Rationale**:
- Native async pattern
- Can be cancelled when user provides input
- Clean resource management

**Implementation**:
```python
async def _start_search_timeout(self, chat_id: int) -> None:
    """Start timeout for search query."""
    async def timeout_handler():
        await asyncio.sleep(60)  # Configurable via config.py
        if self._awaiting_search_query.get(chat_id):
            del self._awaiting_search_query[chat_id]
            await self.bot.send_message(
                chat_id,
                "⏰ Busca cancelada por inatividade.",
            )
    
    # Cancel existing timeout if any
    if chat_id in self._search_timeout_tasks:
        self._search_timeout_tasks[chat_id].cancel()
    
    self._search_timeout_tasks[chat_id] = asyncio.create_task(timeout_handler())
```

---

### 5. Search Service Integration

**Question**: How does existing SearchService work?

**Research Findings**:

From `src/services/search/engine.py`:
- `SearchService` is abstract base class
- `DefaultSearchService` is concrete implementation
- `search(query, chat_id, limit, min_score)` → `SearchResponse`
- `SearchResponse` contains `results: list[SearchResult]`

From `src/models/search_result.py`:
- `SearchResult` has: `session_id`, `session_name`, `relevance_score`, `match_type`
- Score is 0.0-1.0 range

**Integration**:
```python
# In daemon.py
search_response = self.search_service.search(
    query=user_query,
    chat_id=event.chat_id,  # Filter to user's sessions
    limit=5,
    min_score=0.6,  # From config
)

if search_response.results:
    keyboard = build_search_results_keyboard(search_response.results)
    await self.bot.send_message(chat_id, "Resultados:", reply_markup=keyboard)
else:
    # No results flow
```

---

### 6. Callback Data Format

**Question**: What format for search-related callback data?

**Decision**: Consistent with existing patterns: `{namespace}:{action}:{data}`

**Existing Patterns**:
- `action:finalize` - action namespace
- `confirm:session_conflict:finalize` - confirm namespace with type:response
- `help:general` - help namespace with topic

**New Patterns**:
- `action:search` - initiate search (already exists in keyboard)
- `search:select:{session_id}` - select session from results
- `action:close` - dismiss search results (reuse existing)

---

## Configuration Requirements

New configuration values for `config.py`:

```python
class SearchConfig(BaseSettings):
    """Configuration for semantic search."""
    
    min_similarity_score: float = Field(
        default=0.6,
        alias="SEARCH_MIN_SCORE",
        description="Minimum similarity score for search results (0.0-1.0)",
    )
    
    max_results: int = Field(
        default=5,
        alias="SEARCH_MAX_RESULTS",
        description="Maximum search results to display",
    )
    
    query_timeout_seconds: int = Field(
        default=60,
        alias="SEARCH_QUERY_TIMEOUT",
        description="Timeout for search query input in seconds",
    )
```

---

## Summary

All research questions resolved. No blockers identified.

| Topic | Decision | Confidence |
|-------|----------|------------|
| State management | In-memory dict | High |
| Dynamic keyboard | Custom builder function | High |
| Session restoration | Existing SessionManager | High |
| Timeout mechanism | asyncio.Task | High |
| Search integration | Existing SearchService | High |
| Callback format | `search:select:{id}` | High |
