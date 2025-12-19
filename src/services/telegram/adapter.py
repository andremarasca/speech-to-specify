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
        event_type: "command", "voice", or "callback"
        chat_id: Telegram chat ID
        timestamp: When the event was received
        payload: Event-specific data (command args, voice file info, or callback data)
    """

    event_type: str  # "command" | "voice" | "callback"
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

    @classmethod
    def callback(
        cls,
        chat_id: int,
        callback_data: str,
        message_id: Optional[int] = None,
        user_id: Optional[int] = None,
    ) -> "TelegramEvent":
        """
        Create a callback query event.
        
        Callback data format follows the pattern defined in contracts/:
        - action:<action_name> for immediate actions (finalize, cancel, etc.)
        - nav:<direction>:<context> for navigation (page:next, page:prev)
        - help:<topic> for contextual help
        - confirm:<type>:<response> for confirmation dialogs
        - recover:<action> for crash recovery options
        
        Args:
            chat_id: Telegram chat ID
            callback_data: The callback_data string from the button press
            message_id: ID of the message containing the button (for editing)
            user_id: ID of the user who pressed the button
        """
        return cls(
            event_type="callback",
            chat_id=chat_id,
            timestamp=datetime.now(),
            payload={
                "callback_data": callback_data,
                "message_id": message_id,
                "user_id": user_id,
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
    def is_callback(self) -> bool:
        """Check if this is a callback query event."""
        return self.event_type == "callback"

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

    @property
    def callback_data(self) -> Optional[str]:
        """Get callback_data if this is a callback event."""
        if self.is_callback:
            return self.payload.get("callback_data")
        return None

    @property
    def message_id(self) -> Optional[int]:
        """Get message_id if this is a callback event."""
        if self.is_callback:
            return self.payload.get("message_id")
        return None

    @property
    def callback_action(self) -> Optional[str]:
        """
        Get the action type from callback_data.
        
        Returns the prefix before the first colon (e.g., 'action', 'nav', 'help', 'confirm', 'recover').
        """
        if self.is_callback and self.callback_data:
            parts = self.callback_data.split(":", 1)
            return parts[0] if parts else None
        return None

    @property
    def callback_value(self) -> Optional[str]:
        """
        Get the value portion from callback_data.
        
        Returns everything after the first colon.
        """
        if self.is_callback and self.callback_data:
            parts = self.callback_data.split(":", 1)
            return parts[1] if len(parts) > 1 else None
        return None
