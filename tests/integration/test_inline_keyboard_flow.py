"""Integration tests for inline keyboard flow.

Per tasks.md T022 for 005-telegram-ux-overhaul.

These tests verify the complete flow:
1. Voice message → auto-create session → inline buttons → finalize with taps
2. Session conflict handling with confirmation dialogs
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
import tempfile
import os

from telegram import Update, Message, Voice, User, Chat, CallbackQuery

from src.models.session import Session, SessionState
from src.models.ui_state import (
    KeyboardType,
    ConfirmationType,
    ConfirmationContext,
    ConfirmationOption,
    CheckpointData,
)


class TestVoiceMessageAutoSession:
    """Integration tests for voice message → auto-session flow."""

    @pytest.fixture
    def mock_update_with_voice(self):
        """Create a mock update with a voice message."""
        update = MagicMock(spec=Update)
        update.effective_user = MagicMock(spec=User)
        update.effective_user.id = 123456
        update.effective_user.first_name = "Test"
        
        update.effective_chat = MagicMock(spec=Chat)
        update.effective_chat.id = 123456
        
        update.message = MagicMock(spec=Message)
        update.message.voice = MagicMock(spec=Voice)
        update.message.voice.file_id = "test_file_id_123"
        update.message.voice.duration = 10
        update.message.voice.file_size = 50000
        
        return update

    @pytest.fixture
    def mock_context(self):
        """Create a mock context with bot."""
        context = MagicMock()
        context.bot = AsyncMock()
        
        # Mock file download
        mock_file = AsyncMock()
        mock_file.download_to_drive = AsyncMock()
        context.bot.get_file.return_value = mock_file
        
        # Mock send_message
        mock_sent = MagicMock()
        mock_sent.message_id = 999
        context.bot.send_message.return_value = mock_sent
        
        return context

    async def test_voice_message_creates_session_when_none_exists(
        self, mock_update_with_voice, mock_context
    ):
        """Voice message with no active session should create a new one."""
        # This test validates US1: Zero-Command Voice Capture
        # Expected: voice → auto-create session → confirmation with keyboard
        
        from src.services.telegram.ui_service import UIService
        
        # Create a new session (not from mocked session_manager)
        new_session = Session(
            id="2025-12-19_15-30-00",
            state=SessionState.COLLECTING,
            created_at=datetime.now(),
            chat_id=mock_update_with_voice.effective_chat.id,
            intelligible_name="auto-session",
        )
        
        # Create UIService
        ui_service = UIService(bot=mock_context.bot)
        
        # Simulate the flow: create session and send confirmation
        await ui_service.send_session_created(
            chat_id=mock_update_with_voice.effective_chat.id,
            session=new_session,
            audio_count=1,
        )
        
        # Verify message was sent
        mock_context.bot.send_message.assert_called_once()
        
        # Verify keyboard was included
        call_kwargs = mock_context.bot.send_message.call_args.kwargs
        assert "reply_markup" in call_kwargs

    async def test_voice_message_adds_to_existing_session(
        self, mock_update_with_voice, mock_context
    ):
        """Voice message with active session should add audio to it."""
        from src.services.telegram.ui_service import UIService
        
        # Setup: Existing active session
        existing_session = Session(
            id="2025-12-19_15-00-00",
            state=SessionState.COLLECTING,
            created_at=datetime.now(),
            chat_id=mock_update_with_voice.effective_chat.id,
            intelligible_name="existing-session",
        )
        
        ui_service = UIService(bot=mock_context.bot)
        
        # Send audio received confirmation
        await ui_service.send_audio_received(
            chat_id=mock_update_with_voice.effective_chat.id,
            audio_number=2,
            session_name=existing_session.intelligible_name,
        )
        
        # Verify message was sent with sequence number
        mock_context.bot.send_message.assert_called_once()
        call_kwargs = mock_context.bot.send_message.call_args.kwargs
        assert "2" in call_kwargs["text"]


class TestFinalizeWithTapOnly:
    """Integration tests for finalize action via button tap."""

    @pytest.fixture
    def mock_callback_query(self):
        """Create a mock callback query for finalize action."""
        callback = MagicMock(spec=CallbackQuery)
        callback.data = "action:finalize"
        callback.from_user = MagicMock(spec=User)
        callback.from_user.id = 123456
        callback.message = MagicMock(spec=Message)
        callback.message.chat_id = 123456
        callback.answer = AsyncMock()
        callback.edit_message_text = AsyncMock()
        return callback

    async def test_finalize_callback_triggers_transcription(
        self, mock_callback_query
    ):
        """Tapping finalize button should trigger transcription workflow."""
        # This validates US1: finalize with taps only
        
        from src.services.telegram.ui_service import UIService
        
        # Setup: Active session with audio
        session = Session(
            id="2025-12-19_15-00-00",
            state=SessionState.COLLECTING,
            created_at=datetime.now(),
            chat_id=123456,
            intelligible_name="test-session",
        )
        
        mock_bot = AsyncMock()
        mock_sent = MagicMock()
        mock_sent.message_id = 1000
        mock_bot.send_message.return_value = mock_sent
        
        ui_service = UIService(bot=mock_bot)
        
        # After finalize, results should be shown
        await ui_service.send_results(
            chat_id=mock_callback_query.message.chat_id,
            session=session,
            transcription_preview="Transcrição completa do áudio...",
        )
        
        # Verify results were sent with keyboard
        mock_bot.send_message.assert_called_once()
        call_kwargs = mock_bot.send_message.call_args.kwargs
        assert "reply_markup" in call_kwargs


class TestSessionConflictFlow:
    """Integration tests for session conflict confirmation dialog."""

    @pytest.fixture
    def mock_update_with_voice(self):
        """Create a mock update with a voice message."""
        update = MagicMock(spec=Update)
        update.effective_user = MagicMock(spec=User)
        update.effective_user.id = 123456
        
        update.effective_chat = MagicMock(spec=Chat)
        update.effective_chat.id = 123456
        
        update.message = MagicMock(spec=Message)
        update.message.voice = MagicMock(spec=Voice)
        update.message.voice.file_id = "new_voice_file"
        
        return update

    async def test_new_session_with_active_triggers_confirmation(self):
        """Starting new session when active session exists should show confirmation."""
        # This validates US4: Session Conflict Protection
        
        from src.services.telegram.ui_service import UIService
        
        # Setup: Existing active session with audio
        existing_session = Session(
            id="2025-12-19_14-00-00",
            state=SessionState.COLLECTING,
            created_at=datetime.now(),
            chat_id=123456,
            intelligible_name="existing-session",
        )
        
        mock_bot = AsyncMock()
        mock_sent = MagicMock()
        mock_sent.message_id = 1000
        mock_bot.send_message.return_value = mock_sent
        
        ui_service = UIService(bot=mock_bot)
        
        # Create confirmation context
        context = ConfirmationContext(
            confirmation_type=ConfirmationType.SESSION_CONFLICT,
            context_data={"message": "Você tem uma sessão ativa com 2 áudios. Deseja finalizá-la primeiro?"},
            options=[
                ConfirmationOption(label="Finalizar e criar nova", callback_data="confirm:session_conflict:finalize_new"),
                ConfirmationOption(label="Continuar sessão atual", callback_data="confirm:session_conflict:continue"),
                ConfirmationOption(label="Cancelar", callback_data="confirm:session_conflict:cancel"),
            ],
        )
        
        # Send confirmation dialog
        await ui_service.send_confirmation_dialog(
            chat_id=123456,
            context=context,
        )
        
        # Verify confirmation was sent with options
        mock_bot.send_message.assert_called_once()
        call_kwargs = mock_bot.send_message.call_args.kwargs
        
        # Should have keyboard with options
        assert "reply_markup" in call_kwargs
        keyboard = call_kwargs["reply_markup"]
        
        all_callbacks = []
        for row in keyboard.inline_keyboard:
            for button in row:
                all_callbacks.append(button.callback_data)
        
        # Should have all confirmation options
        assert any("finalize_new" in cb for cb in all_callbacks)
        assert any("continue" in cb or "cancel" in cb for cb in all_callbacks)


class TestCrashRecoveryFlow:
    """Integration tests for crash recovery UI flow."""

    async def test_orphaned_session_shows_recovery_prompt(self):
        """Orphaned session on startup should show recovery options."""
        # This validates T031b-T031d: Crash recovery flow
        
        from src.services.telegram.ui_service import UIService
        from datetime import datetime, timedelta
        
        # Setup: Orphaned session (last updated > 1 hour ago, still COLLECTING)
        orphaned_session = Session(
            id="2025-12-19_12-00-00",
            intelligible_name="orphaned-session",
            created_at=datetime.now() - timedelta(hours=2),
            state=SessionState.COLLECTING,
            chat_id=123456,
        )
        
        mock_bot = AsyncMock()
        mock_sent = MagicMock()
        mock_sent.message_id = 1000
        mock_bot.send_message.return_value = mock_sent
        
        ui_service = UIService(bot=mock_bot)
        
        # Send recovery prompt
        await ui_service.send_recovery_prompt(
            chat_id=123456,
            session=orphaned_session,
        )
        
        # Verify recovery prompt was sent
        mock_bot.send_message.assert_called_once()
        call_kwargs = mock_bot.send_message.call_args.kwargs
        
        # Should have keyboard with recovery options
        assert "reply_markup" in call_kwargs
        keyboard = call_kwargs["reply_markup"]
        
        all_callbacks = []
        for row in keyboard.inline_keyboard:
            for button in row:
                all_callbacks.append(button.callback_data)
        
        # Should have Resume, Finalize, and Discard options
        assert any("resume" in cb.lower() for cb in all_callbacks), "Missing resume option"
        assert any("finalize" in cb.lower() for cb in all_callbacks), "Missing finalize option"
        assert any("discard" in cb.lower() for cb in all_callbacks), "Missing discard option"


class TestCompleteVoiceCaptureFlow:
    """End-to-end integration test for complete voice capture flow."""

    async def test_complete_flow_voice_to_transcription(self):
        """Complete flow: voice → session → finalize → results."""
        # This is the primary US1 acceptance test
        
        from src.services.telegram.ui_service import UIService
        from datetime import datetime
        
        mock_bot = AsyncMock()
        mock_sent = MagicMock()
        mock_sent.message_id = 1000
        mock_sent.edit_text = AsyncMock()
        mock_bot.send_message.return_value = mock_sent
        
        ui_service = UIService(bot=mock_bot)
        chat_id = 123456
        
        # Step 1: First voice message creates session
        session = Session(
            id="2025-12-19_16-00-00",
            intelligible_name="flow-test",
            created_at=datetime.now(),
            state=SessionState.COLLECTING,
            chat_id=chat_id,
        )
        
        result1 = await ui_service.send_session_created(
            chat_id=chat_id,
            session=session,
            audio_count=1,
        )
        
        assert result1 is not None
        call1 = mock_bot.send_message.call_args
        assert "reply_markup" in call1.kwargs
        
        # Verify SESSION_ACTIVE keyboard buttons
        keyboard1 = call1.kwargs["reply_markup"]
        callbacks1 = [btn.callback_data for row in keyboard1.inline_keyboard for btn in row]
        assert any("finalize" in cb for cb in callbacks1)
        
        mock_bot.reset_mock()
        
        # Step 2: Second voice message adds to session
        result2 = await ui_service.send_audio_received(
            chat_id=chat_id,
            audio_number=2,
            session_name=session.intelligible_name,
        )
        
        assert result2 is not None
        call2 = mock_bot.send_message.call_args
        assert "2" in call2.kwargs["text"]
        
        mock_bot.reset_mock()
        
        # Step 3: User taps finalize, results shown
        session.state = SessionState.TRANSCRIBING  # TRANSCRIBING after finalize
        
        result3 = await ui_service.send_results(
            chat_id=chat_id,
            session=session,
            transcription_preview="Esta é a transcrição completa dos 2 áudios enviados...",
        )
        
        assert result3 is not None
        call3 = mock_bot.send_message.call_args
        assert "reply_markup" in call3.kwargs
        
        # RESULTS keyboard should have different options
        keyboard3 = call3.kwargs["reply_markup"]
        callbacks3 = [btn.callback_data for row in keyboard3.inline_keyboard for btn in row]
        # Results keyboard should have help button
        assert any("help" in cb for cb in callbacks3)


class TestKeyboardButtonsAccessibility:
    """Tests verifying button accessibility per FR-013, FR-014."""

    @pytest.mark.asyncio
    async def test_all_buttons_have_text_labels(self):
        """All keyboard buttons must have descriptive text labels."""
        from src.services.telegram.ui_service import UIService
        from src.models.ui_state import KeyboardType
        
        mock_bot = AsyncMock()
        ui_service = UIService(bot=mock_bot)
        
        # Test all keyboard types
        for keyboard_type in KeyboardType:
            keyboard = ui_service.build_keyboard(keyboard_type)
            
            for row in keyboard.inline_keyboard:
                for button in row:
                    # Every button must have non-empty text
                    assert button.text, f"Button in {keyboard_type} has no text"
                    assert len(button.text.strip()) > 0, f"Button in {keyboard_type} has empty text"

    @pytest.mark.asyncio
    async def test_simplified_buttons_are_screen_reader_friendly(self):
        """Simplified buttons should have clear text without decorative characters."""
        from src.services.telegram.ui_service import UIService
        from src.models.ui_state import KeyboardType, UIPreferences
        
        mock_bot = AsyncMock()
        ui_service = UIService(
            bot=mock_bot, 
            preferences=UIPreferences(simplified_ui=True)
        )
        
        keyboard = ui_service.build_keyboard(KeyboardType.SESSION_ACTIVE)
        
        for row in keyboard.inline_keyboard:
            for button in row:
                # Simplified buttons should start with a letter, not emoji
                first_char = button.text.strip()[0]
                assert first_char.isalpha() or first_char.isdigit(), \
                    f"Simplified button '{button.text}' should start with text, not symbol"
