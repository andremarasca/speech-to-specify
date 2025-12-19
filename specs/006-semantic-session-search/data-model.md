# Data Model: Semantic Session Search

**Feature**: 006-semantic-session-search  
**Date**: 2025-12-19  
**Status**: Complete

## Overview

This document defines the data entities for semantic session search. Most infrastructure already exists; this feature adds minimal new state.

## Entity Definitions

### 1. SearchQuery (Conceptual - Not Persisted)

Represents a user's search request. Exists only in-memory during search flow.

| Field | Type | Description |
|-------|------|-------------|
| chat_id | int | Telegram chat identifier |
| query_text | str | Natural language search query |
| timestamp | datetime | When query was initiated |

**Notes**:
- Not persisted to disk
- Exists only between [Buscar] tap and results display
- Tracked via `_awaiting_search_query` dict in daemon

---

### 2. ConversationalState (Extension to VoiceOrchestrator)

Tracks which chats are awaiting specific input. Extends existing daemon state.

**New Fields in VoiceOrchestrator**:

| Field | Type | Description |
|-------|------|-------------|
| `_awaiting_search_query` | dict[int, bool] | True if chat is waiting for search query |
| `_search_timeout_tasks` | dict[int, asyncio.Task] | Timeout tasks per chat |

**State Transitions**:
```
[Buscar] tapped → _awaiting_search_query[chat_id] = True
                  Start timeout task

Text received   → Check _awaiting_search_query[chat_id]
                  If True: process as search query, clear state
                  If False: normal text handling

Timeout (60s)   → Clear _awaiting_search_query[chat_id]
                  Send cancellation message
```

---

### 3. SearchResult (Already Implemented)

From `src/models/search_result.py`:

| Field | Type | Description |
|-------|------|-------------|
| session_id | str | Unique session identifier |
| session_name | str | Human-readable name (intelligible_name) |
| relevance_score | float | Similarity score [0.0, 1.0] |
| match_type | MatchType | How match was determined |
| preview_fragments | list[PreviewFragment] | Context snippets (optional) |
| session_created_at | datetime | When session was created |
| audio_count | int | Number of audio files |

**Usage in Search Flow**:
- Score displayed as percentage in button label
- session_id used in callback data for selection
- session_name shown as primary button text

---

### 4. KeyboardType Extension

Add new enum value to `src/models/ui_state.py`:

```python
class KeyboardType(str, Enum):
    # ... existing values ...
    SEARCH_RESULTS = "SEARCH_RESULTS"     # Dynamic search results
    SEARCH_NO_RESULTS = "SEARCH_NO_RESULTS"  # No results found
```

**Keyboard Layouts**:

**SEARCH_RESULTS** (dynamic, 0-5 session buttons):
```
[📁 Session Name 1 (85%)]  → search:select:{id1}
[📁 Session Name 2 (72%)]  → search:select:{id2}
[📁 Session Name 3 (68%)]  → search:select:{id3}
[🔄 Nova Busca] [❌ Fechar] → action:search, action:close
```

**SEARCH_NO_RESULTS** (static):
```
Nenhuma sessão encontrada para sua busca.
[🔄 Nova Busca] [❌ Fechar] → action:search, action:close
```

---

### 5. SearchConfig (New Configuration Class)

Add to `src/lib/config.py`:

| Field | Type | Default | Env Var | Description |
|-------|------|---------|---------|-------------|
| min_similarity_score | float | 0.6 | SEARCH_MIN_SCORE | Minimum score threshold |
| max_results | int | 5 | SEARCH_MAX_RESULTS | Max results to display |
| query_timeout_seconds | int | 60 | SEARCH_QUERY_TIMEOUT | Query input timeout |

---

## Relationships

```
VoiceOrchestrator
    ├── _awaiting_search_query: dict[int, bool]
    ├── _search_timeout_tasks: dict[int, Task]
    ├── search_service: SearchService
    │       └── search() → SearchResponse
    │                         └── results: list[SearchResult]
    └── session_manager: SessionManager
            └── set_active_session(session)
            └── storage.load(session_id) → Session
```

---

## Message Templates

Add to `src/lib/messages.py`:

```python
# Search Flow Messages
SEARCH_PROMPT = "🔍 Descreva o tema da sessão que procura:"
SEARCH_PROMPT_SIMPLIFIED = "Descreva o tema da sessão que procura:"

SEARCH_RESULTS_HEADER = "📋 Sessões encontradas:"
SEARCH_RESULTS_HEADER_SIMPLIFIED = "Sessões encontradas:"

SEARCH_NO_RESULTS = "❌ Nenhuma sessão encontrada para sua busca.\n\nTente descrever de outra forma."
SEARCH_NO_RESULTS_SIMPLIFIED = "Nenhuma sessão encontrada. Tente descrever de outra forma."

SEARCH_SESSION_RESTORED = "✅ Sessão *{session_name}* restaurada.\n\n🎙️ {audio_count} áudio(s)"
SEARCH_SESSION_RESTORED_SIMPLIFIED = "Sessão {session_name} restaurada. {audio_count} áudio(s)"

SEARCH_TIMEOUT = "⏰ Busca cancelada por inatividade."
SEARCH_TIMEOUT_SIMPLIFIED = "Busca cancelada por inatividade."

SEARCH_EMPTY_QUERY = "❌ Por favor, descreva o tema da sessão que procura."
SEARCH_EMPTY_QUERY_SIMPLIFIED = "Por favor, descreva o tema da sessão."

# Button Labels (dynamic - not in constants)
SEARCH_RESULT_BUTTON = "📁 {name} ({score:.0%})"
SEARCH_RESULT_BUTTON_SIMPLIFIED = "{name} ({score:.0%})"

BUTTON_NEW_SEARCH = "🔄 Nova Busca"
BUTTON_NEW_SEARCH_SIMPLIFIED = "Nova Busca"
```

---

## Validation Rules

1. **Search Query**:
   - Must not be empty or whitespace-only
   - No maximum length (embedding model handles truncation)

2. **Relevance Score**:
   - Must be in range [0.0, 1.0]
   - Results below `min_similarity_score` are filtered out

3. **Results Limit**:
   - Maximum `max_results` sessions displayed
   - Ordered by relevance_score descending

4. **Session Restoration**:
   - Session must exist in storage
   - Session files must be valid (not corrupted)
   - If already active, no state change needed
