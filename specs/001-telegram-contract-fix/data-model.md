# Data Model – Telegram Contract Fix

## Entities

### Session
- **Fields**: id (string), friendly_name (string), state (enum: COLLECTING, TRANSCRIBING, TRANSCRIBED, PROCESSING, PROCESSED, INTERRUPTED), chat_id (string), created_at (datetime), updated_at (datetime), audio_count (int), transcripts_path (path), preferences (UIPreferences), last_error (string, optional).
- **Relationships**: references transcripts on filesystem; associated with UI context per chat.
- **Rules**: State transitions follow domain rules; INTERRUPTED sessions trigger recovery prompts.

### CallbackAction
- **Fields**: prefix (enum: action/help/recover/confirm/nav/retry/page/search), payload (string), chat_id (string), message_id (string), session_id (optional), page (optional int), topic (optional string), acknowledged (bool).
- **Rules**: Every prefix must map to handler; invalid payload logs warning and preserves UI state; acknowledge-only actions (`close_help`, `dismiss`, `page:current`) must still answer callback.

### BuscaSemantica
- **Fields**: query (string), results (list of {session_id, score, snippet}), page_size (int), page (int), total (int), occurred_at (datetime), status (enum: OK, EMPTY, ERROR), error_reason (string optional).
- **Rules**: `/search <query>` and conversational search share pipeline; errors return friendly message and optional retry.

### PreferenciasUI
- **Fields**: simplified_ui (bool), chat_id (string), updated_at (datetime).
- **Rules**: Managed externally (env/config/state store); applied to keyboards/help rendering; updated via `/preferences`.

### UIState (per chat)
- **Fields**: chat_id (string), awaiting_search_query (bool), last_session_id (optional), pagination_cursor (TODO/placeholder), mode (derived from SessionState), preferences (UIPreferences).
- **Rules**: Awaiting search cleared after processing query; pagination cursor pending future implementation; must not leave callbacks órfãos.
