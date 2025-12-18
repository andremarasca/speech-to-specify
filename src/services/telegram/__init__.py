"""Telegram service package for bot communication."""

from src.services.telegram.adapter import TelegramEvent
from src.services.telegram.bot import TelegramBotAdapter

__all__ = ["TelegramEvent", "TelegramBotAdapter"]
