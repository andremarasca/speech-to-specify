"""Telegram Voice Orchestrator daemon entry point.

This daemon listens for Telegram commands and voice messages,
manages voice capture sessions, and triggers local transcription
using Whisper. All processing happens locally - Telegram is only
used as a communication channel.

Usage:
    python -m src.cli.daemon
    python -m src.cli.daemon --verbose
"""

import argparse
import asyncio
import logging
import re
import signal
import sys
from datetime import datetime
from pathlib import Path
from typing import NoReturn, Optional

from src.lib.config import (
    get_telegram_config,
    get_whisper_config,
    get_session_config,
    get_search_config,
    UIConfig,
)
from src.lib.timestamps import generate_timestamp
from src.models.session import AudioEntry, ErrorEntry, MatchType, SessionState, TranscriptionStatus
from src.services.session.storage import SessionStorage
from src.services.session.manager import SessionManager, InvalidStateError
from src.services.telegram.adapter import TelegramEvent
from src.services.telegram.bot import TelegramBotAdapter
from src.services.telegram.ui_service import UIService
from src.services.transcription.base import TranscriptionService
from src.services.transcription.whisper import WhisperTranscriptionService
from src.services.session.processor import DownstreamProcessor, ProcessingError
from src.services.session.checkpoint import save_checkpoint
from src.services.presentation.progress import ProgressReporter
from src.services.presentation.error_handler import get_error_presentation_layer
from src.services.search.engine import SearchService, DefaultSearchService
from src.models.ui_state import (
    OperationType,
    ConfirmationContext,
    ConfirmationType,
    ConfirmationOption,
    KeyboardType,
)

# Configure logging
logger = logging.getLogger(__name__)


def escape_markdown(text: str) -> str:
    """Escape special Markdown characters for Telegram.
    
    Args:
        text: Text to escape
        
    Returns:
        Text with special characters escaped
    """
    if not text:
        return ""
    # Escape characters that have special meaning in Telegram Markdown
    # Order matters: escape backslash first
    special_chars = ['\\', '*', '_', '`', '[', ']', '(', ')']
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text


class VoiceOrchestrator:
    """
    Main orchestrator coordinating Telegram bot, session manager, and transcription.

    This class handles the event loop and coordinates between:
    - TelegramBotAdapter: Receives commands and voice messages
    - SessionManager: Manages session lifecycle and persistence
    - TranscriptionService: Converts audio to text using local Whisper
    - DownstreamProcessor: Integrates with narrative pipeline
    - UIService: Handles presentation layer with inline keyboards (005-telegram-ux-overhaul)
    """

    def __init__(
        self,
        bot: TelegramBotAdapter,
        session_manager: SessionManager,
        transcription_service: TranscriptionService | None = None,
        downstream_processor: DownstreamProcessor | None = None,
        ui_service: Optional[UIService] = None,
        search_service: SearchService | None = None,
    ):
        self.bot = bot
        self.session_manager = session_manager
        self.transcription_service = transcription_service
        self.downstream_processor = downstream_processor
        self.ui_service = ui_service
        self.search_service = search_service
        self._chat_id: int = 0  # Will be set from config
        # T079: Simple in-memory preferences per daemon instance
        self._simplified_ui: bool = False
        # 006-semantic-session-search: Conversational state for search flow
        self._awaiting_search_query: dict[int, bool] = {}
        self._search_timeout_tasks: dict[int, asyncio.Task] = {}
        self._search_config = get_search_config()

    def set_chat_id(self, chat_id: int) -> None:
        """Set the authorized chat ID for sending messages."""
        self._chat_id = chat_id

    async def _handle_with_error_presentation(
        self,
        handler_coro,
        event: TelegramEvent,
        context: dict | None = None,
    ) -> None:
        """Wrap handler with error presentation layer.
        
        Per T055 from 005-telegram-ux-overhaul.
        
        Catches exceptions from handlers and translates them to
        user-friendly error messages with recovery options.
        
        Args:
            handler_coro: Awaitable handler coroutine
            event: The event being processed (for chat_id)
            context: Optional context for error logging
        """
        try:
            await handler_coro
        except Exception as e:
            logger.exception(f"Handler error: {e}")
            
            # Translate to user-facing error
            error_layer = get_error_presentation_layer()
            user_error = error_layer.translate_exception(e, context)
            
            # Send error message with UIService if available
            if self.ui_service:
                try:
                    await self.ui_service.send_error(event.chat_id, user_error)
                except Exception as send_error:
                    logger.error(f"Failed to send error message: {send_error}")
                    # Fallback to plain text
                    await self.bot.send_message(
                        event.chat_id,
                        f"❌ {user_error.message}",
                    )
            else:
                # No UI service - send plain text
                await self.bot.send_message(
                    event.chat_id,
                    f"❌ {user_error.message}",
                )

    async def handle_event(self, event: TelegramEvent) -> None:
        """
        Handle incoming Telegram events.

        Routes events to appropriate handlers based on event type.
        Wraps handlers with error presentation layer (T055).
        """
        logger.debug(f"Handling event: {event.event_type} from {event.chat_id}")

        context = {"event_type": event.event_type, "chat_id": event.chat_id}

        if event.is_command:
            context["command"] = event.command_name
            await self._handle_with_error_presentation(
                self._handle_command(event),
                event,
                context,
            )
        elif event.is_voice:
            context["file_id"] = event.file_id
            await self._handle_with_error_presentation(
                self._handle_voice(event),
                event,
                context,
            )
        elif event.is_callback:
            context["callback_data"] = event.callback_data
            await self._handle_with_error_presentation(
                self._handle_callback(event),
                event,
                context,
            )
        elif event.is_text:
            # 006-semantic-session-search: Check if awaiting search query (T012)
            if self._awaiting_search_query.get(event.chat_id):
                context["search_query"] = event.text
                await self._handle_with_error_presentation(
                    self._process_search_query(event, event.text.strip()),
                    event,
                    context,
                )

    async def _handle_command(self, event: TelegramEvent) -> None:
        """Route command to appropriate handler."""
        command = event.command_name

        handlers = {
            "start": self._cmd_start,
            "finish": self._cmd_finish,
            "status": self._cmd_status,
            "transcripts": self._cmd_transcripts,
            "process": self._cmd_process,
            "list": self._cmd_list,
            "get": self._cmd_get,
            "session": self._cmd_session,
            "preferences": self._cmd_preferences,  # T079: simplified_ui toggle
        }

        handler = handlers.get(command)
        if handler:
            await handler(event)
        else:
            logger.warning(f"Unknown command: {command}")

    async def _handle_callback(self, event: TelegramEvent) -> None:
        """
        Handle callback query from inline keyboard button press.
        
        Routes callbacks based on their action type:
        - action:finalize - Finalize session and start transcription
        - action:cancel - Cancel current session
        - action:add_audio - Continue adding audio (no-op, just acknowledge)
        - help:<topic> - Send contextual help
        - recover:resume - Resume interrupted session
        - recover:finalize - Finalize interrupted session
        - recover:discard - Discard interrupted session
        - confirm:<type>:<response> - Handle confirmation dialogs
        """
        callback_action = event.callback_action
        callback_value = event.callback_value
        
        logger.debug(f"Callback action: {callback_action}, value: {callback_value}")
        
        if callback_action == "action":
            await self._handle_action_callback(event, callback_value)
        elif callback_action == "help":
            await self._handle_help_callback(event, callback_value)
        elif callback_action == "recover":
            await self._handle_recover_callback(event, callback_value)
        elif callback_action == "confirm":
            await self._handle_confirm_callback(event, callback_value)
        elif callback_action == "nav":
            await self._handle_nav_callback(event, callback_value)
        elif callback_action == "retry":
            await self._handle_retry_callback(event, callback_value)
        elif callback_action == "search":
            # 006-semantic-session-search: Handle search:select:{session_id} callbacks
            await self._handle_search_select_callback(event, callback_value)
        else:
            logger.warning(f"Unknown callback action: {callback_action}")

    async def _handle_action_callback(self, event: TelegramEvent, action: str) -> None:
        """Handle action: callbacks."""
        if action == "finalize":
            # Same as /done command
            await self._cmd_finish(event)
        elif action == "cancel":
            # Cancel active session without transcription
            active = self.session_manager.get_active_session()
            if active:
                # Mark as error/cancelled state
                try:
                    self.session_manager.transition_state(active.id, SessionState.ERROR)
                    await self.bot.send_message(
                        event.chat_id,
                        f"❌ Session cancelled: `{active.id}`",
                        parse_mode="Markdown",
                    )
                except Exception as e:
                    logger.error(f"Failed to cancel session: {e}")
            else:
                await self.bot.send_message(
                    event.chat_id,
                    "❌ No active session to cancel.",
                )
        elif action == "add_audio":
            # No-op, just acknowledge - user should send voice messages
            pass
        elif action == "continue_wait":
            # T076: User chose to continue waiting for long operation
            await self._handle_continue_wait(event)
        elif action == "cancel_operation":
            # T076: User chose to cancel the long-running operation
            await self._handle_cancel_operation(event)
        elif action == "search":
            # 006-semantic-session-search: Initiate search flow (T009-T010)
            await self._handle_search_action(event)
        elif action == "close":
            # 006-semantic-session-search: Close/dismiss search results (T023-T024)
            await self._handle_close_action(event)
        else:
            logger.warning(f"Unknown action callback: {action}")

    async def _handle_continue_wait(self, event: TelegramEvent) -> None:
        """Handle continue_wait callback - user wants to keep waiting.
        
        T076: Acknowledges the user's choice to continue waiting
        without interrupting the operation.
        """
        await self.bot.send_message(
            event.chat_id,
            "⏳ Ok, continuando a aguardar...\n"
            "Você será notificado quando a operação terminar.",
        )
        logger.debug(f"User chose to continue waiting (chat_id={event.chat_id})")

    async def _handle_cancel_operation(self, event: TelegramEvent) -> None:
        """Handle cancel_operation callback - user wants to cancel.
        
        T076: Cancels the current transcription operation.
        """
        from src.services.presentation.progress import get_progress_reporter
        
        progress_reporter = get_progress_reporter()
        
        # Find operations for this chat
        # Note: ProgressReporter tracks by operation_id, not chat_id
        # We need to cancel any active operations
        active = self.session_manager.get_active_session()
        
        if active and active.state == SessionState.TRANSCRIBING:
            # Cancel via progress reporter
            operation_id = f"transcription_{active.id}"
            await progress_reporter.cancel_operation(operation_id)
            
            # Mark session as error
            try:
                self.session_manager.transition_state(active.id, SessionState.ERROR)
            except Exception as e:
                logger.warning(f"Failed to transition session to error: {e}")
            
            await self.bot.send_message(
                event.chat_id,
                "❌ Operação cancelada pelo usuário.\n"
                f"Sessão `{active.id}` marcada como erro.",
                parse_mode="Markdown",
            )
            logger.info(f"User cancelled operation for session {active.id}")
        else:
            await self.bot.send_message(
                event.chat_id,
                "❌ Nenhuma operação em andamento para cancelar.",
            )

    async def _handle_help_callback(self, event: TelegramEvent, topic: str) -> None:
        """Handle help: callbacks - send contextual help."""
        if self.ui_service:
            await self.ui_service.send_contextual_help(
                chat_id=event.chat_id,
                topic=topic,
            )
        else:
            # Fallback to basic help
            await self.bot.send_message(
                event.chat_id,
                "❓ Use /help for available commands.",
            )

    async def _handle_recover_callback(self, event: TelegramEvent, action: str) -> None:
        """Handle recover: callbacks for crash recovery."""
        # Find interrupted session
        sessions = self.session_manager.list_sessions()
        interrupted = next(
            (s for s in sessions if s.state == SessionState.INTERRUPTED),
            None
        )
        
        if not interrupted:
            await self.bot.send_message(
                event.chat_id,
                "❌ No interrupted session found.",
            )
            return
        
        if action == "resume":
            # Resume session - transition back to COLLECTING
            try:
                self.session_manager.transition_state(interrupted.id, SessionState.COLLECTING)
                await self.bot.send_message(
                    event.chat_id,
                    f"✅ Session resumed: `{interrupted.id}`\n"
                    f"Continue sending voice messages.",
                    parse_mode="Markdown",
                )
            except Exception as e:
                logger.error(f"Failed to resume session: {e}")
                await self.bot.send_message(
                    event.chat_id,
                    f"❌ Failed to resume session: {e}",
                )
        elif action == "finalize":
            # Finalize interrupted session
            try:
                self.session_manager.transition_state(interrupted.id, SessionState.COLLECTING)
                session = self.session_manager.finalize_session(interrupted.id)
                await self._run_transcription(event.chat_id, session)
            except Exception as e:
                logger.error(f"Failed to finalize interrupted session: {e}")
                await self.bot.send_message(
                    event.chat_id,
                    f"❌ Failed to finalize session: {e}",
                )
        elif action == "discard":
            # Discard interrupted session
            try:
                self.session_manager.transition_state(interrupted.id, SessionState.ERROR)
                await self.bot.send_message(
                    event.chat_id,
                    f"🗑️ Session discarded: `{interrupted.id}`",
                    parse_mode="Markdown",
                )
            except Exception as e:
                logger.error(f"Failed to discard session: {e}")
        else:
            logger.warning(f"Unknown recover action: {action}")

    async def _handle_confirm_callback(self, event: TelegramEvent, value: str) -> None:
        """Handle confirm: callbacks for confirmation dialogs."""
        # Parse confirm type and response: "session_conflict:finalize_new"
        parts = value.split(":", 1) if value else []
        if len(parts) != 2:
            logger.warning(f"Invalid confirm callback format: {value}")
            return
        
        confirm_type, response = parts
        
        if confirm_type == "session_conflict":
            await self._handle_session_conflict_confirm(event, response)
        else:
            logger.warning(f"Unknown confirm type: {confirm_type}")

    async def _handle_session_conflict_confirm(self, event: TelegramEvent, response: str) -> None:
        """Handle session conflict confirmation response."""
        active = self.session_manager.get_active_session()
        
        if response == "finalize":
            # Finalize current session and transcribe
            if active:
                try:
                    session = self.session_manager.finalize_session(active.id)
                    await self.bot.send_message(
                        event.chat_id,
                        f"✅ Finalizing session: `{active.id}`\n⏳ Starting transcription...",
                        parse_mode="Markdown",
                    )
                    await self._run_transcription(event.chat_id, session)
                except Exception as e:
                    logger.error(f"Failed to finalize during conflict: {e}")
                    await self.bot.send_message(
                        event.chat_id,
                        f"❌ Failed to finalize: {e}",
                    )
        elif response == "new":
            # Start new session (discard current)
            if active:
                try:
                    # Mark current as error/discarded
                    self.session_manager.transition_state(active.id, SessionState.ERROR)
                except Exception as e:
                    logger.warning(f"Failed to discard session: {e}")
            
            # Create new session
            session = self.session_manager.create_session(chat_id=event.chat_id)
            await self.bot.send_message(
                event.chat_id,
                f"✅ *New Session Started*\n\n"
                f"🆔 Session: `{session.id}`\n"
                f"📁 Status: COLLECTING\n\n"
                f"Send voice messages to record audio.\n"
                f"Use /done when finished.",
                parse_mode="Markdown",
            )
        elif response == "return":
            # Return to current session
            if active:
                await self.bot.send_message(
                    event.chat_id,
                    f"✅ Returning to session: `{active.id}`\n"
                    f"🎙️ Audio files: {active.audio_count}\n\n"
                    f"Send voice messages to continue.",
                    parse_mode="Markdown",
                )
            else:
                await self.bot.send_message(
                    event.chat_id,
                    "❌ No active session. Use /start to begin.",
                )
        else:
            logger.warning(f"Unknown session conflict response: {response}")

    async def _handle_nav_callback(self, event: TelegramEvent, value: str) -> None:
        """Handle nav: callbacks for pagination."""
        # Navigation is typically handled by UIService.send_paginated_text
        # which would update the message in place
        logger.debug(f"Navigation callback: {value}")
        # TODO: Implement pagination state management if needed

    async def _handle_retry_callback(self, event: TelegramEvent, retry_action: str) -> None:
        """Handle retry: callbacks for error recovery.
        
        Per T056 from 005-telegram-ux-overhaul.
        
        Routes retry actions to appropriate handlers:
        - retry:save_audio - Retry saving audio
        - retry:transcribe - Retry transcription
        - retry:send_message - Retry sending message
        - retry:last_action - Retry the last failed action
        """
        logger.debug(f"Retry callback: {retry_action}")
        
        if retry_action == "save_audio":
            # User wants to retry saving audio
            # Acknowledge and prompt to send voice again
            await self.bot.send_message(
                event.chat_id,
                "🎤 Please send the voice message again.",
            )
        elif retry_action == "transcribe":
            # Retry transcription of last session
            active = self.session_manager.get_active_session()
            if active and active.state == SessionState.FINALIZING:
                await self._run_transcription(event.chat_id, active)
            else:
                # Look for last finalized session with failed transcription
                sessions = self.session_manager.list_sessions(limit=5)
                for session in sessions:
                    if session.has_transcription_errors:
                        await self.bot.send_message(
                            event.chat_id,
                            f"🔄 Retrying transcription for session `{session.id}`...",
                            parse_mode="Markdown",
                        )
                        await self._run_transcription(event.chat_id, session)
                        return
                        
                await self.bot.send_message(
                    event.chat_id,
                    "❌ No session found to retry transcription.",
                )
        elif retry_action == "send_message":
            # Generic retry - just acknowledge
            await self.bot.send_message(
                event.chat_id,
                "✅ Ready. Please try your action again.",
            )
        elif retry_action == "last_action":
            # Generic retry - prompt user to repeat
            await self.bot.send_message(
                event.chat_id,
                "🔄 Please try your last action again.",
            )
        else:
            logger.warning(f"Unknown retry action: {retry_action}")
            await self.bot.send_message(
                event.chat_id,
                "🔄 Please try again.",
            )

    # =========================================================================
    # Search Handlers (006-semantic-session-search)
    # =========================================================================

    async def _handle_search_action(self, event: TelegramEvent) -> None:
        """Handle action:search callback - initiate search flow.
        
        Per T009 from 006-semantic-session-search.
        
        Sends search prompt and sets awaiting state for the chat.
        """
        from src.lib.messages import SEARCH_PROMPT, SEARCH_PROMPT_SIMPLIFIED
        
        chat_id = event.chat_id
        
        # Set awaiting state
        self._awaiting_search_query[chat_id] = True
        
        # Send prompt message
        prompt = SEARCH_PROMPT_SIMPLIFIED if self._simplified_ui else SEARCH_PROMPT
        await self.bot.send_message(chat_id, prompt)
        
        # Start timeout task (T011)
        await self._start_search_timeout(chat_id)
        
        logger.debug(f"Search flow initiated for chat_id={chat_id}")

    async def _start_search_timeout(self, chat_id: int) -> None:
        """Start timeout for search query input.
        
        Per T011 from 006-semantic-session-search.
        
        Cancels any existing timeout and starts a new one. After timeout,
        clears awaiting state and sends cancellation message.
        """
        from src.lib.messages import SEARCH_TIMEOUT, SEARCH_TIMEOUT_SIMPLIFIED
        
        # Cancel existing timeout if any
        if chat_id in self._search_timeout_tasks:
            self._search_timeout_tasks[chat_id].cancel()
            del self._search_timeout_tasks[chat_id]
        
        timeout_seconds = self._search_config.query_timeout_seconds
        
        async def timeout_handler():
            try:
                await asyncio.sleep(timeout_seconds)
                # Check if still awaiting (might have been cleared)
                if self._awaiting_search_query.get(chat_id):
                    del self._awaiting_search_query[chat_id]
                    
                    # Send timeout message
                    msg = SEARCH_TIMEOUT_SIMPLIFIED if self._simplified_ui else SEARCH_TIMEOUT
                    await self.bot.send_message(chat_id, msg)
                    
                    logger.debug(f"Search timeout for chat_id={chat_id}")
            except asyncio.CancelledError:
                # Expected when query received or close pressed
                pass
            finally:
                # Cleanup task reference
                self._search_timeout_tasks.pop(chat_id, None)
        
        self._search_timeout_tasks[chat_id] = asyncio.create_task(timeout_handler())

    async def _process_search_query(self, event: TelegramEvent, query: str) -> None:
        """Process search query text from user.
        
        Per T013 from 006-semantic-session-search.
        
        Clears awaiting state, cancels timeout, executes search, and
        presents results.
        """
        from src.lib.messages import SEARCH_EMPTY_QUERY, SEARCH_EMPTY_QUERY_SIMPLIFIED
        
        chat_id = event.chat_id
        
        # Clear awaiting state (T029)
        self._awaiting_search_query.pop(chat_id, None)
        
        # Cancel timeout task (T029)
        if chat_id in self._search_timeout_tasks:
            self._search_timeout_tasks[chat_id].cancel()
            del self._search_timeout_tasks[chat_id]
        
        # Validate query is not empty (T039)
        if not query:
            msg = SEARCH_EMPTY_QUERY_SIMPLIFIED if self._simplified_ui else SEARCH_EMPTY_QUERY
            await self.bot.send_message(chat_id, msg)
            return
        
        # Check if search service is available
        if not self.search_service:
            await self.bot.send_message(
                chat_id,
                "❌ Serviço de busca não disponível.",
            )
            return
        
        # Execute search (T013)
        response = self.search_service.search(
            query=query,
            chat_id=chat_id,
            limit=self._search_config.max_results,
            min_score=self._search_config.min_similarity_score,
        )
        
        # Present results (T016)
        await self._present_search_results(chat_id, response.results)
        
        logger.info(
            f"Search completed for chat_id={chat_id}: "
            f"query='{query[:50]}...', results={len(response.results)}"
        )

    async def _present_search_results(
        self,
        chat_id: int,
        results: list,
    ) -> None:
        """Present search results as inline buttons.
        
        Per T016 from 006-semantic-session-search.
        
        Shows results as buttons if found, or no-results message with
        recovery options if empty.
        """
        from src.lib.messages import (
            SEARCH_RESULTS_HEADER, SEARCH_RESULTS_HEADER_SIMPLIFIED,
            SEARCH_NO_RESULTS, SEARCH_NO_RESULTS_SIMPLIFIED,
        )
        from src.services.telegram.keyboards import (
            build_search_results_keyboard,
            build_no_results_keyboard,
        )
        
        if results:
            # Build results keyboard (T014)
            keyboard = build_search_results_keyboard(
                results,
                simplified=self._simplified_ui,
            )
            
            # Send results header with keyboard
            header = (
                SEARCH_RESULTS_HEADER_SIMPLIFIED 
                if self._simplified_ui 
                else SEARCH_RESULTS_HEADER
            )
            await self.bot.send_message(
                chat_id,
                header,
                reply_markup=keyboard,
            )
        else:
            # Build no results keyboard (T015, T021)
            keyboard = build_no_results_keyboard(simplified=self._simplified_ui)
            
            # Send no results message with keyboard
            msg = (
                SEARCH_NO_RESULTS_SIMPLIFIED 
                if self._simplified_ui 
                else SEARCH_NO_RESULTS
            )
            await self.bot.send_message(
                chat_id,
                msg,
                reply_markup=keyboard,
            )

    async def _handle_search_select_callback(
        self,
        event: TelegramEvent,
        value: str,
    ) -> None:
        """Handle search:select:{session_id} callback.
        
        Per T017-T018 from 006-semantic-session-search.
        
        Parses session ID from callback value and calls _restore_session.
        """
        # Parse callback value: "select:{session_id}"
        parts = value.split(":", 1)
        if len(parts) != 2 or parts[0] != "select":
            logger.warning(f"Invalid search callback format: {value}")
            return
        
        session_id = parts[1]
        await self._restore_session(event.chat_id, session_id)

    async def _restore_session(self, chat_id: int, session_id: str) -> None:
        """Restore a session from search results.
        
        Per T019-T020 from 006-semantic-session-search.
        
        Loads session, sets as active, and sends confirmation with
        SESSION_ACTIVE keyboard.
        """
        from src.lib.messages import (
            SEARCH_SESSION_RESTORED, SEARCH_SESSION_RESTORED_SIMPLIFIED,
            SEARCH_SESSION_LOAD_ERROR, SEARCH_SESSION_LOAD_ERROR_SIMPLIFIED,
        )
        from src.services.telegram.keyboards import (
            build_keyboard,
            build_session_load_error_keyboard,
        )
        from src.models.ui_state import KeyboardType
        
        try:
            # Load session (T019)
            session = self.session_manager.storage.load(session_id)
            
            if not session:
                raise ValueError(f"Session not found: {session_id}")
            
            # Check if already active (T020)
            active = self.session_manager.get_active_session()
            if active and active.id == session_id:
                # Already active - just confirm
                await self.bot.send_message(
                    chat_id,
                    "✅ Esta sessão já está ativa.",
                )
                return
            
            # Note: For search restoration, we show session info but don't 
            # change its state. The user can view transcripts or process it.
            # Only sessions in COLLECTING state are "active" per SessionManager.
            
            # Build confirmation message
            session_name = escape_markdown(session.intelligible_name or session_id)
            if self._simplified_ui:
                msg = SEARCH_SESSION_RESTORED_SIMPLIFIED.format(
                    session_name=session_name,
                    audio_count=session.audio_count,
                )
            else:
                msg = SEARCH_SESSION_RESTORED.format(
                    session_name=session_name,
                    audio_count=session.audio_count,
                )
            
            # Build SESSION_ACTIVE keyboard
            keyboard = build_keyboard(
                KeyboardType.SESSION_ACTIVE,
                simplified=self._simplified_ui,
            )
            
            await self.bot.send_message(
                chat_id,
                msg,
                parse_mode="Markdown",
                reply_markup=keyboard,
            )
            
            logger.info(f"Session restored: {session_id} for chat_id={chat_id}")
            
        except Exception as e:
            # Session load error (T025-T026)
            logger.error(f"Failed to restore session {session_id}: {e}")
            
            msg = (
                SEARCH_SESSION_LOAD_ERROR_SIMPLIFIED 
                if self._simplified_ui 
                else SEARCH_SESSION_LOAD_ERROR
            )
            keyboard = build_session_load_error_keyboard(simplified=self._simplified_ui)
            
            await self.bot.send_message(
                chat_id,
                msg,
                reply_markup=keyboard,
            )

    async def _handle_close_action(self, event: TelegramEvent) -> None:
        """Handle action:close callback - dismiss search results.
        
        Per T023-T024, T030 from 006-semantic-session-search.
        
        Clears any pending search state and acknowledges the close.
        """
        chat_id = event.chat_id
        
        # Clear awaiting state if any
        self._awaiting_search_query.pop(chat_id, None)
        
        # Cancel timeout task if any (T030)
        if chat_id in self._search_timeout_tasks:
            self._search_timeout_tasks[chat_id].cancel()
            del self._search_timeout_tasks[chat_id]
        
        # Simply acknowledge - message will be dismissed by Telegram
        logger.debug(f"Search closed for chat_id={chat_id}")

    async def _cmd_start(self, event: TelegramEvent) -> None:
        """Handle /start command - create new session."""
        from src.lib.messages import WELCOME_MESSAGE, WELCOME_MESSAGE_SIMPLIFIED
        
        try:
            # T080: Check if this is a first-time user (no session history)
            all_sessions = self.session_manager.list_sessions()
            is_first_time = len(all_sessions) == 0
            
            # Check for existing active session
            active = self.session_manager.get_active_session()
            if active and active.audio_count > 0:
                # T062: Show confirmation dialog for session conflict
                context = ConfirmationContext(
                    confirmation_type=ConfirmationType.SESSION_CONFLICT,
                    context_data={
                        "message": f"Você tem uma sessão ativa com {active.audio_count} áudio(s).\nO que deseja fazer?",
                        "session_id": active.id,
                    },
                    options=[
                        ConfirmationOption(
                            label="Finalizar e Transcrever",
                            callback_data="confirm:session_conflict:finalize"
                        ),
                        ConfirmationOption(
                            label="Iniciar Nova (descartar)",
                            callback_data="confirm:session_conflict:new"
                        ),
                        ConfirmationOption(
                            label="Continuar Sessão Atual",
                            callback_data="confirm:session_conflict:return"
                        ),
                    ],
                )
                
                # Use UIService to send confirmation dialog
                if self.ui_service:
                    await self.ui_service.send_confirmation_dialog(
                        chat_id=event.chat_id,
                        context=context,
                    )
                else:
                    # Fallback: use keyboard directly
                    keyboard = self.ui_service.build_keyboard(KeyboardType.SESSION_CONFLICT)
                    await self.bot.send_message(
                        event.chat_id,
                        f"⚠️ *Sessão Ativa*\n\n"
                        f"Você tem uma sessão com {active.audio_count} áudio(s).\n"
                        f"O que deseja fazer?",
                        parse_mode="Markdown",
                        reply_markup=keyboard,
                    )
                return

            # No active session or empty session - create new
            if active and active.audio_count == 0:
                # Silent cleanup of empty session
                try:
                    self.session_manager.transition_state(active.id, SessionState.ERROR)
                except Exception:
                    pass

            # T080: Show welcome message for first-time users
            if is_first_time:
                welcome_msg = WELCOME_MESSAGE_SIMPLIFIED if self._simplified_ui else WELCOME_MESSAGE
                await self.bot.send_message(
                    event.chat_id,
                    welcome_msg,
                    parse_mode="Markdown",
                )
                return  # Don't create session automatically - let user send voice

            # Create new session
            session = self.session_manager.create_session(chat_id=event.chat_id)

            await self.bot.send_message(
                event.chat_id,
                f"✅ *Session Started*\n\n"
                f"🆔 Session: `{session.id}`\n"
                f"📁 Status: COLLECTING\n\n"
                f"Send voice messages to record audio.\n"
                f"Use /done when finished.",
                parse_mode="Markdown",
            )

            logger.info(f"Started session {session.id}")

        except Exception as e:
            logger.exception(f"Error starting session: {e}")
            await self.bot.send_message(
                event.chat_id,
                f"❌ Failed to start session: {e}",
            )

    async def _cmd_finish(self, event: TelegramEvent) -> None:
        """Handle /done or /finish command - finalize session and transcribe."""
        active = self.session_manager.get_active_session()

        if not active:
            await self.bot.send_message(
                event.chat_id,
                "❌ No active session. Use /start to begin.",
            )
            return

        if active.audio_count == 0:
            await self.bot.send_message(
                event.chat_id,
                "❌ Cannot finalize session with no audio.\n"
                "Send voice messages first, or use /start to start over.",
            )
            return

        try:
            session = self.session_manager.finalize_session(active.id)

            await self.bot.send_message(
                event.chat_id,
                f"✅ *Session Finalized*\n\n"
                f"🆔 Session: `{session.id}`\n"
                f"🎙️ Audio files: {session.audio_count}\n"
                f"📁 Status: TRANSCRIBING\n\n"
                f"⏳ Transcription starting...",
                parse_mode="Markdown",
            )

            # Run transcription
            await self._run_transcription(event.chat_id, session)

        except InvalidStateError as e:
            await self.bot.send_message(
                event.chat_id,
                f"❌ Cannot finalize: {e}",
            )
        except Exception as e:
            logger.exception(f"Error finalizing session: {e}")
            await self.bot.send_message(
                event.chat_id,
                f"❌ Failed to finalize session: {e}",
            )

    async def _run_transcription(self, chat_id: int, session) -> None:
        """
        Run transcription for all audio files in a session.

        Uses ProgressReporter for real-time progress feedback (T044).
        Updates transcription status for each audio file and writes
        transcript files to session/transcripts/ folder.
        """
        if not self.transcription_service or not self.transcription_service.is_ready():
            logger.warning("Transcription service not ready - skipping transcription")
            await self.bot.send_message(
                chat_id,
                "⚠️ Transcription service not available.\n"
                "Session finalized but transcripts not generated.",
            )
            # Transition to TRANSCRIBED anyway (empty transcripts)
            self.session_manager.transition_state(session.id, SessionState.TRANSCRIBED)
            return

        # Get session paths
        sessions_dir = self.session_manager.sessions_dir
        audio_dir = session.audio_path(sessions_dir)
        transcripts_dir = session.transcripts_path(sessions_dir)
        transcripts_dir.mkdir(exist_ok=True)

        total = session.audio_count
        success_count = 0
        error_count = 0

        # Calculate total audio duration for ETA estimation
        audio_minutes = sum(
            (entry.duration_seconds or 0) / 60.0 
            for entry in session.audio_entries
        )

        # Initialize ProgressReporter (T044)
        progress_reporter: ProgressReporter | None = None
        operation_id: str | None = None
        
        if self.ui_service:
            progress_reporter = ProgressReporter(ui_service=self.ui_service)
            operation_id = await progress_reporter.start_operation(
                operation_type=OperationType.TRANSCRIPTION,
                total_steps=total,
                chat_id=chat_id,
                audio_minutes=audio_minutes,
            )

        for i, audio_entry in enumerate(session.audio_entries, 1):
            # Update progress with ProgressReporter
            if progress_reporter and operation_id:
                await progress_reporter.update_progress(
                    operation_id,
                    current_step=i,
                    step_description=f"Transcrevendo áudio {i} de {total}...",
                )
            else:
                # Fallback: Send progress notification via bot
                await self.bot.send_message(
                    chat_id,
                    f"🎯 Transcribing audio {i}/{total}...",
                )

            audio_path = audio_dir / audio_entry.local_filename
            transcript_filename = f"{audio_entry.sequence:03d}_audio.txt"
            transcript_path = transcripts_dir / transcript_filename

            try:
                # Transcribe the audio file
                result = self.transcription_service.transcribe(audio_path)

                if result.success:
                    # Write transcript to file
                    transcript_path.write_text(result.text, encoding="utf-8")

                    # Update transcription status
                    self.session_manager.update_transcription_status(
                        session.id,
                        audio_entry.sequence,
                        TranscriptionStatus.SUCCESS,
                        transcript_filename,
                    )
                    
                    # Update session name from first successful transcription
                    if audio_entry.sequence == 1 and result.text.strip():
                        from src.services.session.name_generator import get_name_generator
                        from src.models.session import NameSource
                        
                        name_generator = get_name_generator()
                        transcript_name = name_generator.generate_from_transcript(result.text)
                        
                        if transcript_name:
                            self.session_manager.update_session_name(
                                session.id,
                                transcript_name,
                                NameSource.TRANSCRIPTION,
                            )
                            logger.info(
                                f"Updated session name from transcription: '{transcript_name}'"
                            )
                    
                    success_count += 1
                    logger.info(
                        f"Transcribed audio #{audio_entry.sequence}: "
                        f"{len(result.text)} chars"
                    )
                else:
                    # Transcription failed
                    self.session_manager.update_transcription_status(
                        session.id,
                        audio_entry.sequence,
                        TranscriptionStatus.FAILED,
                    )
                    error_count += 1
                    logger.error(
                        f"Transcription failed for audio #{audio_entry.sequence}: "
                        f"{result.error_message}"
                    )

                    # Add error to session
                    self.session_manager.add_error(
                        session.id,
                        ErrorEntry(
                            timestamp=generate_timestamp(),
                            operation="transcribe",
                            target=audio_entry.local_filename,
                            message=result.error_message or "Unknown error",
                            recoverable=False,
                        ),
                    )

            except Exception as e:
                # Unexpected error
                self.session_manager.update_transcription_status(
                    session.id,
                    audio_entry.sequence,
                    TranscriptionStatus.FAILED,
                )
                error_count += 1
                logger.exception(f"Error transcribing audio #{audio_entry.sequence}: {e}")

                self.session_manager.add_error(
                    session.id,
                    ErrorEntry(
                        timestamp=generate_timestamp(),
                        operation="transcribe",
                        target=audio_entry.local_filename,
                        message=str(e),
                        recoverable=False,
                    ),
                )

        # Transition to TRANSCRIBED
        self.session_manager.transition_state(session.id, SessionState.TRANSCRIBED)

        # Complete progress tracking
        if progress_reporter and operation_id:
            await progress_reporter.complete_operation(
                operation_id, 
                success=(error_count == 0),
            )

        # Send completion message
        status_emoji = "✅" if error_count == 0 else "⚠️"
        await self.bot.send_message(
            chat_id,
            f"{status_emoji} *Transcription Complete*\n\n"
            f"🆔 Session: `{session.id}`\n"
            f"✅ Success: {success_count}/{total}\n"
            f"❌ Errors: {error_count}/{total}\n"
            f"📁 Status: TRANSCRIBED\n\n"
            f"Use /transcripts to view results.",
            parse_mode="Markdown",
        )

        logger.info(
            f"Session {session.id} transcription complete: "
            f"{success_count} success, {error_count} errors"
        )

    async def _cmd_status(self, event: TelegramEvent) -> None:
        """Handle /status [session_ref] command - show session status.
        
        If no session reference provided, uses active session context (US4).
        """
        # Check if a session reference was provided
        session_reference = event.command_args.strip() if event.command_args else ""
        
        target_session = None
        
        if session_reference:
            # Resolve session reference
            active = self.session_manager.get_active_session()
            match = self.session_manager.resolve_session_reference(
                session_reference,
                active.id if active else None
            )
            
            if match.match_type == MatchType.AMBIGUOUS:
                await self._show_ambiguous_candidates(event.chat_id, session_reference, match.candidates)
                return
            elif match.match_type == MatchType.NOT_FOUND:
                await self.bot.send_message(
                    event.chat_id,
                    f"❌ No session matching '{session_reference}' found.\n\n"
                    "💡 Use /list to see available sessions.",
                )
                return
            
            target_session = self.session_manager.storage.load(match.session_id)
        else:
            # No reference - use active session context
            target_session = self.session_manager.get_active_session()

        if target_session:
            name_display = f"📌 *{escape_markdown(target_session.intelligible_name)}*\n" if target_session.intelligible_name else ""
            is_active = target_session.state == SessionState.COLLECTING
            
            await self.bot.send_message(
                event.chat_id,
                f"📊 *{'Active ' if is_active else ''}Session*\n\n"
                f"{name_display}"
                f"🆔 Session: `{target_session.id}`\n"
                f"📁 Status: {target_session.state.value}\n"
                f"🎙️ Audio files: {target_session.audio_count}\n"
                f"📅 Created: {target_session.created_at.strftime('%Y-%m-%d %H:%M:%S')} UTC\n\n"
                f"*Available actions:*\n"
                + ("• Send voice messages to add audio\n• /done to finalize and transcribe" 
                   if is_active else "• /transcripts to view transcriptions\n• /list to see files"),
                parse_mode="Markdown",
            )
        else:
            # No active session - provide helpful clarification (US4)
            sessions = self.session_manager.list_sessions(limit=5)

            if sessions:
                session_lines = []
                for s in sessions:
                    status_emoji = {
                        SessionState.COLLECTING: "🟢",
                        SessionState.TRANSCRIBING: "🟡",
                        SessionState.TRANSCRIBED: "🔵",
                        SessionState.PROCESSING: "🟣",
                        SessionState.PROCESSED: "✅",
                        SessionState.ERROR: "❌",
                    }.get(s.state, "⚪")
                    name = escape_markdown(s.intelligible_name) if s.intelligible_name else s.id
                    session_lines.append(
                        f"{status_emoji} *{name}*\n   `{s.id}` ({s.audio_count} audio)"
                    )

                await self.bot.send_message(
                    event.chat_id,
                    f"📊 *No Active Session*\n\n"
                    f"*Recent sessions:*\n" + "\n".join(session_lines) + "\n\n"
                    f"💡 Send a voice message to start a new session,\n"
                    f"or use /session <name> to select an existing one.",
                    parse_mode="Markdown",
                )
            else:
                await self.bot.send_message(
                    event.chat_id,
                    "📊 *No Active Session*\n\n"
                    "No sessions found.\n\n"
                    "💡 Send a voice message to start your first session!",
                    parse_mode="Markdown",
                )

    async def _cmd_transcripts(self, event: TelegramEvent) -> None:
        """Handle /transcripts [session_ref] command - retrieve transcriptions.
        
        If no session reference provided, uses active session context.
        """
        # Check if a specific session reference was provided
        session_reference = event.command_args.strip() if event.command_args else ""

        target_session = None

        if session_reference:
            # Try to resolve session reference using natural language matching
            active = self.session_manager.get_active_session()
            match = self.session_manager.resolve_session_reference(
                session_reference,
                active.id if active else None
            )

            if match.match_type == MatchType.AMBIGUOUS:
                await self._show_ambiguous_candidates(event.chat_id, session_reference, match.candidates)
                return
            elif match.match_type == MatchType.NOT_FOUND:
                await self.bot.send_message(
                    event.chat_id,
                    f"❌ No session matching '{session_reference}' found.\n\n"
                    "💡 Use /list to see available sessions.",
                )
                return
            
            target_session = self.session_manager.storage.load(match.session_id)
        else:
            # No reference provided - use active session context (US4)
            target_session = self.session_manager.get_active_session()
            
            if not target_session:
                # Fall back to most recent transcribed session
                sessions = self.session_manager.list_sessions(limit=10)
                for s in sessions:
                    if s.state in (
                        SessionState.TRANSCRIBED,
                        SessionState.PROCESSING,
                        SessionState.PROCESSED,
                    ):
                        target_session = s
                        break

        if not target_session:
            await self.bot.send_message(
                event.chat_id,
                "❌ No active session found.\n\n"
                "💡 Send a voice message to start, or use /session <name> to select one.",
            )
            return

        # Read all transcript files
        transcripts_dir = target_session.transcripts_path(self.session_manager.sessions_dir)
        transcripts = []

        for audio_entry in target_session.audio_entries:
            if audio_entry.transcript_filename:
                transcript_path = transcripts_dir / audio_entry.transcript_filename
                if transcript_path.exists():
                    text = transcript_path.read_text(encoding="utf-8").strip()
                    transcripts.append(f"--- Audio #{audio_entry.sequence} ---\n{text}")

        if not transcripts:
            await self.bot.send_message(
                event.chat_id,
                f"⚠️ No transcripts found for session `{target_session.id}`",
                parse_mode="Markdown",
            )
            return

        full_text = "\n\n".join(transcripts)

        # Telegram message limit is 4096 characters
        if len(full_text) <= 4000:
            await self.bot.send_message(
                event.chat_id,
                f"📝 *Transcripts for session `{target_session.id}`*\n\n{escape_markdown(full_text)}",
                parse_mode="Markdown",
            )
        else:
            # Split into chunks or send as file
            # First, try to send as file
            consolidated_path = transcripts_dir / "consolidated.txt"
            consolidated_path.write_text(full_text, encoding="utf-8")

            await self.bot.send_file(
                event.chat_id,
                consolidated_path,
                caption=f"📝 Transcripts for session {target_session.id}",
            )

        logger.info(f"Sent transcripts for session {target_session.id}")

    async def _cmd_process(self, event: TelegramEvent) -> None:
        """Handle /process command - trigger downstream processing."""
        if not self.downstream_processor:
            await self.bot.send_message(
                event.chat_id,
                "❌ Downstream processor not available.",
            )
            return

        # Check if a specific session ID was provided
        specified_session_id = event.payload.get("args")

        target_session = None

        if specified_session_id:
            # Try to get the specific session
            target_session = self.session_manager.get_session(specified_session_id)
            if not target_session:
                await self.bot.send_message(
                    event.chat_id,
                    f"❌ Session `{specified_session_id}` not found.",
                    parse_mode="Markdown",
                )
                return
            if target_session.state != SessionState.TRANSCRIBED:
                await self.bot.send_message(
                    event.chat_id,
                    f"❌ Session `{specified_session_id}` is in state `{target_session.state.value}`.\n\n"
                    f"Only TRANSCRIBED sessions can be processed.",
                    parse_mode="Markdown",
                )
                return
        else:
            # Find most recent TRANSCRIBED session
            sessions = self.session_manager.list_sessions(limit=10)

            for s in sessions:
                if s.state == SessionState.TRANSCRIBED:
                    target_session = s
                    break

        if not target_session:
            await self.bot.send_message(
                event.chat_id,
                "❌ No transcribed session ready for processing.\n\n"
                "Complete transcription with /done first.",
            )
            return

        await self.bot.send_message(
            event.chat_id,
            f"⚙️ *Starting Downstream Processing*\n\n"
            f"🆔 Session: `{target_session.id}`\n"
            f"📁 Status: PROCESSING\n\n"
            f"⏳ This may take a few minutes...",
            parse_mode="Markdown",
        )

        try:
            # Transition to PROCESSING state
            self.session_manager.transition_state(target_session.id, SessionState.PROCESSING)

            # Run the downstream processor
            output_dir = self.downstream_processor.process(target_session)

            # List outputs
            outputs = self.downstream_processor.list_outputs(target_session)
            output_names = [p.name.replace("_", "\\_") for p in outputs[:10]]  # Escape underscores

            # Transition to PROCESSED state
            self.session_manager.transition_state(target_session.id, SessionState.PROCESSED)

            await self.bot.send_message(
                event.chat_id,
                f"✅ *Processing Complete*\n\n"
                f"🆔 Session: `{target_session.id}`\n"
                f"📁 Status: PROCESSED\n"
                f"📄 Outputs: {len(outputs)} files\n\n"
                f"*Generated files:*\n" + "\n".join(f"• `{name}`" for name in output_names) + "\n\n"
                f"Use /list to see all files, /get <file> to download.",
                parse_mode="Markdown",
            )

            logger.info(f"Session {target_session.id} processed successfully")

        except ProcessingError as e:
            logger.exception(f"Processing failed for session {target_session.id}: {e}")

            # Add error to session but don't change state (stays TRANSCRIBED)
            self.session_manager.add_error(
                target_session.id,
                ErrorEntry(
                    timestamp=generate_timestamp(),
                    operation="process",
                    message=str(e),
                    recoverable=True,
                ),
            )

            # Revert to TRANSCRIBED state if we transitioned
            try:
                current = self.session_manager.get_session(target_session.id)
                if current and current.state == SessionState.PROCESSING:
                    # Can't revert, so mark as ERROR
                    self.session_manager.transition_state(target_session.id, SessionState.ERROR)
            except Exception:
                pass

            # Escape error message for Markdown
            error_msg = str(e).replace("_", "\\_").replace("*", "\\*").replace("`", "\\`")
            await self.bot.send_message(
                event.chat_id,
                f"❌ *Processing Failed*\n\n"
                f"🆔 Session: `{target_session.id}`\n"
                f"⚠️ Error: {error_msg}\n\n"
                f"Check logs for details.",
                parse_mode="Markdown",
            )

        except Exception as e:
            logger.exception(f"Unexpected error processing session {target_session.id}: {e}")
            await self.bot.send_message(
                event.chat_id,
                f"❌ Processing failed: {e}",
            )

    async def _cmd_list(self, event: TelegramEvent) -> None:
        """Handle /list command - list session files."""
        # Find most recent session with files
        sessions = self.session_manager.list_sessions(limit=10)

        if not sessions:
            await self.bot.send_message(
                event.chat_id,
                "❌ No sessions found.",
            )
            return

        target_session = sessions[0]  # Most recent
        sessions_dir = self.session_manager.sessions_dir
        session_path = target_session.folder_path(sessions_dir)

        # Collect all files
        files = []

        # Audio files
        audio_dir = target_session.audio_path(sessions_dir)
        if audio_dir.exists():
            for f in audio_dir.iterdir():
                if f.is_file():
                    files.append(("🎙️", f"audio/{f.name}", f.stat().st_size))

        # Transcript files
        transcripts_dir = target_session.transcripts_path(sessions_dir)
        if transcripts_dir.exists():
            for f in transcripts_dir.iterdir():
                if f.is_file():
                    files.append(("📝", f"transcripts/{f.name}", f.stat().st_size))

        # Process output files
        process_dir = target_session.process_path(sessions_dir)
        if process_dir.exists():
            for f in process_dir.rglob("*"):
                if f.is_file():
                    rel_path = f.relative_to(session_path)
                    files.append(("📄", str(rel_path), f.stat().st_size))

        # Metadata
        metadata_path = target_session.metadata_path(sessions_dir)
        if metadata_path.exists():
            files.append(("⚙️", "metadata.json", metadata_path.stat().st_size))

        if not files:
            await self.bot.send_message(
                event.chat_id,
                f"📂 Session `{target_session.id}` has no files.",
                parse_mode="Markdown",
            )
            return

        # Format file list
        file_lines = []
        for emoji, name, size in files:
            size_str = self._format_size(size)
            file_lines.append(f"{emoji} `{escape_markdown(name)}` ({size_str})")

        session_name = escape_markdown(target_session.intelligible_name) if target_session.intelligible_name else target_session.id
        await self.bot.send_message(
            event.chat_id,
            f"📂 *{session_name}*\n"
            f"🆔 Session: `{target_session.id}`\n"
            f"Status: {target_session.state.value}\n\n" +
            "\n".join(file_lines) +
            "\n\n💡 Use /get <path> to download a file.",
            parse_mode="Markdown",
        )

    def _format_size(self, size_bytes: int) -> str:
        """Format file size for display."""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        else:
            return f"{size_bytes / (1024 * 1024):.1f} MB"

    async def _cmd_get(self, event: TelegramEvent) -> None:
        """Handle /get <filename> command - retrieve specific file."""
        if not event.command_args:
            await self.bot.send_message(
                event.chat_id,
                "❓ Usage: /get <filepath>\n\n"
                "Example: /get transcripts/001_audio.txt\n\n"
                "Use /list to see available files.",
            )
            return

        filename = event.command_args.strip()

        # Find most recent session
        sessions = self.session_manager.list_sessions(limit=10)
        if not sessions:
            await self.bot.send_message(
                event.chat_id,
                "❌ No sessions found.",
            )
            return

        target_session = sessions[0]
        sessions_dir = self.session_manager.sessions_dir
        session_path = target_session.folder_path(sessions_dir)

        # Resolve the file path (prevent path traversal)
        try:
            file_path = (session_path / filename).resolve()
            if not str(file_path).startswith(str(session_path.resolve())):
                raise ValueError("Invalid path")
        except Exception:
            await self.bot.send_message(
                event.chat_id,
                "❌ Invalid file path.",
            )
            return

        if not file_path.exists() or not file_path.is_file():
            await self.bot.send_message(
                event.chat_id,
                f"❌ File not found: `{escape_markdown(filename)}`\n\nUse /list to see available files.",
                parse_mode="Markdown",
            )
            return

        try:
            await self.bot.send_file(
                event.chat_id,
                file_path,
                caption=f"📁 {filename}",
            )
            logger.info(f"Sent file {filename} from session {target_session.id}")
        except Exception as e:
            logger.exception(f"Failed to send file {filename}: {e}")
            await self.bot.send_message(
                event.chat_id,
                f"❌ Failed to send file: {e}",
            )

    async def _cmd_session(self, event: TelegramEvent) -> None:
        """Handle /session [reference] - find and activate session by natural language reference."""
        reference = event.command_args.strip() if event.command_args else ""

        # Get active session ID for context
        active = self.session_manager.get_active_session()
        active_session_id = active.id if active else None

        # Resolve the reference using SessionMatcher
        match = self.session_manager.resolve_session_reference(reference, active_session_id)

        if match.match_type == MatchType.NOT_FOUND:
            # No match found
            await self.bot.send_message(
                event.chat_id,
                "❌ No matching session found.\n\n"
                "💡 Try using /list to see available sessions, "
                "or use a different search term.",
            )
            return

        if match.match_type == MatchType.AMBIGUOUS:
            # Multiple matches - present candidates
            await self._show_ambiguous_candidates(event.chat_id, reference, match.candidates)
            return

        # Single match found - show session details
        session = self.session_manager.storage.load(match.session_id)
        if not session:
            await self.bot.send_message(
                event.chat_id,
                "❌ Session not found (may have been deleted).",
            )
            return

        # Format match type for display
        match_type_labels = {
            MatchType.EXACT_SUBSTRING: "exact match",
            MatchType.FUZZY_SUBSTRING: "fuzzy match",
            MatchType.SEMANTIC_SIMILARITY: "semantic match",
            MatchType.ACTIVE_CONTEXT: "active session",
        }
        match_label = match_type_labels.get(match.match_type, str(match.match_type.value))

        session_name = escape_markdown(session.intelligible_name) if session.intelligible_name else session.id
        await self.bot.send_message(
            event.chat_id,
            f"✅ Found session ({match_label})\n\n"
            f"📛 *{session_name}*\n"
            f"🆔 ID: `{session.id}`\n"
            f"📅 Created: {session.created_at}\n"
            f"📊 Status: {session.state.value}\n"
            f"🎙️ Audios: {session.audio_count}\n\n"
            f"💡 Use /list to see files, /transcripts to view transcripts.",
            parse_mode="Markdown",
        )

        logger.info(f"Resolved '{reference}' to session {session.id} via {match.match_type.value}")

    async def _cmd_preferences(self, event: TelegramEvent) -> None:
        """Handle /preferences [simplified] - toggle UI preferences.
        
        T079: Add simplified_ui preference toggle.
        
        Usage:
            /preferences          - Show current preferences
            /preferences simple   - Enable simplified UI (no emojis)
            /preferences normal   - Disable simplified UI (with emojis)
            /preferences toggle   - Toggle simplified UI
        """
        args = (event.command_args or "").strip().lower()
        
        if args in ("simple", "simplified"):
            self._simplified_ui = True
            if self.ui_service:
                self.ui_service.simplified = True
            await self.bot.send_message(
                event.chat_id,
                "✓ Interface simplificada ativada.\n"
                "Emojis removidos, texto mais claro.",
            )
        elif args in ("normal", "default"):
            self._simplified_ui = False
            if self.ui_service:
                self.ui_service.simplified = False
            await self.bot.send_message(
                event.chat_id,
                "✅ Interface normal ativada.\n"
                "Emojis e formatação completa.",
            )
        elif args in ("toggle", "t"):
            self._simplified_ui = not self._simplified_ui
            if self.ui_service:
                self.ui_service.simplified = self._simplified_ui
            mode = "simplificada" if self._simplified_ui else "normal"
            await self.bot.send_message(
                event.chat_id,
                f"🔄 Interface alterada para: {mode}",
            )
        else:
            # Show current preferences
            mode = "simplificada" if self._simplified_ui else "normal"
            await self.bot.send_message(
                event.chat_id,
                f"⚙️ **Preferências Atuais**\n\n"
                f"Interface: {mode}\n\n"
                f"**Comandos:**\n"
                f"`/preferences simple` - Ativar modo simplificado\n"
                f"`/preferences normal` - Ativar modo normal\n"
                f"`/preferences toggle` - Alternar modo",
                parse_mode="Markdown",
            )
        
        logger.debug(f"Preferences updated: simplified_ui={self._simplified_ui}")

    async def _show_ambiguous_candidates(
        self,
        chat_id: int,
        reference: str,
        candidates: list[str]
    ) -> None:
        """Show list of candidate sessions when match is ambiguous."""
        lines = [f"⚠️ Multiple sessions match '{escape_markdown(reference)}':\n"]

        for i, session_id in enumerate(candidates[:5], 1):  # Limit to 5
            session = self.session_manager.storage.load(session_id)
            if session:
                name = escape_markdown(session.intelligible_name) if session.intelligible_name else session.id
                lines.append(f"{i}. 📂 *{name}*")
                lines.append(f"   `{session.id}`\n")

        lines.append("\n💡 Be more specific or use the session ID directly.")

        await self.bot.send_message(
            chat_id,
            "\n".join(lines),
            parse_mode="Markdown",
        )

    async def _handle_voice(self, event: TelegramEvent) -> None:
        """Handle voice message - download and add to session (with auto-creation)."""
        from src.lib.exceptions import AudioPersistenceError
        from src.lib.audio_validation import validate_audio

        # First, download the audio from Telegram
        try:
            # Create temp directory for download
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp_file:
                tmp_path = Path(tmp_file.name)

            # Download voice file to temp location
            file_size = await self.bot.download_voice(event.file_id, tmp_path)
            audio_data = tmp_path.read_bytes()
            tmp_path.unlink()  # Clean up temp file

        except Exception as e:
            logger.error(f"Failed to download voice from Telegram: {e}")
            await self.bot.send_message(
                event.chat_id,
                f"❌ Failed to download audio: {e}\n\nPlease try again.",
            )
            return

        # T031e: Validate audio for empty/silent content
        validation_result = validate_audio(
            audio_data=audio_data,
            duration_seconds=float(event.duration) if event.duration else None,
        )
        
        if not validation_result.is_valid:
            logger.warning(f"Audio validation failed: {validation_result.message}")
            
            # Send warning but allow user to continue
            warning_message = (
                f"⚠️ {validation_result.message}\n\n"
                "The audio was still saved, but transcription may fail.\n"
                "Send another voice message or use /done to finalize."
            )
            await self.bot.send_message(
                event.chat_id,
                warning_message,
            )
            # Don't return - continue to save the audio anyway
            # User can decide whether to keep it

        # Use handle_audio_receipt which handles auto-session creation
        try:
            session, audio_entry = self.session_manager.handle_audio_receipt(
                chat_id=event.chat_id,
                audio_data=audio_data,
                telegram_file_id=event.file_id,
                duration_seconds=float(event.duration) if event.duration else None,
            )

            # Build response message
            duration_str = f"{event.duration}s" if event.duration else "unknown"
            escaped_filename = escape_markdown(audio_entry.local_filename)
            
            # Check if this was a new session (first audio entry)
            if len(session.audio_entries) == 1:
                # New session was auto-created
                if self.ui_service:
                    # Use UIService with inline keyboard (005-telegram-ux-overhaul)
                    await self.ui_service.send_session_created(
                        chat_id=event.chat_id,
                        session=session,
                        audio_count=1,
                    )
                else:
                    # Fallback to plain text message
                    session_name = escape_markdown(session.intelligible_name) if session.intelligible_name else session.id
                    await self.bot.send_message(
                        event.chat_id,
                        f"✅ Session created: *{session_name}*\n\n"
                        f"Audio #{audio_entry.sequence} received\n"
                        f"   📁 {escaped_filename}\n"
                        f"   ⏱️ Duration: {duration_str}\n"
                        f"   💾 Size: {audio_entry.file_size_bytes:,} bytes\n\n"
                        f"Send more audio or /done when finished.",
                        parse_mode="Markdown",
                    )
            else:
                # Added to existing session
                if self.ui_service:
                    # Use UIService with inline keyboard
                    session_name = session.intelligible_name if session.intelligible_name else session.id
                    await self.ui_service.send_audio_received(
                        chat_id=event.chat_id,
                        audio_number=audio_entry.sequence,
                        session_name=session_name,
                    )
                else:
                    # Fallback to plain text message  
                    await self.bot.send_message(
                        event.chat_id,
                        f"✅ Audio #{audio_entry.sequence} received\n"
                        f"   📁 {escaped_filename}\n"
                        f"   ⏱️ Duration: {duration_str}\n"
                        f"   💾 Size: {audio_entry.file_size_bytes:,} bytes",
                    )

            # Save checkpoint for crash recovery (T031a)
            try:
                save_checkpoint(
                    session=session,
                    sessions_root=self.session_manager.sessions_dir,
                    audio_sequence=audio_entry.sequence,
                    processing_state="COLLECTING",
                )
                logger.debug(f"Checkpoint saved after audio #{audio_entry.sequence}")
            except Exception as e:
                logger.warning(f"Failed to save checkpoint: {e}")

        except AudioPersistenceError as e:
            logger.error(f"Critical: Failed to persist audio: {e}")
            await self.bot.send_message(
                event.chat_id,
                f"❌ Critical error: Could not save audio.\n"
                f"Please try again or check disk space.\n\n"
                f"Error: {e}",
            )

        except Exception as e:
            logger.exception(f"Error handling voice message: {e}")
            await self.bot.send_message(
                event.chat_id,
                f"❌ Failed to process audio: {e}",
            )


def setup_logging(verbose: bool = False) -> None:
    """Configure logging for the daemon."""
    level = logging.DEBUG if verbose else logging.INFO
    format_str = "[%(asctime)s] %(levelname)s: %(message)s"
    logging.basicConfig(
        level=level,
        format=format_str,
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def validate_configuration() -> bool:
    """Validate all required configuration is present."""
    telegram_config = get_telegram_config()
    whisper_config = get_whisper_config()
    session_config = get_session_config()

    errors = []

    if not telegram_config.is_configured():
        errors.append(
            "Telegram not configured. Set TELEGRAM_BOT_TOKEN and "
            "TELEGRAM_ALLOWED_CHAT_ID in .env file."
        )

    if not session_config.sessions_path.exists():
        logger.info(f"Creating sessions directory: {session_config.sessions_path}")
        session_config.sessions_path.mkdir(parents=True, exist_ok=True)

    if errors:
        for error in errors:
            logger.error(error)
        return False

    logger.info(f"Telegram: Authorized chat ID {telegram_config.allowed_chat_id}")
    logger.info(f"Whisper: Model {whisper_config.model_name} on {whisper_config.device}")
    logger.info(f"Sessions: {session_config.sessions_path.absolute()}")

    return True


async def _check_orphaned_sessions(
    session_manager: SessionManager,
    ui_service: Optional[UIService],
    chat_id: int,
) -> None:
    """
    Check for orphaned sessions on startup and send recovery prompts.
    
    An orphaned session is one that:
    - Is in COLLECTING or TRANSCRIBING state
    - Has checkpoint data with age > 1 hour (configurable)
    
    Per T031b from 005-telegram-ux-overhaul.
    
    Args:
        session_manager: Session manager to query sessions
        ui_service: UIService for sending recovery prompts
        chat_id: Chat ID to send recovery prompt to
    """
    from datetime import timedelta
    from src.services.session.checkpoint import has_checkpoint
    
    orphan_threshold = timedelta(hours=1)
    
    # Find potentially orphaned sessions
    sessions = session_manager.list_sessions()
    orphaned = []
    
    for session in sessions:
        # Check if session is in a recovery-eligible state
        if session.state in (SessionState.COLLECTING, SessionState.TRANSCRIBING):
            # Check if it has checkpoint data and is old
            if has_checkpoint(session):
                checkpoint = session.checkpoint_data
                if checkpoint and checkpoint.last_checkpoint_at:
                    age = datetime.now() - checkpoint.last_checkpoint_at
                    if age > orphan_threshold:
                        orphaned.append(session)
                        logger.info(f"Found orphaned session: {session.id} (age: {age})")
            elif session.updated_at:
                # No checkpoint but has updated_at
                age = datetime.now() - session.updated_at
                if age > orphan_threshold:
                    orphaned.append(session)
                    logger.info(f"Found orphaned session: {session.id} (no checkpoint, age: {age})")
    
    if not orphaned:
        logger.info("No orphaned sessions found")
        return
    
    # For each orphaned session, transition to INTERRUPTED and send recovery prompt
    for session in orphaned:
        try:
            # Transition to INTERRUPTED state
            session_manager.transition_state(session.id, SessionState.INTERRUPTED)
            logger.info(f"Marked session {session.id} as INTERRUPTED")
            
            # Reload session after state change
            updated_session = session_manager.storage.load(session.id)
            
            # Send recovery prompt
            if ui_service and updated_session:
                await ui_service.send_recovery_prompt(
                    chat_id=chat_id,
                    session=updated_session,
                )
                logger.info(f"Sent recovery prompt for session {session.id}")
            else:
                logger.warning(f"Could not send recovery prompt for {session.id} - UIService unavailable")
        except Exception as e:
            logger.error(f"Failed to handle orphaned session {session.id}: {e}")


async def run_daemon() -> NoReturn:
    """Main daemon loop."""
    logger.info("Starting Telegram Voice Orchestrator daemon...")

    # Get configuration
    telegram_config = get_telegram_config()
    session_config = get_session_config()
    whisper_config = get_whisper_config()

    # Initialize components
    storage = SessionStorage(session_config.sessions_path)
    session_manager = SessionManager(storage)
    bot = TelegramBotAdapter(telegram_config)

    # Initialize transcription service
    transcription_service: TranscriptionService | None = None
    try:
        logger.info("Initializing Whisper transcription service...")
        transcription_service = WhisperTranscriptionService(whisper_config)
        transcription_service.load_model()
        logger.info("Whisper model loaded and ready")
    except Exception as e:
        logger.warning(f"Failed to load Whisper model: {e}")
        logger.warning("Transcription will be unavailable")
        transcription_service = None

    # Initialize downstream processor
    downstream_processor = DownstreamProcessor(session_manager)

    # Initialize SearchService for semantic session search (006-semantic-session-search)
    search_service: SearchService | None = None
    try:
        logger.info("Initializing SearchService...")
        search_service = DefaultSearchService(storage=storage, embedding_service=None)
        logger.info("SearchService initialized")
    except Exception as e:
        logger.warning(f"Failed to initialize SearchService: {e}")
        logger.warning("Semantic search will be unavailable")
        search_service = None

    # Initialize UIService for inline keyboard support (005-telegram-ux-overhaul)
    # UIService requires access to bot._app.bot after bot.start()
    # So we initialize it as None and set it after bot starts
    ui_service: Optional[UIService] = None

    # Create orchestrator and register event handler
    orchestrator = VoiceOrchestrator(
        bot, session_manager, transcription_service, downstream_processor, ui_service,
        search_service=search_service,
    )
    orchestrator.set_chat_id(telegram_config.allowed_chat_id)
    bot.on_event(orchestrator.handle_event)

    # Start the bot
    await bot.start()

    # Now that bot is started, initialize UIService with the telegram Bot instance
    # This provides inline keyboard support per 005-telegram-ux-overhaul
    if bot._app and bot._app.bot:
        ui_service = UIService(bot=bot._app.bot)
        orchestrator.ui_service = ui_service
        logger.info("UIService initialized with inline keyboard support")
    else:
        logger.warning("Could not initialize UIService - inline keyboards unavailable")

    # Check for orphaned sessions on startup (T031b)
    # Orphaned sessions are in COLLECTING state but haven't been updated recently
    await _check_orphaned_sessions(
        session_manager=session_manager,
        ui_service=ui_service,
        chat_id=telegram_config.allowed_chat_id,
    )

    logger.info("Daemon running. Press Ctrl+C to stop.")

    try:
        # Keep running until cancelled
        while True:
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        pass
    finally:
        # Unload Whisper model
        if transcription_service:
            transcription_service.unload_model()

        await bot.stop()
        logger.info("Daemon stopped.")


def signal_handler(signum: int, frame) -> None:
    """Handle shutdown signals gracefully."""
    logger.info(f"Received signal {signum}, initiating shutdown...")
    sys.exit(0)


def main() -> int:
    """Entry point for the daemon."""
    parser = argparse.ArgumentParser(
        description="Telegram Voice Orchestrator Daemon",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    setup_logging(verbose=args.verbose)

    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    logger.info("=" * 60)
    logger.info("Telegram Voice Orchestrator (OATL)")
    logger.info("All processing is local - Telegram is channel only")
    logger.info("=" * 60)

    if not validate_configuration():
        logger.error("Configuration validation failed. Exiting.")
        return 1

    try:
        asyncio.run(run_daemon())
    except KeyboardInterrupt:
        logger.info("Daemon stopped by user.")
    except Exception as e:
        logger.exception(f"Daemon failed with error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
