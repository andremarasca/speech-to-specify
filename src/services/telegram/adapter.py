"""Telegram event normalization layer.

This module defines normalized events from Telegram, isolating the
Telegram protocol details from the rest of the application.

Following contracts/telegram-bot.md specification.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class TelegramEvent:
    """
    Normalized event from Telegram.

    Attributes:
        event_type: "command" or "voice"
        chat_id: Telegram chat ID
        timestamp: When the event was received
        payload: Event-specific data (command args or voice file info)
    """

    event_type: str  # "command" | "voice"
    chat_id: int
    timestamp: datetime
    payload: dict

    @classmethod
    def command(cls, chat_id: int, command: str, args: Optional[str] = None) -> "TelegramEvent":
        """Create a command event."""
        return cls(
            event_type="command",
            chat_id=chat_id,
            timestamp=datetime.now(),
            payload={
                "command": command,
                "args": args,
            },
        )

    @classmethod
    def voice(
        cls,
        chat_id: int,
        file_id: str,
        duration: Optional[int] = None,
        file_size: Optional[int] = None,
    ) -> "TelegramEvent":
        """Create a voice message event."""
        return cls(
            event_type="voice",
            chat_id=chat_id,
            timestamp=datetime.now(),
            payload={
                "file_id": file_id,
                "duration": duration,
                "file_size": file_size,
            },
        )

    @property
    def is_command(self) -> bool:
        """Check if this is a command event."""
        return self.event_type == "command"

    @property
    def is_voice(self) -> bool:
        """Check if this is a voice message event."""
        return self.event_type == "voice"

    @property
    def command_name(self) -> Optional[str]:
        """Get command name if this is a command event."""
        if self.is_command:
            return self.payload.get("command")
        return None

    @property
    def command_args(self) -> Optional[str]:
        """Get command arguments if this is a command event."""
        if self.is_command:
            return self.payload.get("args")
        return None

    @property
    def file_id(self) -> Optional[str]:
        """Get file_id if this is a voice event."""
        if self.is_voice:
            return self.payload.get("file_id")
        return None

    @property
    def duration(self) -> Optional[int]:
        """Get duration if this is a voice event."""
        if self.is_voice:
            return self.payload.get("duration")
        return None
