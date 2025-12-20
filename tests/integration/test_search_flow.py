"""Integration tests for search flow (001-telegram-contract-fix)."""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

from src.cli.daemon import VoiceOrchestrator
from src.services.telegram.adapter import TelegramEvent
from src.services.search.engine import SearchResponse, SearchMethod
from src.models.search_result import SearchResult
from src.models.session import AudioEntry, Session, SessionState, MatchType


def _audio_entry(sequence: int = 1) -> AudioEntry:
    return AudioEntry(
        sequence=sequence,
        received_at=datetime.now(),
        telegram_file_id=f"file-{sequence}",
        local_filename=f"{sequence:03d}_audio.ogg",
        file_size_bytes=2048,
        duration_seconds=2.5,
    )


def _search_response(session: Session) -> SearchResponse:
    result = SearchResult(
        session_id=session.id,
        session_name=session.intelligible_name or session.id,
        relevance_score=0.92,
        match_type=MatchType.TEXT,
        audio_count=session.audio_count,
    )
    return SearchResponse(
        query="meeting notes",
        results=[result],
        total_found=1,
        search_method=SearchMethod.TEXT,
    )


@pytest.mark.asyncio
async def test_search_flow_lists_results_and_restores_session(monkeypatch):
    chat_id = 67890

    # Mock bot
    bot = AsyncMock()
    bot.send_message = AsyncMock()

    # Mock session and storage
    session = Session(
        id="sess-search-1",
        state=SessionState.COLLECTING,
        created_at=datetime.now(),
        chat_id=chat_id,
        intelligible_name="Notas da Reunião",
        audio_entries=[_audio_entry()],
    )

    storage = MagicMock()
    storage.load.return_value = session

    session_manager = MagicMock()
    session_manager.storage = storage
    session_manager.get_active_session.return_value = None

    # Mock search service response
    search_service = MagicMock()
    search_service.search.return_value = _search_response(session)

    orchestrator = VoiceOrchestrator(
        bot=bot,
        session_manager=session_manager,
        transcription_service=None,
        downstream_processor=None,
        ui_service=None,
        search_service=search_service,
    )

    # Send /search with inline query
    await orchestrator.handle_event(
        TelegramEvent.command(chat_id=chat_id, command="search", args="meeting notes")
    )

    # Should have sent results with keyboard containing search:select callback
    bot.send_message.assert_awaited()
    first_call = bot.send_message.await_args_list[0]
    reply_markup = first_call.kwargs.get("reply_markup")
    callbacks = [btn.callback_data for row in reply_markup.inline_keyboard for btn in row]
    assert any(cb.startswith("search:select:") for cb in callbacks)

    # Simulate selecting a result
    await orchestrator.handle_event(
        TelegramEvent.callback(
            chat_id=chat_id,
            callback_data=f"search:select:{session.id}",
        )
    )

    # Second message should confirm session restoration
    assert bot.send_message.await_count >= 2
    restore_call = bot.send_message.await_args_list[-1]
    restore_text = restore_call.kwargs.get("text") or restore_call.args[1]
    assert "Notas da Reunião" in restore_text
    # Should present session actions keyboard
    assert restore_call.kwargs.get("reply_markup") is not None

