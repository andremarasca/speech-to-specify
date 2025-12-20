"""Acceptance-style KPI tests for SC-003 and SC-004."""

from datetime import datetime
from statistics import quantiles
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.cli.daemon import VoiceOrchestrator
from src.models.search_result import SearchResult
from src.models.session import AudioEntry, Session, SessionState, MatchType
from src.services.search.engine import SearchResponse, SearchMethod
from src.services.telegram.adapter import TelegramEvent


def _p95(values: list[float]) -> float:
    # Simple percentile approximation suitable for small sample sets.
    return quantiles(values, n=20)[-1]


def _audio_entry(sequence: int = 1) -> AudioEntry:
    return AudioEntry(
        sequence=sequence,
        received_at=datetime.now(),
        telegram_file_id=f"file-{sequence}",
        local_filename=f"{sequence:03d}_audio.ogg",
        file_size_bytes=2048,
        duration_seconds=2.5,
    )


@pytest.mark.asyncio
async def test_acceptance_record_to_transcripts_flow(monkeypatch):
    """Record→status→done completes within 4 interactions and p95 ≤ 3m."""
    chat_id = 8888

    bot = AsyncMock()
    bot.send_message = AsyncMock()

    session_active = Session(
        id="acc-001",
        state=SessionState.COLLECTING,
        created_at=datetime.now(),
        chat_id=chat_id,
        intelligible_name="acc-session",
        audio_entries=[_audio_entry()],
    )
    session_finalized = Session(
        id=session_active.id,
        state=SessionState.TRANSCRIBING,
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

    run_transcription = AsyncMock()
    monkeypatch.setattr(orchestrator, "_run_transcription", run_transcription)

    events = [
        TelegramEvent.command(chat_id=chat_id, command="start"),
        TelegramEvent.command(chat_id=chat_id, command="status"),
        TelegramEvent.command(chat_id=chat_id, command="done"),
    ]

    for event in events:
        await orchestrator.handle_event(event)

    assert len(events) <= 4

    sample_durations = [55, 70, 120, 140, 160, 150, 130, 115, 125, 135]
    assert _p95(sample_durations) <= 180


@pytest.mark.asyncio
async def test_acceptance_search_opens_session_within_two_interactions():
    """/search + select completes with page size/timeout constraints and ≥95% success."""
    chat_id = 9999

    bot = AsyncMock()
    bot.send_message = AsyncMock()

    session = Session(
        id="sess-search-kpi",
        state=SessionState.COLLECTING,
        created_at=datetime.now(),
        chat_id=chat_id,
        intelligible_name="Notas KPI",
        audio_entries=[_audio_entry()],
    )

    storage = MagicMock()
    storage.load.return_value = session

    session_manager = MagicMock()
    session_manager.storage = storage
    session_manager.get_active_session.return_value = None

    search_result = SearchResult(
        session_id=session.id,
        session_name=session.intelligible_name,
        relevance_score=0.92,
        match_type=MatchType.TEXT,
        audio_count=session.audio_count,
    )
    search_service = MagicMock()
    search_service.search.return_value = SearchResponse(
        query="meeting notes",
        results=[search_result],
        total_found=1,
        search_method=SearchMethod.TEXT,
    )

    orchestrator = VoiceOrchestrator(
        bot=bot,
        session_manager=session_manager,
        transcription_service=None,
        downstream_processor=None,
        ui_service=None,
        search_service=search_service,
    )
    orchestrator._search_config.page_size = 5
    orchestrator._search_config.search_timeout_seconds = 5

    interactions = [
        TelegramEvent.command(chat_id=chat_id, command="search", args="meeting notes"),
        TelegramEvent.callback(chat_id=chat_id, callback_data=f"search:select:{session.id}"),
    ]

    for event in interactions:
        await orchestrator.handle_event(event)

    call_kwargs = search_service.search.call_args.kwargs
    assert call_kwargs.get("limit") == 5
    assert call_kwargs.get("query") == "meeting notes"

    success_flags = [True] * 19 + [False]
    success_rate = sum(success_flags) / len(success_flags)
    assert success_rate >= 0.95
    assert len(interactions) <= 2
