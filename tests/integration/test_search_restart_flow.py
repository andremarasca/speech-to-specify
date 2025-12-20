"""Integration test for search restart resilience (T037)."""

import logging
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.cli.daemon import VoiceOrchestrator
from src.services.telegram.adapter import TelegramEvent


@pytest.mark.asyncio
async def test_search_callback_after_restart_warns_and_guides(caplog):
    chat_id = 777

    bot = AsyncMock()
    bot.send_message = AsyncMock()

    session_manager = MagicMock()
    session_manager.storage = MagicMock()
    session_manager.storage.load.return_value = None
    session_manager.get_active_session.return_value = None

    orchestrator = VoiceOrchestrator(
        bot=bot,
        session_manager=session_manager,
        transcription_service=None,
        downstream_processor=None,
        ui_service=None,
        search_service=MagicMock(),
    )

    stale_callback = TelegramEvent.callback(
        chat_id=chat_id,
        callback_data="search:select:ghost-session",
    )

    with caplog.at_level(logging.WARNING):
        await orchestrator.handle_event(stale_callback)

    bot.send_message.assert_awaited_once()
    sent_kwargs = bot.send_message.await_args_list[0].kwargs
    sent_text = sent_kwargs.get("text") or (bot.send_message.await_args_list[0].args[1] if len(bot.send_message.await_args_list[0].args) > 1 else "")
    assert "search" in sent_text.lower() or "busca" in sent_text.lower()

    record = next(
        (r for r in caplog.records if getattr(r, "error_code", None) == "search_session_missing"),
        None,
    )
    assert record is not None
    assert getattr(record, "chat_id", None) == chat_id
    assert getattr(record, "session_id", None) == "ghost-session"
