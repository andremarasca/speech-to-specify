"""Integration test for inline keyboard flow (001-telegram-contract-fix)."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime

from src.cli.daemon import VoiceOrchestrator
from src.services.telegram.adapter import TelegramEvent
from src.models.session import Session, SessionState, AudioEntry


def _audio_entry(sequence: int = 1) -> AudioEntry:
    return AudioEntry(
        sequence=sequence,
        received_at=datetime.now(),
        telegram_file_id=f"file-{sequence}",
        local_filename=f"{sequence:03d}_audio.ogg",
        file_size_bytes=1024,
        duration_seconds=3.2,
    )


@pytest.mark.asyncio
async def test_inline_flow_start_status_finish(monkeypatch):
    chat_id = 12345

    bot = AsyncMock()
    bot.send_message = AsyncMock()

    session_active = Session(
        id="sess-123",
        state=SessionState.COLLECTING,
        created_at=datetime.now(),
        chat_id=chat_id,
        intelligible_name="flow-session",
        audio_entries=[_audio_entry()],
    )
    session_finalized = Session(
        id=session_active.id,
        state=SessionState.TRANSCRIBED,  # Now transcribed directly (audio transcribed inline)
        created_at=session_active.created_at,
        chat_id=chat_id,
        intelligible_name=session_active.intelligible_name,
        audio_entries=session_active.audio_entries,
    )

    session_manager = MagicMock()
    session_manager.list_sessions.return_value = [session_finalized]
    session_manager.get_active_session.side_effect = [None, session_active, session_active]
    session_manager.create_session.return_value = session_active
    session_manager.finalize_session.return_value = session_finalized

    orchestrator = VoiceOrchestrator(
        bot=bot,
        session_manager=session_manager,
        transcription_service=None,
        downstream_processor=None,
        ui_service=None,
        search_service=None,
    )

    await orchestrator.handle_event(TelegramEvent.command(chat_id=chat_id, command="start"))
    await orchestrator.handle_event(TelegramEvent.command(chat_id=chat_id, command="status"))
    await orchestrator.handle_event(TelegramEvent.command(chat_id=chat_id, command="done"))

    session_manager.create_session.assert_called_once_with(chat_id=chat_id)
    session_manager.finalize_session.assert_called_once_with(session_active.id)
    # Note: /done no longer calls _run_transcription - audio is transcribed inline after receipt

    sent_texts = []
    for call in bot.send_message.await_args_list:
        if call.kwargs and "text" in call.kwargs:
            sent_texts.append(call.kwargs["text"])
        elif len(call.args) >= 2:
            sent_texts.append(call.args[1])
        else:
            sent_texts.append("")
    assert any("Session Started" in text for text in sent_texts)
    assert any("Status: COLLECTING" in text for text in sent_texts)
    assert any("Session Finalized" in text for text in sent_texts)
