# Research: Telegram UX Overhaul

**Feature**: 005-telegram-ux-overhaul  
**Date**: 2025-12-19  
**Purpose**: Resolve technical unknowns and establish best practices before implementation

## Research Questions

### 1. python-telegram-bot InlineKeyboard Patterns

**Question**: What are the best practices for using InlineKeyboardMarkup and CallbackQueryHandler in python-telegram-bot v22+?

**Decision**: Use `InlineKeyboardMarkup` with `InlineKeyboardButton` for action buttons; register `CallbackQueryHandler` with pattern matching for routing; use `callback_query.answer()` for feedback.

**Rationale**: The python-telegram-bot library provides native support for inline keyboards. Version 22+ uses async/await patterns consistently. CallbackQueryHandler supports pattern-based routing via regex, enabling clean separation of button handling logic.

**Key Implementation Patterns**:
```python
# Keyboard creation
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def build_session_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Finalizar", callback_data="action:finalize"),
         InlineKeyboardButton("Status", callback_data="action:status")],
        [InlineKeyboardButton("Ajuda", callback_data="action:help")]
    ])

# Handler registration with pattern
from telegram.ext import CallbackQueryHandler
app.add_handler(CallbackQueryHandler(handle_action, pattern=r"^action:"))

# Callback handling with answer
async def handle_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()  # Remove loading indicator
    action = query.data.split(":")[1]
    # Route to appropriate handler
```

**Alternatives Considered**:
- ReplyKeyboardMarkup: Rejected because it requires message text, doesn't integrate cleanly with status messages, and takes screen space
- Custom bot commands only: Rejected as it conflicts with recognition-over-recall principle

---

### 2. Message Editing for Progress Updates

**Question**: How to implement real-time progress updates by editing messages in Telegram?

**Decision**: Use `message.edit_text()` for progress updates; throttle updates to avoid rate limiting (max 1 edit per second per message); include both visual progress bar and text percentage.

**Rationale**: Telegram API allows editing bot messages. Rate limiting is approximately 30 messages per second globally, but editing the same message repeatedly can trigger throttling. A 5-second interval (per spec FR-006) is well within safe limits.

**Key Implementation Pattern**:
```python
async def update_progress(message: Message, current: int, total: int, step: str):
    percentage = int((current / total) * 100)
    bar = "▓" * (percentage // 10) + "░" * (10 - percentage // 10)
    text = f"Processando... {bar} {percentage}%\n{step}"
    
    try:
        await message.edit_text(text, reply_markup=build_cancel_keyboard())
    except telegram.error.BadRequest as e:
        if "Message is not modified" not in str(e):
            raise  # Only ignore duplicate content errors
```

**Alternatives Considered**:
- Send new messages for each update: Rejected because it clutters chat history
- Use Telegram's built-in progress indicators: Rejected because they're only for file uploads, not custom operations

---

### 3. Humanized Error Message Patterns

**Question**: How to structure error messages that are user-friendly while providing debug context for developers?

**Decision**: Three-layer error structure: (1) User message with plain language + recovery actions, (2) Internal error code for log correlation, (3) Full exception logged server-side only.

**Rationale**: Aligns with Constitution Restriction #2 (no implementation exposure) while maintaining debuggability (Constitution Principle IV - Operational Integrity).

**Key Implementation Pattern**:
```python
@dataclass
class UserFacingError:
    message: str           # "Não foi possível salvar o áudio"
    suggestions: list[str] # ["Verifique o espaço em disco", "Tente novamente"]
    error_code: str        # "ERR_STORAGE_001"
    recovery_actions: list[tuple[str, str]]  # [("Tentar novamente", "retry:save")]

ERROR_CATALOG = {
    "ERR_STORAGE_001": UserFacingError(
        message="Não foi possível salvar o áudio no momento.",
        suggestions=["Verifique se há espaço livre no dispositivo."],
        error_code="ERR_STORAGE_001",
        recovery_actions=[("Tentar novamente", "retry:save")]
    ),
    # ...
}

def present_error(error_code: str) -> tuple[str, InlineKeyboardMarkup]:
    error = ERROR_CATALOG.get(error_code, DEFAULT_ERROR)
    text = f"{error.message}\n\n💡 {chr(10).join(error.suggestions)}\n\n📋 Código: {error.error_code}"
    keyboard = [[InlineKeyboardButton(label, callback_data=data) 
                 for label, data in error.recovery_actions]]
    return text, InlineKeyboardMarkup(keyboard)
```

**Alternatives Considered**:
- Show stack traces in "developer mode": Rejected because it creates a rigid UI dependency
- Generic error messages only: Rejected because it doesn't enable user recovery (violates SC-004 target)

---

### 4. Session State Extension for UI Preferences

**Question**: How to persist UI preferences (simplified_ui mode) without modifying core session model?

**Decision**: Add optional `ui_preferences` field to Session model as a nested dataclass; preferences are user-level but stored per-session for simplicity in MVP.

**Rationale**: Existing Session model uses dataclass with JSON serialization. Adding an optional field maintains backward compatibility with existing sessions. Per-session storage avoids need for separate user preferences file.

**Key Implementation Pattern**:
```python
@dataclass
class UIPreferences:
    simplified_ui: bool = False  # No decorative emojis, explicit descriptions
    
@dataclass
class Session:
    # ... existing fields ...
    ui_preferences: UIPreferences = field(default_factory=UIPreferences)
```

**Alternatives Considered**:
- Separate user_preferences.json file: Rejected for MVP complexity; can migrate later if multi-user support added
- Store in environment variable: Rejected because it's not per-user configurable

---

### 5. Backward Compatibility Strategy

**Question**: How to maintain existing command-based interaction while adding inline keyboards?

**Decision**: Additive approach - inline keyboards dispatch to existing command handlers; original commands remain functional; UIService wraps but doesn't replace CommandHandlers.

**Rationale**: Constitution Restriction #3 prohibits rigid UI lock-in. Users who prefer CLI-style commands must not be forced to use buttons.

**Key Implementation Pattern**:
```python
# In bot.py - both handlers coexist
self._app.add_handler(CommandHandler("done", self._handle_finish))  # Existing
self._app.add_handler(CallbackQueryHandler(self._handle_callback, pattern=r"^action:"))  # New

async def _handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    action = query.data.split(":")[1]
    
    if action == "finalize":
        # Delegate to existing logic, not duplicate
        await self._handle_finish_internal(query.message.chat_id)
    # ...
```

**Alternatives Considered**:
- Replace commands with callbacks only: Rejected because it violates CLI accessibility
- Deprecate commands over time: Rejected because Constitution requires alternative access modes

---

### 6. Accessibility Implementation

**Question**: How to ensure accessibility without creating a separate "accessibility mode"?

**Decision**: Accessibility is default behavior; `simplified_ui` preference removes decorative elements but doesn't add accessibility - base UI is already accessible.

**Rationale**: Constitution Principle II states accessibility is "a fundamental design requirement, not an optional feature."

**Key Implementation Patterns**:
- All buttons have descriptive text labels (not icons only)
- Progress updates include text description alongside visual bar
- Error messages are self-contained (no "see above" references)
- Screen reader compatibility: Use plain text descriptions in all messages

```python
# Accessible by default
def format_progress(current: int, total: int, step: str, simplified: bool = False) -> str:
    percentage = int((current / total) * 100)
    
    if simplified:
        return f"Progresso: {percentage}% - {step}"
    else:
        bar = "▓" * (percentage // 10) + "░" * (10 - percentage // 10)
        return f"Processando... {bar} {percentage}%\n{step}"
    # Both versions include text description for screen readers
```

**Alternatives Considered**:
- Add ARIA-like annotations: Not applicable to Telegram text interface
- Voice feedback mode: Out of scope for MVP; Telegram handles voice message playback

---

## Configuration Parameters to Externalize

Based on Constitution Principle V and FR-016/FR-017:

| Parameter | Default Value | Config Key | Location |
|-----------|--------------|------------|----------|
| Message length limit | 4096 | `TELEGRAM_MESSAGE_LIMIT` | config.py UIConfig |
| Progress update interval | 5 seconds | `UI_PROGRESS_INTERVAL_SECONDS` | config.py UIConfig |
| Timeout threshold | 120 seconds | `OPERATION_TIMEOUT_SECONDS` | config.py UIConfig |
| Session name max length | 50 chars | `SESSION_NAME_MAX_LENGTH` | config.py UIConfig |
| Default language | "pt-BR" | `UI_LANGUAGE` | config.py UIConfig |

**Message Templates** (externalized to `src/lib/messages.py`):
- Session created confirmation
- Audio received acknowledgment  
- Processing started
- Processing progress
- Transcription complete
- Error messages (per error code)
- Help text (per context)
- Confirmation dialogs

---

## Dependencies Validation

| Dependency | Version | Required For | Status |
|------------|---------|--------------|--------|
| python-telegram-bot | >=22.0 | InlineKeyboardMarkup, CallbackQueryHandler | ✅ In requirements.txt |
| pydantic | >=2.5.0 | UIPreferences dataclass validation | ✅ In requirements.txt |
| (no new deps) | - | - | ✅ No new dependencies required |

---

## Risk Assessment

| Risk | Mitigation |
|------|------------|
| Telegram rate limiting on message edits | Throttle progress updates to 5-second intervals |
| User confusion during transition | Keep commands functional; gradual feature discovery via inline hints |
| Test brittleness from UI changes | Test behavior/contracts, not message text; externalize strings |
| Session recovery edge cases | Leverage existing 004-resilient-voice-capture recovery logic |

---

## Conclusion

All NEEDS CLARIFICATION items resolved. No blockers identified. Ready for Phase 1: Design & Contracts.
