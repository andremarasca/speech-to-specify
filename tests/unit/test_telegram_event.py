"""Unit tests for Telegram event normalization and routing.

Tests cover TelegramEvent factories plus command/callback routing
contracts defined for the VoiceOrchestrator.
"""

import asyncio
import logging
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.cli.daemon import VoiceOrchestrator
from src.services.telegram.adapter import TelegramEvent


class TestTelegramEventCallback:
    """Tests for TelegramEvent.callback factory method."""

    def test_callback_creates_event_with_correct_type(self):
        """Callback events should have event_type='callback'."""
        event = TelegramEvent.callback(
            chat_id=123456,
            callback_data="action:finalize",
        )
        
        assert event.event_type == "callback"
        assert event.is_callback is True
        assert event.is_command is False
        assert event.is_voice is False

    def test_callback_stores_chat_id(self):
        """Callback events should store chat_id."""
        event = TelegramEvent.callback(
            chat_id=123456,
            callback_data="action:finalize",
        )
        
        assert event.chat_id == 123456

    def test_callback_stores_callback_data(self):
        """Callback events should store callback_data in payload."""
        event = TelegramEvent.callback(
            chat_id=123456,
            callback_data="action:finalize",
        )
        
        assert event.callback_data == "action:finalize"
        assert event.payload["callback_data"] == "action:finalize"

    def test_callback_stores_message_id(self):
        """Callback events should store message_id for editing."""
        event = TelegramEvent.callback(
            chat_id=123456,
            callback_data="action:finalize",
            message_id=789,
        )
        
        assert event.message_id == 789
        assert event.payload["message_id"] == 789

    def test_callback_stores_user_id(self):
        """Callback events should store user_id."""
        event = TelegramEvent.callback(
            chat_id=123456,
            callback_data="action:finalize",
            user_id=42,
        )
        
        assert event.payload["user_id"] == 42

    def test_callback_has_timestamp(self):
        """Callback events should have timestamp."""
        before = datetime.now()
        event = TelegramEvent.callback(
            chat_id=123456,
            callback_data="action:finalize",
        )
        after = datetime.now()
        
        assert before <= event.timestamp <= after


class TestCallbackActionParsing:
    """Tests for callback_action and callback_value properties."""

    def test_callback_action_extracts_prefix(self):
        """callback_action should return the prefix before first colon."""
        event = TelegramEvent.callback(
            chat_id=123456,
            callback_data="action:finalize",
        )
        
        assert event.callback_action == "action"

    def test_callback_value_extracts_remainder(self):
        """callback_value should return everything after first colon."""
        event = TelegramEvent.callback(
            chat_id=123456,
            callback_data="action:finalize",
        )
        
        assert event.callback_value == "finalize"

    def test_callback_action_for_nav(self):
        """Navigation callbacks should parse correctly."""
        event = TelegramEvent.callback(
            chat_id=123456,
            callback_data="nav:next:page_2",
        )
        
        assert event.callback_action == "nav"
        assert event.callback_value == "next:page_2"

    def test_callback_action_for_help(self):
        """Help callbacks should parse correctly."""
        event = TelegramEvent.callback(
            chat_id=123456,
            callback_data="help:voice_messages",
        )
        
        assert event.callback_action == "help"
        assert event.callback_value == "voice_messages"

    def test_callback_action_for_confirm(self):
        """Confirmation callbacks should parse correctly."""
        event = TelegramEvent.callback(
            chat_id=123456,
            callback_data="confirm:session_conflict:finalize_new",
        )
        
        assert event.callback_action == "confirm"
        assert event.callback_value == "session_conflict:finalize_new"

    def test_callback_action_for_recover(self):
        """Recovery callbacks should parse correctly."""
        event = TelegramEvent.callback(
            chat_id=123456,
            callback_data="recover:resume",
        )
        
        assert event.callback_action == "recover"
        assert event.callback_value == "resume"

    def test_callback_action_no_colon_returns_full_data(self):
        """callback_action with no colon returns full data."""
        event = TelegramEvent.callback(
            chat_id=123456,
            callback_data="noop",
        )
        
        assert event.callback_action == "noop"
        assert event.callback_value is None

    def test_callback_action_returns_none_for_non_callback(self):
        """callback_action returns None for command events."""
        event = TelegramEvent.command(
            chat_id=123456,
            command="start",
        )
        
        assert event.callback_action is None
        assert event.callback_value is None


class TestCallbackPropertyAccessOnNonCallback:
    """Tests that callback properties return None for non-callback events."""

    def test_callback_data_none_for_command(self):
        """callback_data should return None for command events."""
        event = TelegramEvent.command(
            chat_id=123456,
            command="start",
        )
        
        assert event.callback_data is None

    def test_callback_data_none_for_voice(self):
        """callback_data should return None for voice events."""
        event = TelegramEvent.voice(
            chat_id=123456,
            file_id="test_file_id",
        )
        
        assert event.callback_data is None

    def test_message_id_none_for_command(self):
        """message_id should return None for command events."""
        event = TelegramEvent.command(
            chat_id=123456,
            command="start",
        )
        
        assert event.message_id is None


class TestExistingEventTypes:
    """Tests that existing event types still work correctly."""

    def test_command_event_unchanged(self):
        """Command events should work as before."""
        event = TelegramEvent.command(
            chat_id=123456,
            command="start",
            args="test",
        )
        
        assert event.is_command is True
        assert event.is_voice is False
        assert event.is_callback is False
        assert event.command_name == "start"
        assert event.command_args == "test"

    def test_voice_event_unchanged(self):
        """Voice events should work as before."""
        event = TelegramEvent.voice(
            chat_id=123456,
            file_id="test_file_id",
            duration=30,
            file_size=10000,
        )
        
        assert event.is_voice is True
        assert event.is_command is False
        assert event.is_callback is False
        assert event.file_id == "test_file_id"
        assert event.duration == 30


class TestCommandRouting:
    """Ensure VoiceOrchestrator routes all contract commands."""

    @pytest.fixture()
    def orchestrator(self) -> VoiceOrchestrator:
        """Provide orchestrator with minimal dependencies for routing tests."""
        bot = MagicMock()
        bot.send_message = AsyncMock()
        return VoiceOrchestrator(bot=bot, session_manager=MagicMock())

    @pytest.mark.parametrize(
        "command, handler_name",
        [
            ("start", "_cmd_start"),
            ("finish", "_cmd_finish"),
            ("done", "_cmd_finish"),
            ("status", "_cmd_status"),
            ("transcripts", "_cmd_transcripts"),
            ("process", "_cmd_process"),
            ("list", "_cmd_list"),
            ("get", "_cmd_get"),
            ("session", "_cmd_session"),
            ("preferences", "_cmd_preferences"),
            ("help", "_cmd_help"),
            ("search", "_cmd_search"),
        ],
    )
    def test_commands_dispatch_to_handlers(self, orchestrator: VoiceOrchestrator, command: str, handler_name: str):
        handler = AsyncMock()
        setattr(orchestrator, handler_name, handler)

        event = TelegramEvent.command(chat_id=123456, command=command)
        asyncio.run(orchestrator._handle_command(event))

        handler.assert_awaited_once_with(event)

    def test_unknown_command_warns(self, orchestrator: VoiceOrchestrator, caplog: pytest.LogCaptureFixture):
        event = TelegramEvent.command(chat_id=123456, command="unknown")

        with caplog.at_level(logging.WARNING):
            asyncio.run(orchestrator._handle_command(event))

        assert "Unknown command" in caplog.text


class TestCallbackRouting:
    """Ensure callback prefixes route to dedicated handlers."""

    @pytest.fixture()
    def orchestrator(self) -> VoiceOrchestrator:
        orchestrator = VoiceOrchestrator(bot=MagicMock(), session_manager=MagicMock())

        orchestrator._handle_action_callback = AsyncMock()
        orchestrator._handle_help_callback = AsyncMock()
        orchestrator._handle_recover_callback = AsyncMock()
        orchestrator._handle_confirm_callback = AsyncMock()
        orchestrator._handle_nav_callback = AsyncMock()
        orchestrator._handle_retry_callback = AsyncMock()
        orchestrator._handle_page_callback = AsyncMock()
        orchestrator._handle_search_select_callback = AsyncMock()

        return orchestrator

    @pytest.mark.parametrize(
        "callback_data, handler_name, expected_value",
        [
            ("action:finalize", "_handle_action_callback", "finalize"),
            ("help:session", "_handle_help_callback", "session"),
            ("recover:resume_session", "_handle_recover_callback", "resume_session"),
            ("confirm:session_conflict:new", "_handle_confirm_callback", "session_conflict:new"),
            ("nav:next:page", "_handle_nav_callback", "next:page"),
            ("retry:last_action", "_handle_retry_callback", "last_action"),
            ("page:2", "_handle_page_callback", "2"),
            ("search:select:abc123", "_handle_search_select_callback", "select:abc123"),
        ],
    )
    def test_callback_dispatches_by_prefix(
        self,
        orchestrator: VoiceOrchestrator,
        callback_data: str,
        handler_name: str,
        expected_value: str,
    ) -> None:
        handler = getattr(orchestrator, handler_name)

        event = TelegramEvent.callback(chat_id=123456, callback_data=callback_data)
        asyncio.run(orchestrator._handle_callback(event))

        handler.assert_awaited_once_with(event, expected_value)

    def test_unknown_callback_logs_warning(self, orchestrator: VoiceOrchestrator, caplog: pytest.LogCaptureFixture):
        event = TelegramEvent.callback(chat_id=123456, callback_data="noop")

        with caplog.at_level(logging.WARNING):
            asyncio.run(orchestrator._handle_callback(event))

        assert "Unknown callback action" in caplog.text
