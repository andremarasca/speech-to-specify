# Contract: Telegram Bot Adapter

**Module**: `src/services/telegram/`  
**Purpose**: Receive commands and voice messages from Telegram, normalize to domain events

## Interface

### TelegramBotAdapter

```python
from abc import ABC, abstractmethod
from typing import Callable, Awaitable

class TelegramEvent:
    """Normalized event from Telegram."""
    event_type: str  # "command" | "voice"
    chat_id: int
    timestamp: datetime
    payload: dict  # Command args or voice file info

class TelegramBotAdapter(ABC):
    @abstractmethod
    async def start(self) -> None:
        """Start listening for Telegram updates."""
        pass
    
    @abstractmethod
    async def stop(self) -> None:
        """Stop the bot gracefully."""
        pass
    
    @abstractmethod
    def on_event(self, handler: Callable[[TelegramEvent], Awaitable[None]]) -> None:
        """Register event handler callback."""
        pass
    
    @abstractmethod
    async def send_message(self, chat_id: int, text: str) -> None:
        """Send text message to user."""
        pass
    
    @abstractmethod
    async def send_file(self, chat_id: int, file_path: Path) -> None:
        """Send file to user."""
        pass
    
    @abstractmethod
    async def download_voice(self, file_id: str, destination: Path) -> int:
        """Download voice message to local path. Returns file size in bytes."""
        pass
```

## Commands

| Command | Event Type | Payload |
|---------|------------|---------|
| `/start` | command | `{"command": "start"}` |
| `/finish` or `/done` | command | `{"command": "finish"}` |
| `/status` | command | `{"command": "status"}` |
| `/transcripts` | command | `{"command": "transcripts"}` |
| `/process` | command | `{"command": "process"}` |
| `/list` | command | `{"command": "list"}` |
| `/get <filename>` | command | `{"command": "get", "filename": "..."}` |
| (voice message) | voice | `{"file_id": "...", "duration": 60}` |

## Authorization

- Single user only: `TELEGRAM_ALLOWED_CHAT_ID` environment variable
- Unauthorized chat_id receives: "⛔ Unauthorized access"
- All events from unauthorized users are dropped (not logged)

## Error Handling

| Error | Response |
|-------|----------|
| Bot token invalid | Fail startup with clear error |
| Network timeout | Automatic retry (built into python-telegram-bot) |
| File download failed | Return error, caller handles |
| Unknown command | Respond: "❓ Unknown command. Try /status" |

## Configuration

```python
class TelegramConfig:
    bot_token: str          # TELEGRAM_BOT_TOKEN env var
    allowed_chat_id: int    # TELEGRAM_ALLOWED_CHAT_ID env var
    download_timeout: int = 60  # Seconds for voice download
```

## Events Flow

```text
Telegram API
     │
     │ Update (command or voice)
     ▼
┌─────────────────────────┐
│  TelegramBotAdapter     │
│  (python-telegram-bot)  │
└─────────────────────────┘
     │
     │ TelegramEvent (normalized)
     ▼
┌─────────────────────────┐
│  Event Handler          │
│  (SessionManager)       │
└─────────────────────────┘
