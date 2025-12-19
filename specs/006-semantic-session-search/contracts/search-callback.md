# Contract: Search Callback Protocol

**Feature**: 006-semantic-session-search  
**Version**: 1.0.0  
**Date**: 2025-12-19

## Overview

Defines the callback protocol for semantic session search interactions in the Telegram bot.

## Callback Data Formats

### 1. Initiate Search

**Callback Data**: `action:search`  
**Trigger**: User taps [Buscar] button  
**Handler**: `_handle_action_callback(event, "search")`

**Behavior**:
1. Send search prompt message
2. Set `_awaiting_search_query[chat_id] = True`
3. Start 60s timeout task

**Response Message**:
```
🔍 Descreva o tema da sessão que procura:
```

---

### 2. Select Session from Results

**Callback Data**: `search:select:{session_id}`  
**Trigger**: User taps session button from search results  
**Handler**: `_handle_search_select_callback(event, session_id)`

**Behavior**:
1. Load session via `storage.load(session_id)`
2. Set as active via `session_manager.set_active_session(session)`
3. Send confirmation with SESSION_ACTIVE keyboard

**Response Message**:
```
✅ Sessão *{session_name}* restaurada.

🎙️ {audio_count} áudio(s)
```

**Error Cases**:
- Session not found: Show error + [Nova Busca] [Fechar]
- Session corrupted: Show error + [Tentar Novamente] [Fechar]

---

### 3. Close Search Results

**Callback Data**: `action:close`  
**Trigger**: User taps [Fechar] button  
**Handler**: `_handle_action_callback(event, "close")`

**Behavior**:
1. Clear any pending search state
2. Delete or edit message to remove buttons
3. Optionally send acknowledgment

---

### 4. New Search (from results)

**Callback Data**: `action:search`  
**Trigger**: User taps [Nova Busca] button from results/no-results  
**Handler**: Same as #1

---

## Text Message Handling

### Search Query Processing

**Condition**: `_awaiting_search_query.get(chat_id) == True`  
**Handler**: Modified `_handle_text()` or new `_handle_search_query()`

**Flow**:
```python
async def _handle_text(self, event: TelegramEvent) -> None:
    chat_id = event.chat_id
    text = event.text.strip()
    
    # Check if awaiting search query
    if self._awaiting_search_query.get(chat_id):
        await self._process_search_query(event, text)
        return
    
    # ... existing text handling ...
```

**Search Query Processing**:
```python
async def _process_search_query(self, event: TelegramEvent, query: str) -> None:
    chat_id = event.chat_id
    
    # Clear state
    self._awaiting_search_query.pop(chat_id, None)
    if chat_id in self._search_timeout_tasks:
        self._search_timeout_tasks[chat_id].cancel()
        del self._search_timeout_tasks[chat_id]
    
    # Validate query
    if not query:
        await self.bot.send_message(chat_id, SEARCH_EMPTY_QUERY)
        return
    
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
        await self.bot.send_message(
            chat_id,
            SEARCH_RESULTS_HEADER,
            reply_markup=keyboard,
        )
    else:
        keyboard = build_no_results_keyboard(simplified=self._simplified_ui)
        await self.bot.send_message(
            chat_id,
            SEARCH_NO_RESULTS,
            reply_markup=keyboard,
        )
```

---

## Keyboard Specifications

### Search Results Keyboard

**Builder**: `build_search_results_keyboard(results, simplified)`

**Structure**:
```
Row 1: [Session 1 button]
Row 2: [Session 2 button]
Row 3: [Session 3 button]
Row 4: [Session 4 button]
Row 5: [Session 5 button]
Row 6: [Nova Busca] [Fechar]
```

**Button Format**:
- Label: `📁 {session_name} ({score:.0%})` or `{session_name} ({score:.0%})` simplified
- Callback: `search:select:{session_id}`

**Footer Buttons**:
- Nova Busca: `action:search`
- Fechar: `action:close`

---

### No Results Keyboard

**Builder**: `build_no_results_keyboard(simplified)`

**Structure**:
```
Row 1: [Nova Busca] [Fechar]
```

---

## State Machine

```
                    ┌─────────────────┐
                    │     IDLE        │
                    │ (no search)     │
                    └────────┬────────┘
                             │
                    [Buscar] tapped
                             │
                             ▼
                    ┌─────────────────┐
                    │ AWAITING_QUERY  │◄──────────────┐
                    │                 │               │
                    └────────┬────────┘               │
                             │                        │
            ┌────────────────┼────────────────┐       │
            │                │                │       │
     Text received    Timeout (60s)    [Fechar] tapped│
            │                │                │       │
            ▼                ▼                │       │
    ┌───────────────┐ ┌──────────────┐       │       │
    │ PROCESSING    │ │ CANCELLED    │       │       │
    │ (search)      │ │              │       │       │
    └───────┬───────┘ └──────────────┘       │       │
            │                                 │       │
    Results found?                            │       │
     Yes │    │ No                            │       │
         ▼    ▼                               │       │
    ┌─────────┐ ┌──────────────┐             │       │
    │ RESULTS │ │ NO_RESULTS   │─────────────┼───────┘
    │ SHOWN   │ │              │             │ [Nova Busca]
    └────┬────┘ └──────────────┘             │
         │                                    │
Session tapped                                │
         │                                    │
         ▼                                    │
    ┌─────────────────┐                       │
    │ SESSION         │                       │
    │ RESTORED        │───────────────────────┘
    │                 │ (back to IDLE)
    └─────────────────┘
```

---

## Error Handling

| Error | User Message | Recovery Options |
|-------|--------------|------------------|
| Search service unavailable | "Serviço de busca indisponível" | [Tentar Novamente] [Fechar] |
| Session not found | "Sessão não encontrada" | [Nova Busca] [Fechar] |
| Session corrupted | "Erro ao carregar sessão" | [Tentar Novamente] [Fechar] |
| Empty query | "Por favor, descreva o tema" | (no buttons, await new input) |
| Timeout | "Busca cancelada por inatividade" | (no buttons) |

---

## Test Scenarios

### Happy Path

1. User taps [Buscar]
2. System sends prompt
3. User types "reunião sobre arquitetura"
4. System returns 3 matching sessions
5. User taps "Reunião Tech (85%)"
6. Session is restored, SESSION_ACTIVE keyboard shown

### No Results

1. User taps [Buscar]
2. System sends prompt
3. User types "xyzabc123"
4. System shows "Nenhuma sessão encontrada" + [Nova Busca] [Fechar]
5. User taps [Nova Busca]
6. System sends prompt again

### Timeout

1. User taps [Buscar]
2. System sends prompt
3. User does nothing for 60 seconds
4. System sends "Busca cancelada por inatividade"

### Session Already Active

1. User searches and selects Session A
2. Session A becomes active
3. User searches again, finds Session A in results
4. User selects Session A
5. System confirms "Sessão já estava ativa"
