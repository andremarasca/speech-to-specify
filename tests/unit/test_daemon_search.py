"""Unit tests for search state management in VoiceOrchestrator.

Per T031-T034 from 006-semantic-session-search tasks.md.
Tests the conversational state management for the [Buscar] button flow.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from src.cli.daemon import VoiceOrchestrator
from src.services.telegram.adapter import TelegramEvent
from src.models.session import Session, SessionState


@pytest.fixture
def mock_bot():
    """Create a mock TelegramBotAdapter."""
    bot = MagicMock()
    bot.send_message = AsyncMock()
    return bot


@pytest.fixture
def mock_session_manager():
    """Create a mock SessionManager."""
    manager = MagicMock()
    manager.get_active_session.return_value = None
    manager.list_sessions.return_value = []
    manager.storage = MagicMock()
    return manager


@pytest.fixture
def mock_search_service():
    """Create a mock SearchService."""
    service = MagicMock()
    response = MagicMock()
    response.results = []
    response.total_found = 0
    service.search.return_value = response
    return service


@pytest.fixture
def mock_ui_service():
    """Create a mock UIService."""
    service = MagicMock()
    return service


@pytest.fixture
def orchestrator(mock_bot, mock_session_manager, mock_search_service, mock_ui_service):
    """Create a VoiceOrchestrator with mocked dependencies."""
    orch = VoiceOrchestrator(
        bot=mock_bot,
        session_manager=mock_session_manager,
        transcription_service=None,
        downstream_processor=None,
        ui_service=mock_ui_service,
        search_service=mock_search_service,
    )
    orch.set_chat_id(12345)
    return orch


@pytest.fixture
def callback_event():
    """Create a mock callback event for search action."""
    event = MagicMock(spec=TelegramEvent)
    event.chat_id = 12345
    event.is_callback = True
    event.is_command = False
    event.is_voice = False
    event.is_text = False
    event.callback_action = "action"
    event.callback_value = "search"
    event.callback_data = "action:search"
    return event


@pytest.fixture
def text_event():
    """Create a mock text event for search query."""
    event = MagicMock(spec=TelegramEvent)
    event.chat_id = 12345
    event.is_callback = False
    event.is_command = False
    event.is_voice = False
    event.is_text = True
    event.text = "microsserviços arquitetura"
    return event


class TestSearchActionSetsAwaitingState:
    """T032: Test that search action sets awaiting state."""

    @pytest.mark.asyncio
    async def test_search_action_sets_awaiting_state(self, orchestrator, callback_event):
        """Verify that tapping [Buscar] sets _awaiting_search_query[chat_id] = True."""
        chat_id = callback_event.chat_id
        
        # Initially should not be awaiting
        assert chat_id not in orchestrator._awaiting_search_query
        
        # Handle the search action
        await orchestrator._handle_search_action(callback_event)
        
        # Should now be awaiting
        assert orchestrator._awaiting_search_query.get(chat_id) is True

    @pytest.mark.asyncio
    async def test_search_action_sends_prompt(self, orchestrator, callback_event, mock_bot):
        """Verify that search action sends the prompt message."""
        await orchestrator._handle_search_action(callback_event)
        
        mock_bot.send_message.assert_called_once()
        call_args = mock_bot.send_message.call_args
        assert "Descreva o tema" in call_args[0][1] or "Descreva o tema" in str(call_args)

    @pytest.mark.asyncio
    async def test_search_action_starts_timeout(self, orchestrator, callback_event):
        """Verify that search action starts a timeout task."""
        chat_id = callback_event.chat_id
        
        # Initially no timeout task
        assert chat_id not in orchestrator._search_timeout_tasks
        
        await orchestrator._handle_search_action(callback_event)
        
        # Should have a timeout task
        assert chat_id in orchestrator._search_timeout_tasks
        assert isinstance(orchestrator._search_timeout_tasks[chat_id], asyncio.Task)
        
        # Cleanup
        orchestrator._search_timeout_tasks[chat_id].cancel()


class TestSearchQueryClearsState:
    """T033: Test that receiving search query clears awaiting state."""

    @pytest.mark.asyncio
    async def test_search_query_clears_awaiting_state(
        self, orchestrator, text_event, mock_search_service
    ):
        """Verify that receiving a search query clears _awaiting_search_query."""
        chat_id = text_event.chat_id
        
        # Set up awaiting state
        orchestrator._awaiting_search_query[chat_id] = True
        
        # Process query
        await orchestrator._process_search_query(text_event, text_event.text)
        
        # State should be cleared
        assert chat_id not in orchestrator._awaiting_search_query

    @pytest.mark.asyncio
    async def test_search_query_cancels_timeout(self, orchestrator, text_event):
        """Verify that receiving a search query cancels the timeout task."""
        chat_id = text_event.chat_id
        
        # Set up awaiting state with timeout task
        orchestrator._awaiting_search_query[chat_id] = True
        
        async def dummy_timeout():
            await asyncio.sleep(60)
        
        orchestrator._search_timeout_tasks[chat_id] = asyncio.create_task(dummy_timeout())
        
        # Process query
        await orchestrator._process_search_query(text_event, text_event.text)
        
        # Timeout task should be cancelled and removed
        assert chat_id not in orchestrator._search_timeout_tasks

    @pytest.mark.asyncio
    async def test_search_query_calls_search_service(
        self, orchestrator, text_event, mock_search_service
    ):
        """Verify that search query triggers SearchService.search()."""
        chat_id = text_event.chat_id
        orchestrator._awaiting_search_query[chat_id] = True
        orchestrator._search_config.page_size = 3
        
        await orchestrator._process_search_query(text_event, text_event.text)
        
        mock_search_service.search.assert_called_once()
        call_kwargs = mock_search_service.search.call_args
        assert text_event.text in str(call_kwargs)
        assert call_kwargs.kwargs.get("limit") == 3

    @pytest.mark.asyncio
    async def test_search_query_timeout_warns_user(
        self, orchestrator, text_event, mock_bot
    ):
        """Verify that a long search triggers timeout handling."""
        chat_id = text_event.chat_id
        orchestrator._awaiting_search_query[chat_id] = True
        orchestrator._search_config.search_timeout_seconds = 0.01

        # Replace search_service.search with a slow coroutine via to_thread by wrapping
        def slow_blocking_search(**kwargs):
            import time
            time.sleep(0.05)
            return MagicMock(results=[])

        orchestrator.search_service.search.side_effect = slow_blocking_search

        await orchestrator._process_search_query(text_event, text_event.text)

        mock_bot.send_message.assert_called()
        assert "busca" in str(mock_bot.send_message.call_args).lower()


class TestSearchTimeoutClearsState:
    """T034: Test that search timeout clears awaiting state."""

    @pytest.mark.asyncio
    async def test_timeout_clears_awaiting_state(self, orchestrator, mock_bot):
        """Verify that timeout clears _awaiting_search_query after configured seconds."""
        chat_id = 12345
        
        # Override timeout to be very short for testing
        orchestrator._search_config.query_timeout_seconds = 0.1
        
        # Set awaiting state
        orchestrator._awaiting_search_query[chat_id] = True
        
        # Start timeout
        await orchestrator._start_search_timeout(chat_id)
        
        # Wait for timeout to trigger
        await asyncio.sleep(0.2)
        
        # State should be cleared
        assert chat_id not in orchestrator._awaiting_search_query

    @pytest.mark.asyncio
    async def test_timeout_sends_message(self, orchestrator, mock_bot):
        """Verify that timeout sends cancellation message."""
        chat_id = 12345
        
        # Override timeout to be very short
        orchestrator._search_config.query_timeout_seconds = 0.1
        
        orchestrator._awaiting_search_query[chat_id] = True
        await orchestrator._start_search_timeout(chat_id)
        
        # Wait for timeout
        await asyncio.sleep(0.2)
        
        # Should have sent timeout message
        mock_bot.send_message.assert_called()
        call_args = str(mock_bot.send_message.call_args)
        assert "inatividade" in call_args.lower() or "timeout" in call_args.lower()


class TestSearchResultsPresentation:
    """Test search results presentation."""

    @pytest.mark.asyncio
    async def test_presents_results_with_keyboard(
        self, orchestrator, mock_bot, mock_search_service
    ):
        """Verify that search results are presented with inline keyboard."""
        from src.models.search_result import SearchResult
        from src.models.session import MatchType
        
        chat_id = 12345
        
        # Set up mock results
        results = [
            SearchResult(
                session_id="session_001",
                session_name="Python Meeting",
                relevance_score=0.85,
                match_type=MatchType.SEMANTIC,
            ),
            SearchResult(
                session_id="session_002",
                session_name="Architecture Review",
                relevance_score=0.72,
                match_type=MatchType.SEMANTIC,
            ),
        ]
        
        await orchestrator._present_search_results(chat_id, results)
        
        # Should send message with keyboard
        mock_bot.send_message.assert_called_once()
        call_kwargs = mock_bot.send_message.call_args
        assert "reply_markup" in str(call_kwargs)

    @pytest.mark.asyncio
    async def test_presents_no_results_message(self, orchestrator, mock_bot):
        """Verify that empty results show appropriate message."""
        chat_id = 12345
        
        await orchestrator._present_search_results(chat_id, [])
        
        mock_bot.send_message.assert_called_once()
        call_args = str(mock_bot.send_message.call_args)
        assert "encontrada" in call_args.lower() or "no results" in call_args.lower()


class TestSessionRestoration:
    """Test session restoration from search results."""

    @pytest.mark.asyncio
    async def test_restore_session_success(
        self, orchestrator, mock_bot, mock_session_manager
    ):
        """Verify successful session restoration."""
        chat_id = 12345
        session_id = "test_session_001"
        
        # Set up mock session
        mock_session = MagicMock(spec=Session)
        mock_session.id = session_id
        mock_session.intelligible_name = "Test Session"
        mock_session.audio_count = 3
        mock_session_manager.storage.load.return_value = mock_session
        mock_session_manager.get_active_session.return_value = None
        
        await orchestrator._restore_session(chat_id, session_id)
        
        # Should load session
        mock_session_manager.storage.load.assert_called_with(session_id)
        
        # Should send confirmation
        mock_bot.send_message.assert_called_once()
        call_args = str(mock_bot.send_message.call_args)
        assert "restaurada" in call_args.lower() or "restored" in call_args.lower()

    @pytest.mark.asyncio
    async def test_restore_session_already_active(
        self, orchestrator, mock_bot, mock_session_manager
    ):
        """Verify handling when session is already active."""
        chat_id = 12345
        session_id = "test_session_001"
        
        # Set up mock session that is already active
        mock_session = MagicMock(spec=Session)
        mock_session.id = session_id
        mock_session_manager.storage.load.return_value = mock_session
        mock_session_manager.get_active_session.return_value = mock_session
        
        await orchestrator._restore_session(chat_id, session_id)
        
        # Should send "already active" message
        mock_bot.send_message.assert_called_once()
        call_args = str(mock_bot.send_message.call_args)
        assert "ativa" in call_args.lower() or "active" in call_args.lower()

    @pytest.mark.asyncio
    async def test_restore_session_error(
        self, orchestrator, mock_bot, mock_session_manager
    ):
        """Verify handling of session load errors."""
        chat_id = 12345
        session_id = "nonexistent_session"
        
        # Make storage.load raise an exception
        mock_session_manager.storage.load.side_effect = Exception("Session corrupted")
        
        await orchestrator._restore_session(chat_id, session_id)
        
        # Should send error message with recovery keyboard
        mock_bot.send_message.assert_called_once()
        call_kwargs = mock_bot.send_message.call_args
        assert "reply_markup" in str(call_kwargs)


class TestCloseAction:
    """Test close action handler."""

    @pytest.mark.asyncio
    async def test_close_clears_awaiting_state(self, orchestrator, callback_event):
        """Verify that close action clears awaiting state."""
        chat_id = callback_event.chat_id
        
        # Set up awaiting state
        orchestrator._awaiting_search_query[chat_id] = True
        
        # Handle close
        callback_event.callback_value = "close"
        await orchestrator._handle_close_action(callback_event)
        
        # State should be cleared
        assert chat_id not in orchestrator._awaiting_search_query

    @pytest.mark.asyncio
    async def test_close_cancels_timeout(self, orchestrator, callback_event):
        """Verify that close action cancels timeout task."""
        chat_id = callback_event.chat_id
        
        # Set up timeout task
        async def dummy_timeout():
            await asyncio.sleep(60)
        
        orchestrator._search_timeout_tasks[chat_id] = asyncio.create_task(dummy_timeout())
        
        # Handle close
        callback_event.callback_value = "close"
        await orchestrator._handle_close_action(callback_event)
        
        # Timeout should be cancelled
        assert chat_id not in orchestrator._search_timeout_tasks


class TestEmptyQueryHandling:
    """Test empty query edge case (T039)."""

    @pytest.mark.asyncio
    async def test_empty_query_shows_error(self, orchestrator, mock_bot, text_event):
        """Verify that empty query shows error message."""
        chat_id = text_event.chat_id
        orchestrator._awaiting_search_query[chat_id] = True
        
        # Process empty query
        await orchestrator._process_search_query(text_event, "")
        
        mock_bot.send_message.assert_called_once()
        call_args = str(mock_bot.send_message.call_args)
        assert "descreva" in call_args.lower()


class TestPageCallbackBehavior:
    """Validate pagination callbacks per contract."""

    @pytest.mark.asyncio
    async def test_invalid_page_sends_warning(self, orchestrator, mock_bot):
        event = MagicMock(spec=TelegramEvent)
        event.chat_id = 12345
        await orchestrator._handle_page_callback(event, "abc")
        mock_bot.send_message.assert_called_once()
        assert "página inválida" in str(mock_bot.send_message.call_args).lower()

    @pytest.mark.asyncio
    async def test_current_page_no_message(self, orchestrator, mock_bot):
        event = MagicMock(spec=TelegramEvent)
        event.chat_id = 12345
        await orchestrator._handle_page_callback(event, "current")
        mock_bot.send_message.assert_not_called()


class TestHelpFallbackToggle:
    """Ensure help fallback obeys configuration toggle."""

    @pytest.mark.asyncio
    async def test_help_fallback_disabled(self, orchestrator, mock_bot):
        orchestrator.ui_service = None
        orchestrator._help_fallback_enabled = False
        event = MagicMock(spec=TelegramEvent)
        event.chat_id = 12345

        await orchestrator._handle_help_callback(event, "unknown")

        mock_bot.send_message.assert_called_once()
        assert "ajuda contextual indisponível" in str(mock_bot.send_message.call_args).lower()

    @pytest.mark.asyncio
    async def test_whitespace_query_shows_error(self, orchestrator, mock_bot, text_event):
        """Verify that whitespace-only query shows error message."""
        chat_id = text_event.chat_id
        orchestrator._awaiting_search_query[chat_id] = True
        
        # Process whitespace query (note: query is already stripped in handle_event)
        await orchestrator._process_search_query(text_event, "   ")
        
        # Empty after strip should trigger error
        mock_bot.send_message.assert_called_once()
