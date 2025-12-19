"""Contract tests for UIService.

Per contracts/ui-service.md for 005-telegram-ux-overhaul.

These tests verify:
1. UIService implements the UIServiceProtocol interface correctly
2. Messages include appropriate keyboards
3. Preferences are respected (simplified_ui)
4. Callbacks follow the defined format
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from telegram import InlineKeyboardMarkup

from src.models.session import Session, SessionState
from src.models.ui_state import (
    KeyboardType,
    UIPreferences,
    ProgressState,
    ProgressStatus,
    OperationType,
    ConfirmationType,
    ConfirmationContext,
    ConfirmationOption,
)
from src.lib.config import get_ui_config

# Configure pytest-asyncio
pytestmark = pytest.mark.asyncio


class TestUIServiceProtocol:
    """Verify UIService implements the protocol interface."""

    @pytest.fixture
    def mock_bot(self):
        """Create a mock Telegram bot."""
        bot = AsyncMock()
        # Mock send_message to return a message with an id
        mock_message = MagicMock()
        mock_message.message_id = 12345
        bot.send_message.return_value = mock_message
        return bot

    @pytest.fixture
    def sample_session(self) -> Session:
        """Create a sample session for testing."""
        return Session(
            id="2025-12-19_15-30-00",
            state=SessionState.COLLECTING,
            created_at=datetime.now(),
            chat_id=123456,
            intelligible_name="test-session",
        )

    @pytest.fixture
    def default_preferences(self) -> UIPreferences:
        """Create default UI preferences."""
        return UIPreferences(simplified_ui=False)

    @pytest.fixture
    def simplified_preferences(self) -> UIPreferences:
        """Create simplified UI preferences."""
        return UIPreferences(simplified_ui=True)


class TestSendSessionCreated(TestUIServiceProtocol):
    """Tests for UIService.send_session_created()."""

    @pytest.mark.asyncio
    async def test_send_session_created_returns_message(
        self, mock_bot, sample_session
    ):
        """send_session_created should return a message with message_id."""
        from src.services.telegram.ui_service import UIService

        ui_service = UIService(bot=mock_bot)
        
        result = await ui_service.send_session_created(
            chat_id=123456,
            session=sample_session,
            audio_count=1,
        )
        
        assert result is not None
        assert hasattr(result, "message_id")

    @pytest.mark.asyncio
    async def test_send_session_created_includes_keyboard(
        self, mock_bot, sample_session
    ):
        """Session creation message must include inline keyboard."""
        from src.services.telegram.ui_service import UIService

        ui_service = UIService(bot=mock_bot)
        
        await ui_service.send_session_created(
            chat_id=123456,
            session=sample_session,
            audio_count=1,
        )
        
        # Verify send_message was called with reply_markup
        mock_bot.send_message.assert_called_once()
        call_kwargs = mock_bot.send_message.call_args.kwargs
        assert "reply_markup" in call_kwargs
        assert isinstance(call_kwargs["reply_markup"], InlineKeyboardMarkup)

    @pytest.mark.asyncio
    async def test_send_session_created_keyboard_has_required_buttons(
        self, mock_bot, sample_session
    ):
        """SESSION_ACTIVE keyboard should have finalize, status, help buttons."""
        from src.services.telegram.ui_service import UIService

        ui_service = UIService(bot=mock_bot)
        
        await ui_service.send_session_created(
            chat_id=123456,
            session=sample_session,
            audio_count=1,
        )
        
        call_kwargs = mock_bot.send_message.call_args.kwargs
        keyboard = call_kwargs["reply_markup"]
        
        # Flatten all buttons from all rows
        all_callbacks = []
        for row in keyboard.inline_keyboard:
            for button in row:
                all_callbacks.append(button.callback_data)
        
        # Verify required callbacks exist
        assert any("finalize" in cb for cb in all_callbacks), "Missing finalize button"
        assert any("status" in cb for cb in all_callbacks), "Missing status button"
        assert any("help" in cb for cb in all_callbacks), "Missing help button"


class TestSendAudioReceived(TestUIServiceProtocol):
    """Tests for UIService.send_audio_received()."""

    @pytest.mark.asyncio
    async def test_send_audio_received_returns_message(self, mock_bot):
        """send_audio_received should return a message."""
        from src.services.telegram.ui_service import UIService

        ui_service = UIService(bot=mock_bot)
        
        result = await ui_service.send_audio_received(
            chat_id=123456,
            audio_number=2,
            session_name="test-session",
        )
        
        assert result is not None

    @pytest.mark.asyncio
    async def test_send_audio_received_includes_sequence_number(self, mock_bot):
        """Audio receipt should include the sequence number."""
        from src.services.telegram.ui_service import UIService

        ui_service = UIService(bot=mock_bot)
        
        await ui_service.send_audio_received(
            chat_id=123456,
            audio_number=5,
            session_name="test-session",
        )
        
        call_kwargs = mock_bot.send_message.call_args.kwargs
        assert "5" in call_kwargs["text"]


class TestBuildKeyboard(TestUIServiceProtocol):
    """Tests for UIService.build_keyboard()."""

    def test_build_keyboard_session_active_has_finalize(self, mock_bot):
        """SESSION_ACTIVE keyboard should have finalize button."""
        from src.services.telegram.ui_service import UIService

        ui_service = UIService(bot=mock_bot)
        
        keyboard = ui_service.build_keyboard(KeyboardType.SESSION_ACTIVE)
        
        all_callbacks = []
        for row in keyboard.inline_keyboard:
            for button in row:
                all_callbacks.append(button.callback_data)
        
        assert any("finalize" in cb for cb in all_callbacks)

    def test_build_keyboard_session_active_has_status(self, mock_bot):
        """SESSION_ACTIVE keyboard should have status button."""
        from src.services.telegram.ui_service import UIService

        ui_service = UIService(bot=mock_bot)
        
        keyboard = ui_service.build_keyboard(KeyboardType.SESSION_ACTIVE)
        
        all_callbacks = []
        for row in keyboard.inline_keyboard:
            for button in row:
                all_callbacks.append(button.callback_data)
        
        assert any("status" in cb for cb in all_callbacks)

    def test_build_keyboard_session_active_has_help(self, mock_bot):
        """SESSION_ACTIVE keyboard should have help button."""
        from src.services.telegram.ui_service import UIService

        ui_service = UIService(bot=mock_bot)
        
        keyboard = ui_service.build_keyboard(KeyboardType.SESSION_ACTIVE)
        
        all_callbacks = []
        for row in keyboard.inline_keyboard:
            for button in row:
                all_callbacks.append(button.callback_data)
        
        assert any("help" in cb for cb in all_callbacks)

    def test_build_keyboard_error_recovery_has_retry(self, mock_bot):
        """ERROR_RECOVERY keyboard should have retry button."""
        from src.services.telegram.ui_service import UIService

        ui_service = UIService(bot=mock_bot)
        
        keyboard = ui_service.build_keyboard(KeyboardType.ERROR_RECOVERY)
        
        all_callbacks = []
        for row in keyboard.inline_keyboard:
            for button in row:
                all_callbacks.append(button.callback_data)
        
        assert any("retry" in cb for cb in all_callbacks)

    def test_build_keyboard_error_recovery_has_cancel(self, mock_bot):
        """ERROR_RECOVERY keyboard should have cancel button."""
        from src.services.telegram.ui_service import UIService

        ui_service = UIService(bot=mock_bot)
        
        keyboard = ui_service.build_keyboard(KeyboardType.ERROR_RECOVERY)
        
        all_callbacks = []
        for row in keyboard.inline_keyboard:
            for button in row:
                all_callbacks.append(button.callback_data)
        
        assert any("cancel" in cb for cb in all_callbacks)


class TestPreferencesRespected(TestUIServiceProtocol):
    """Tests verifying UIPreferences are respected."""

    @pytest.mark.asyncio
    async def test_simplified_ui_removes_emojis_from_message(
        self, mock_bot, sample_session
    ):
        """Simplified UI preference should remove decorative emojis from messages."""
        from src.services.telegram.ui_service import UIService

        ui_service = UIService(bot=mock_bot, preferences=UIPreferences(simplified_ui=True))
        
        await ui_service.send_session_created(
            chat_id=123456,
            session=sample_session,
            audio_count=1,
        )
        
        call_kwargs = mock_bot.send_message.call_args.kwargs
        message_text = call_kwargs["text"]
        
        # Common decorative emojis that should be removed
        decorative_emojis = ["✨", "🎙️", "🚀", "✅"]
        for emoji in decorative_emojis:
            assert emoji not in message_text, f"Emoji {emoji} found in simplified message"

    def test_simplified_ui_removes_emojis_from_buttons(self, mock_bot):
        """Simplified UI should remove emojis from button labels."""
        from src.services.telegram.ui_service import UIService

        ui_service = UIService(bot=mock_bot, preferences=UIPreferences(simplified_ui=True))
        
        keyboard = ui_service.build_keyboard(KeyboardType.SESSION_ACTIVE)
        
        # Check all button texts
        for row in keyboard.inline_keyboard:
            for button in row:
                # Common decorative emojis
                for emoji in ["✅", "📊", "❓", "❌", "🔄"]:
                    assert emoji not in button.text, f"Emoji {emoji} in button: {button.text}"


class TestCallbackDataFormat(TestUIServiceProtocol):
    """Tests verifying callback data follows the contract format."""

    def test_action_callbacks_follow_format(self, mock_bot):
        """Action callbacks should follow action:{name} format."""
        from src.services.telegram.ui_service import UIService

        ui_service = UIService(bot=mock_bot)
        keyboard = ui_service.build_keyboard(KeyboardType.SESSION_ACTIVE)
        
        action_callbacks = []
        for row in keyboard.inline_keyboard:
            for button in row:
                if button.callback_data.startswith("action:"):
                    action_callbacks.append(button.callback_data)
        
        # Verify format
        for cb in action_callbacks:
            parts = cb.split(":")
            assert len(parts) >= 2, f"Invalid callback format: {cb}"
            assert parts[0] == "action"

    def test_confirm_callbacks_follow_format(self, mock_bot):
        """Confirmation callbacks should follow confirm:{type}:{action} format."""
        from src.services.telegram.ui_service import UIService

        ui_service = UIService(bot=mock_bot)
        
        context = ConfirmationContext(
            confirmation_type=ConfirmationType.SESSION_CONFLICT,
            context_data={"message": "Test conflict"},
            options=[
                ConfirmationOption(label="Finalize", callback_data="confirm:session_conflict:finalize_new"),
                ConfirmationOption(label="Cancel", callback_data="confirm:session_conflict:cancel"),
            ],
        )
        
        keyboard = ui_service.build_keyboard(
            KeyboardType.CONFIRMATION,
            context={"confirmation_context": context}
        )
        
        confirm_callbacks = []
        for row in keyboard.inline_keyboard:
            for button in row:
                if button.callback_data.startswith("confirm:"):
                    confirm_callbacks.append(button.callback_data)
        
        # Verify format
        for cb in confirm_callbacks:
            parts = cb.split(":")
            assert len(parts) >= 3, f"Invalid confirm callback format: {cb}"
            assert parts[0] == "confirm"


class TestPaginatedText(TestUIServiceProtocol):
    """Tests for UIService.send_paginated_text()."""

    @pytest.mark.asyncio
    async def test_send_paginated_text_respects_limit(self, mock_bot):
        """Paginated messages should stay within Telegram character limit."""
        from src.services.telegram.ui_service import UIService

        ui_service = UIService(bot=mock_bot)
        config = get_ui_config()
        
        # Create text longer than limit
        long_text = "A" * (config.message_limit * 3)
        
        await ui_service.send_paginated_text(
            chat_id=123456,
            text=long_text,
            page=1,
        )
        
        call_kwargs = mock_bot.send_message.call_args.kwargs
        message_text = call_kwargs["text"]
        
        # Message should be within limit (accounting for pagination controls)
        assert len(message_text) <= config.message_limit

    @pytest.mark.asyncio
    async def test_send_paginated_text_has_navigation_keyboard(self, mock_bot):
        """Paginated text with multiple pages should have navigation."""
        from src.services.telegram.ui_service import UIService

        ui_service = UIService(bot=mock_bot)
        config = get_ui_config()
        
        # Create text that needs multiple pages
        long_text = "A" * (config.message_limit * 3)
        
        await ui_service.send_paginated_text(
            chat_id=123456,
            text=long_text,
            page=1,
        )
        
        call_kwargs = mock_bot.send_message.call_args.kwargs
        assert "reply_markup" in call_kwargs
        keyboard = call_kwargs["reply_markup"]
        
        # Should have navigation buttons
        all_callbacks = []
        for row in keyboard.inline_keyboard:
            for button in row:
                all_callbacks.append(button.callback_data)
        
        # First page should have "next" or page navigation
        assert any("page" in cb or "next" in cb for cb in all_callbacks)


class TestContextualHelp(TestUIServiceProtocol):
    """Tests for UIService.send_contextual_help()."""

    @pytest.mark.asyncio
    async def test_send_contextual_help_returns_message(
        self, mock_bot, default_preferences
    ):
        """send_contextual_help should return a message."""
        from src.services.telegram.ui_service import UIService

        ui_service = UIService(bot=mock_bot)
        
        result = await ui_service.send_contextual_help(
            chat_id=123456,
            context=KeyboardType.SESSION_ACTIVE,
            preferences=default_preferences,
        )
        
        assert result is not None

    @pytest.mark.asyncio
    async def test_contextual_help_content_varies_by_context(self, mock_bot, default_preferences):
        """Help content should be different for different contexts."""
        from src.services.telegram.ui_service import UIService

        ui_service = UIService(bot=mock_bot)
        
        # Get help for SESSION_ACTIVE
        await ui_service.send_contextual_help(
            chat_id=123456,
            context=KeyboardType.SESSION_ACTIVE,
            preferences=default_preferences,
        )
        session_active_text = mock_bot.send_message.call_args.kwargs["text"]
        
        mock_bot.reset_mock()
        
        # Get help for ERROR_RECOVERY
        await ui_service.send_contextual_help(
            chat_id=123456,
            context=KeyboardType.ERROR_RECOVERY,
            preferences=default_preferences,
        )
        error_recovery_text = mock_bot.send_message.call_args.kwargs["text"]
        
        # Help should be different
        assert session_active_text != error_recovery_text


class TestSendResults(TestUIServiceProtocol):
    """Tests for UIService.send_results()."""

    @pytest.mark.asyncio
    async def test_send_results_includes_keyboard(self, mock_bot, sample_session):
        """Results message should include action buttons keyboard."""
        from src.services.telegram.ui_service import UIService

        ui_service = UIService(bot=mock_bot)
        
        await ui_service.send_results(
            chat_id=123456,
            session=sample_session,
            transcription_preview="Test transcription preview...",
        )
        
        call_kwargs = mock_bot.send_message.call_args.kwargs
        assert "reply_markup" in call_kwargs
        assert isinstance(call_kwargs["reply_markup"], InlineKeyboardMarkup)

    @pytest.mark.asyncio
    async def test_send_results_shows_transcription_preview(
        self, mock_bot, sample_session
    ):
        """Results message should show transcription preview."""
        from src.services.telegram.ui_service import UIService

        ui_service = UIService(bot=mock_bot)
        
        preview_text = "Esta é uma prévia da transcrição..."
        
        await ui_service.send_results(
            chat_id=123456,
            session=sample_session,
            transcription_preview=preview_text,
        )
        
        call_kwargs = mock_bot.send_message.call_args.kwargs
        assert preview_text in call_kwargs["text"]


class TestSendProgress(TestUIServiceProtocol):
    """Tests for UIService.send_progress() and update_progress()."""

    @pytest.fixture
    def sample_progress(self) -> ProgressState:
        """Create sample progress state."""
        now = datetime.now()
        return ProgressState(
            operation_id="op-001",
            operation_type=OperationType.TRANSCRIPTION,
            current_step=1,
            total_steps=5,
            step_description="Transcrevendo áudio 1 de 5",
            started_at=now,
            last_update_at=now,
            status=ProgressStatus.ACTIVE,
        )

    async def test_send_progress_returns_message(
        self, mock_bot, sample_progress, default_preferences
    ):
        """send_progress should return a message for tracking."""
        from src.services.telegram.ui_service import UIService

        ui_service = UIService(bot=mock_bot)
        
        result = await ui_service.send_progress(
            chat_id=123456,
            progress=sample_progress,
            preferences=default_preferences,
        )
        
        assert result is not None
        assert hasattr(result, "message_id")

    async def test_send_progress_shows_progress_bar(
        self, mock_bot, sample_progress, default_preferences
    ):
        """Progress message should include progress bar."""
        from src.services.telegram.ui_service import UIService

        ui_service = UIService(bot=mock_bot)
        
        await ui_service.send_progress(
            chat_id=123456,
            progress=sample_progress,
            preferences=default_preferences,
        )
        
        call_kwargs = mock_bot.send_message.call_args.kwargs
        # Should contain either percentage or progress indicator
        assert "%" in call_kwargs["text"] or "Transcrevendo" in call_kwargs["text"]

    async def test_update_progress_edits_message(self, mock_bot, sample_progress, default_preferences):
        """update_progress should edit the existing message."""
        from src.services.telegram.ui_service import UIService

        ui_service = UIService(bot=mock_bot)
        
        # Create a mock message to update
        mock_message = MagicMock()
        mock_message.edit_text = AsyncMock()
        
        now = datetime.now()
        updated_progress = ProgressState(
            operation_id="op-001",
            operation_type=OperationType.TRANSCRIPTION,
            current_step=3,
            total_steps=5,
            step_description="Transcrevendo áudio 3 de 5",
            started_at=now,
            last_update_at=now,
            status=ProgressStatus.ACTIVE,
        )
        
        await ui_service.update_progress(
            message=mock_message,
            progress=updated_progress,
            preferences=default_preferences,
        )
        
        mock_message.edit_text.assert_called_once()


class TestSendRecoveryPrompt(TestUIServiceProtocol):
    """Tests for UIService.send_recovery_prompt() (crash recovery)."""

    @pytest.mark.asyncio
    async def test_send_recovery_prompt_has_resume_option(
        self, mock_bot, sample_session
    ):
        """Recovery prompt should have Resume option."""
        from src.services.telegram.ui_service import UIService

        ui_service = UIService(bot=mock_bot)
        
        await ui_service.send_recovery_prompt(
            chat_id=123456,
            session=sample_session,
        )
        
        call_kwargs = mock_bot.send_message.call_args.kwargs
        keyboard = call_kwargs["reply_markup"]
        
        all_callbacks = []
        for row in keyboard.inline_keyboard:
            for button in row:
                all_callbacks.append(button.callback_data)
        
        assert any("resume" in cb.lower() for cb in all_callbacks)

    @pytest.mark.asyncio
    async def test_send_recovery_prompt_has_finalize_option(
        self, mock_bot, sample_session
    ):
        """Recovery prompt should have Finalize option."""
        from src.services.telegram.ui_service import UIService

        ui_service = UIService(bot=mock_bot)
        
        await ui_service.send_recovery_prompt(
            chat_id=123456,
            session=sample_session,
        )
        
        call_kwargs = mock_bot.send_message.call_args.kwargs
        keyboard = call_kwargs["reply_markup"]
        
        all_callbacks = []
        for row in keyboard.inline_keyboard:
            for button in row:
                all_callbacks.append(button.callback_data)
        
        assert any("finalize" in cb.lower() for cb in all_callbacks)

    @pytest.mark.asyncio
    async def test_send_recovery_prompt_has_discard_option(
        self, mock_bot, sample_session
    ):
        """Recovery prompt should have Discard option."""
        from src.services.telegram.ui_service import UIService

        ui_service = UIService(bot=mock_bot)
        
        await ui_service.send_recovery_prompt(
            chat_id=123456,
            session=sample_session,
        )
        
        call_kwargs = mock_bot.send_message.call_args.kwargs
        keyboard = call_kwargs["reply_markup"]
        
        all_callbacks = []
        for row in keyboard.inline_keyboard:
            for button in row:
                all_callbacks.append(button.callback_data)
        
        assert any("discard" in cb.lower() for cb in all_callbacks)
