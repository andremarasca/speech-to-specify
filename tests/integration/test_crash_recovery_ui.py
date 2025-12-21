"""Integration tests for crash recovery UI flow.

Per T031d from 005-telegram-ux-overhaul.

Tests the complete crash recovery flow:
1. Orphaned session detection on startup
2. Recovery prompt UI with Resume/Finalize/Discard options
3. Callback handling for recovery actions
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from src.models.session import Session, SessionState
from src.models.ui_state import CheckpointData
from src.services.telegram.ui_service import UIService


class TestOrphanedSessionDetection:
    """Tests for orphaned session detection on startup."""

    async def test_detects_orphaned_collecting_session(self):
        """Sessions in COLLECTING state with old checkpoint should be detected."""
        from src.cli.daemon import _check_orphaned_sessions
        
        # Create a mock session manager
        mock_session_manager = MagicMock()
        
        # Create an orphaned session (COLLECTING, checkpoint > 1 hour old)
        orphaned_session = Session(
            id="2025-12-19_10-00-00",
            intelligible_name="orphaned-test",
            created_at=datetime.now() - timedelta(hours=2),
            state=SessionState.COLLECTING,
            chat_id=123456,
        )
        orphaned_session.checkpoint_data = CheckpointData(
            last_checkpoint_at=datetime.now() - timedelta(hours=2),
            last_audio_sequence=3,
        )
        
        mock_session_manager.list_sessions.return_value = [orphaned_session]
        mock_session_manager.transition_state = MagicMock()
        
        # Create mock updated session after transition
        updated_session = Session(
            id="2025-12-19_10-00-00",
            intelligible_name="orphaned-test",
            created_at=datetime.now() - timedelta(hours=2),
            state=SessionState.INTERRUPTED,
            chat_id=123456,
        )
        mock_session_manager.storage.load.return_value = updated_session
        
        # Create mock UIService
        mock_ui_service = MagicMock(spec=UIService)
        mock_ui_service.send_recovery_prompt = AsyncMock()
        
        # Run detection
        await _check_orphaned_sessions(
            session_manager=mock_session_manager,
            ui_service=mock_ui_service,
            chat_id=123456,
        )
        
        # Verify session was marked as INTERRUPTED
        mock_session_manager.transition_state.assert_called_once_with(
            orphaned_session.id,
            SessionState.INTERRUPTED,
        )
        
        # Verify recovery prompt was sent
        mock_ui_service.send_recovery_prompt.assert_called_once()
        call_kwargs = mock_ui_service.send_recovery_prompt.call_args.kwargs
        assert call_kwargs["chat_id"] == 123456
        assert call_kwargs["session"].id == updated_session.id

    async def test_ignores_recent_sessions(self):
        """Sessions with recent checkpoint should not be detected."""
        from src.cli.daemon import _check_orphaned_sessions
        
        mock_session_manager = MagicMock()
        
        # Create a recent session (COLLECTING, checkpoint < 1 hour old)
        recent_session = Session(
            id="2025-12-19_15-30-00",
            intelligible_name="recent-test",
            created_at=datetime.now() - timedelta(minutes=30),
            state=SessionState.COLLECTING,
            chat_id=123456,
        )
        recent_session.checkpoint_data = CheckpointData(
            last_checkpoint_at=datetime.now() - timedelta(minutes=30),
            last_audio_sequence=2,
        )
        
        mock_session_manager.list_sessions.return_value = [recent_session]
        
        mock_ui_service = MagicMock(spec=UIService)
        mock_ui_service.send_recovery_prompt = AsyncMock()
        
        await _check_orphaned_sessions(
            session_manager=mock_session_manager,
            ui_service=mock_ui_service,
            chat_id=123456,
        )
        
        # Should not transition or send prompt
        mock_session_manager.transition_state.assert_not_called()
        mock_ui_service.send_recovery_prompt.assert_not_called()

    async def test_ignores_completed_sessions(self):
        """Sessions in terminal states should be ignored."""
        from src.cli.daemon import _check_orphaned_sessions
        
        mock_session_manager = MagicMock()
        
        # Create completed sessions
        completed = Session(
            id="2025-12-19_10-00-00",
            state=SessionState.READY,
            created_at=datetime.now() - timedelta(hours=2),
            chat_id=123456,
        )
        error = Session(
            id="2025-12-19_09-00-00",
            state=SessionState.ERROR,
            created_at=datetime.now() - timedelta(hours=3),
            chat_id=123456,
        )
        
        mock_session_manager.list_sessions.return_value = [completed, error]
        
        mock_ui_service = MagicMock(spec=UIService)
        mock_ui_service.send_recovery_prompt = AsyncMock()
        
        await _check_orphaned_sessions(
            session_manager=mock_session_manager,
            ui_service=mock_ui_service,
            chat_id=123456,
        )
        
        # Should not transition or send prompt
        mock_session_manager.transition_state.assert_not_called()
        mock_ui_service.send_recovery_prompt.assert_not_called()


class TestRecoveryPromptUI:
    """Tests for recovery prompt user interface."""

    async def test_recovery_prompt_has_all_options(self):
        """Recovery prompt should have Resume, Finalize, and Discard options."""
        mock_bot = AsyncMock()
        mock_sent = MagicMock()
        mock_sent.message_id = 1000
        mock_bot.send_message.return_value = mock_sent
        
        ui_service = UIService(bot=mock_bot)
        
        session = Session(
            id="2025-12-19_10-00-00",
            intelligible_name="recovery-test",
            created_at=datetime.now() - timedelta(hours=2),
            state=SessionState.INTERRUPTED,
            chat_id=123456,
        )
        
        await ui_service.send_recovery_prompt(
            chat_id=123456,
            session=session,
        )
        
        mock_bot.send_message.assert_called_once()
        call_kwargs = mock_bot.send_message.call_args.kwargs
        
        assert "reply_markup" in call_kwargs
        keyboard = call_kwargs["reply_markup"]
        
        all_callbacks = []
        for row in keyboard.inline_keyboard:
            for button in row:
                all_callbacks.append(button.callback_data)
        
        # Should have all three recovery options
        assert any("resume" in cb.lower() for cb in all_callbacks), "Missing resume option"
        assert any("finalize" in cb.lower() for cb in all_callbacks), "Missing finalize option"
        assert any("discard" in cb.lower() for cb in all_callbacks), "Missing discard option"


class TestRecoveryCallbackHandling:
    """Tests for recovery callback handling."""

    async def test_resume_callback_transitions_to_collecting(self):
        """Resume callback should transition session back to COLLECTING."""
        from src.cli.daemon import VoiceOrchestrator
        from src.services.telegram.adapter import TelegramEvent
        
        # Create mock components
        mock_bot = MagicMock()
        mock_bot.send_message = AsyncMock()
        
        mock_session_manager = MagicMock()
        interrupted_session = Session(
            id="2025-12-19_10-00-00",
            state=SessionState.INTERRUPTED,
            created_at=datetime.now() - timedelta(hours=2),
            chat_id=123456,
        )
        mock_session_manager.list_sessions.return_value = [interrupted_session]
        mock_session_manager.transition_state = MagicMock()
        
        orchestrator = VoiceOrchestrator(
            bot=mock_bot,
            session_manager=mock_session_manager,
        )
        
        # Create recover:resume callback event
        event = TelegramEvent.callback(
            chat_id=123456,
            callback_data="recover:resume_session",
            message_id=1000,
        )
        
        await orchestrator._handle_recover_callback(event, "resume_session")
        
        # Should transition to COLLECTING
        mock_session_manager.transition_state.assert_called_once_with(
            interrupted_session.id,
            SessionState.COLLECTING,
        )
        
        # Should send confirmation message
        mock_bot.send_message.assert_called_once()

    async def test_finalize_callback_starts_transcription(self):
        """Finalize callback should finalize session and start transcription."""
        from src.cli.daemon import VoiceOrchestrator
        from src.services.telegram.adapter import TelegramEvent
        
        mock_bot = MagicMock()
        mock_bot.send_message = AsyncMock()
        
        mock_session_manager = MagicMock()
        interrupted_session = Session(
            id="2025-12-19_10-00-00",
            state=SessionState.INTERRUPTED,
            created_at=datetime.now() - timedelta(hours=2),
            chat_id=123456,
        )
        mock_session_manager.list_sessions.return_value = [interrupted_session]
        mock_session_manager.transition_state = MagicMock()
        mock_session_manager.finalize_session = MagicMock(return_value=interrupted_session)
        
        orchestrator = VoiceOrchestrator(
            bot=mock_bot,
            session_manager=mock_session_manager,
        )
        orchestrator._run_transcription = AsyncMock()
        
        event = TelegramEvent.callback(
            chat_id=123456,
            callback_data="recover:finalize_orphan",
            message_id=1000,
        )
        
        await orchestrator._handle_recover_callback(event, "finalize_orphan")
        
        # Should transition to COLLECTING first (required for finalize)
        mock_session_manager.transition_state.assert_called_with(
            interrupted_session.id,
            SessionState.COLLECTING,
        )
        
        # Should finalize and start transcription
        mock_session_manager.finalize_session.assert_called_once()
        orchestrator._run_transcription.assert_called_once()

    async def test_discard_callback_marks_as_error(self):
        """Discard callback should mark session as ERROR."""
        from src.cli.daemon import VoiceOrchestrator
        from src.services.telegram.adapter import TelegramEvent
        
        mock_bot = MagicMock()
        mock_bot.send_message = AsyncMock()
        
        mock_session_manager = MagicMock()
        interrupted_session = Session(
            id="2025-12-19_10-00-00",
            state=SessionState.INTERRUPTED,
            created_at=datetime.now() - timedelta(hours=2),
            chat_id=123456,
        )
        mock_session_manager.list_sessions.return_value = [interrupted_session]
        mock_session_manager.transition_state = MagicMock()
        
        orchestrator = VoiceOrchestrator(
            bot=mock_bot,
            session_manager=mock_session_manager,
        )
        
        event = TelegramEvent.callback(
            chat_id=123456,
            callback_data="recover:discard_orphan",
            message_id=1000,
        )
        
        await orchestrator._handle_recover_callback(event, "discard_orphan")
        
        # Should transition to ERROR
        mock_session_manager.transition_state.assert_called_once_with(
            interrupted_session.id,
            SessionState.ERROR,
        )


class TestCheckpointSaveOnAudioReceipt:
    """Tests for checkpoint saving after audio receipt."""

    async def test_checkpoint_saved_after_audio(self):
        """Checkpoint should be saved after each audio receipt.
        
        Note: After receiving audio, the new flow immediately transcribes it,
        so the checkpoint state reflects the transcription result.
        """
        from src.cli.daemon import VoiceOrchestrator
        from src.services.telegram.adapter import TelegramEvent
        
        mock_bot = MagicMock()
        mock_bot.send_message = AsyncMock()
        mock_bot.send_chat_action = AsyncMock()
        mock_bot.download_voice = AsyncMock(return_value=1000)
        
        session = Session(
            id="2025-12-19_16-00-00",
            state=SessionState.COLLECTING,
            created_at=datetime.now(),
            chat_id=123456,
        )
        
        mock_session_manager = MagicMock()
        mock_session_manager.sessions_dir = MagicMock()
        
        # Mock audio entry
        from src.models.session import AudioEntry
        audio_entry = AudioEntry(
            sequence=1,
            telegram_file_id="test_file",
            local_filename="001_audio.ogg",
            file_size_bytes=1000,
            received_at=datetime.now(),
        )
        mock_session_manager.handle_audio_receipt.return_value = (session, audio_entry)
        
        # Mock transcription service
        mock_transcription = MagicMock()
        mock_transcription.transcribe.return_value = MagicMock(
            success=True,
            text="test transcription",
            duration_seconds=30.0,
        )
        
        orchestrator = VoiceOrchestrator(
            bot=mock_bot,
            session_manager=mock_session_manager,
            transcription_service=mock_transcription,
        )
        
        event = TelegramEvent.voice(
            chat_id=123456,
            file_id="test_file_id",
            duration=30,
        )
        
        with patch("src.cli.daemon.save_checkpoint") as mock_save:
            with patch("tempfile.NamedTemporaryFile"):
                with patch("pathlib.Path.read_bytes", return_value=b"audio_data"):
                    with patch("pathlib.Path.unlink"):
                        await orchestrator._handle_voice(event)
            
            # Verify checkpoint was saved (may be called multiple times during transcription)
            assert mock_save.called
            # Verify the final checkpoint reflects transcribed state
            final_call_kwargs = mock_save.call_args.kwargs
            assert final_call_kwargs["session"] == session
            assert final_call_kwargs["audio_sequence"] == 1
            # After immediate transcription, state is TRANSCRIBED
            assert final_call_kwargs["processing_state"] == "TRANSCRIBED"


class TestCompleteRecoveryFlow:
    """End-to-end test for complete crash recovery flow."""

    async def test_complete_crash_recovery_flow(self):
        """Test complete flow: orphan detection → prompt → resume → continue."""
        from src.cli.daemon import _check_orphaned_sessions, VoiceOrchestrator
        from src.services.telegram.adapter import TelegramEvent
        
        # Step 1: Create orphaned session
        orphaned = Session(
            id="2025-12-19_10-00-00",
            intelligible_name="crashed-session",
            created_at=datetime.now() - timedelta(hours=2),
            state=SessionState.COLLECTING,
            chat_id=123456,
        )
        orphaned.checkpoint_data = CheckpointData(
            last_checkpoint_at=datetime.now() - timedelta(hours=2),
            last_audio_sequence=3,
        )
        
        # Step 2: Detection marks as INTERRUPTED
        mock_session_manager = MagicMock()
        mock_session_manager.list_sessions.return_value = [orphaned]
        mock_session_manager.transition_state = MagicMock()
        
        interrupted = Session(
            id="2025-12-19_10-00-00",
            intelligible_name="crashed-session",
            created_at=datetime.now() - timedelta(hours=2),
            state=SessionState.INTERRUPTED,
            chat_id=123456,
        )
        mock_session_manager.storage.load.return_value = interrupted
        
        mock_bot = AsyncMock()
        mock_sent = MagicMock()
        mock_sent.message_id = 1000
        mock_bot.send_message.return_value = mock_sent
        
        mock_ui_service = MagicMock(spec=UIService)
        mock_ui_service.send_recovery_prompt = AsyncMock()
        
        await _check_orphaned_sessions(
            session_manager=mock_session_manager,
            ui_service=mock_ui_service,
            chat_id=123456,
        )
        
        # Verify detection worked
        mock_session_manager.transition_state.assert_called_with(
            orphaned.id,
            SessionState.INTERRUPTED,
        )
        mock_ui_service.send_recovery_prompt.assert_called_once()
        
        # Step 3: User taps Resume
        mock_session_manager.reset_mock()
        mock_session_manager.list_sessions.return_value = [interrupted]
        
        orchestrator = VoiceOrchestrator(
            bot=mock_bot,
            session_manager=mock_session_manager,
        )
        
        resume_event = TelegramEvent.callback(
            chat_id=123456,
            callback_data="recover:resume",
        )
        
        await orchestrator._handle_recover_callback(resume_event, "resume")
        
        # Should transition back to COLLECTING
        mock_session_manager.transition_state.assert_called_with(
            interrupted.id,
            SessionState.COLLECTING,
        )
