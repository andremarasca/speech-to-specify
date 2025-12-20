"""Telegram bot adapter using python-telegram-bot.

This module implements the TelegramBotAdapter interface from
contracts/telegram-bot.md using the python-telegram-bot library.

The bot handles:
- Commands: /start, /done, /finish, /status, /transcripts, /process, /list, /get
- Voice messages: Download and forward to session manager
- Callback queries: Inline keyboard button presses for UI interactions
"""

import logging
from pathlib import Path
from typing import Callable, Awaitable, Optional

from telegram import Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

from src.lib.config import TelegramConfig
from src.services.telegram.adapter import TelegramEvent

logger = logging.getLogger(__name__)


class TelegramBotAdapter:
    """
    Telegram bot adapter using python-telegram-bot library.

    Implements the adapter pattern to isolate Telegram protocol details.
    All Telegram events are normalized to TelegramEvent objects.
    """

    def __init__(self, config: TelegramConfig):
        """
        Initialize the Telegram bot adapter.

        Args:
            config: Telegram configuration with bot token and allowed chat ID
        """
        self.config = config
        self._app: Optional[Application] = None
        self._event_handler: Optional[Callable[[TelegramEvent], Awaitable[None]]] = None
        self._running = False

    def on_event(self, handler: Callable[[TelegramEvent], Awaitable[None]]) -> None:
        """
        Register event handler callback.

        The handler will be called for all normalized events.

        Args:
            handler: Async function that processes TelegramEvent
        """
        self._event_handler = handler

    async def start(self) -> None:
        """Start listening for Telegram updates."""
        if self._running:
            logger.warning("Bot already running")
            return

        logger.info("Initializing Telegram bot...")

        # Build the application
        self._app = (
            ApplicationBuilder()
            .token(self.config.bot_token)
            .build()
        )

        # Register command handlers
        self._app.add_handler(CommandHandler("start", self._handle_start))
        self._app.add_handler(CommandHandler("done", self._handle_finish))
        self._app.add_handler(CommandHandler("finish", self._handle_finish))
        self._app.add_handler(CommandHandler("status", self._handle_status))
        self._app.add_handler(CommandHandler("transcripts", self._handle_transcripts))
        self._app.add_handler(CommandHandler("process", self._handle_process))
        self._app.add_handler(CommandHandler("list", self._handle_list))
        self._app.add_handler(CommandHandler("sessions", self._handle_sessions))
        self._app.add_handler(CommandHandler("get", self._handle_get))
        self._app.add_handler(CommandHandler("help", self._handle_help))
        self._app.add_handler(CommandHandler("preferences", self._handle_preferences))
        self._app.add_handler(CommandHandler("search", self._handle_search))
        self._app.add_handler(CommandHandler("searchid", self._handle_searchid))
        self._app.add_handler(CommandHandler("searchtxt", self._handle_searchtxt))
        self._app.add_handler(CommandHandler("session", self._handle_session))
        self._app.add_handler(CommandHandler("reopen", self._handle_reopen))

        # Fallback handlers for unregistered commands (when Telegram doesn't send BOT_COMMAND entity)
        # These catch text messages starting with /command pattern
        self._app.add_handler(MessageHandler(
            filters.TEXT & filters.Regex(r"^/searchid(\s|$)"),
            self._handle_searchid_text
        ))
        self._app.add_handler(MessageHandler(
            filters.TEXT & filters.Regex(r"^/reopen(\s|$)"),
            self._handle_reopen_text
        ))
        self._app.add_handler(MessageHandler(
            filters.TEXT & filters.Regex(r"^/searchtxt(\s|$)"),
            self._handle_searchtxt_text
        ))

        # Register voice message handler
        self._app.add_handler(MessageHandler(filters.VOICE, self._handle_voice))

        # Register callback query handler for inline keyboard buttons
        self._app.add_handler(CallbackQueryHandler(self._handle_callback))

        # Register unknown command handler
        self._app.add_handler(MessageHandler(filters.COMMAND, self._handle_unknown))

        # Initialize and start polling
        await self._app.initialize()
        await self._app.start()
        await self._app.updater.start_polling(drop_pending_updates=True)

        self._running = True
        logger.info("Telegram bot started and listening for messages")

    async def stop(self) -> None:
        """Stop the bot gracefully."""
        if not self._running or not self._app:
            return

        logger.info("Stopping Telegram bot...")

        await self._app.updater.stop()
        await self._app.stop()
        await self._app.shutdown()

        self._running = False
        logger.info("Telegram bot stopped")

    def _is_authorized(self, chat_id: int) -> bool:
        """Check if chat_id is authorized."""
        return chat_id == self.config.allowed_chat_id

    async def _check_auth(self, update: Update) -> bool:
        """Check authorization and respond if unauthorized."""
        chat_id = update.effective_chat.id

        if not self._is_authorized(chat_id):
            logger.warning(f"Unauthorized access attempt from chat_id: {chat_id}")
            await update.message.reply_text("⛔ Unauthorized access")
            return False

        return True

    async def _dispatch_event(self, event: TelegramEvent) -> None:
        """Dispatch event to registered handler."""
        if self._event_handler:
            try:
                await self._event_handler(event)
            except Exception as e:
                logger.exception(f"Error handling event: {e}")

    # Command handlers

    async def _handle_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command."""
        if not await self._check_auth(update):
            return

        event = TelegramEvent.command(
            chat_id=update.effective_chat.id,
            command="start",
        )
        await self._dispatch_event(event)

    async def _handle_finish(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /done or /finish command.
        
        Preserve the actual command name so orchestrator routing can
        distinguish aliases for contract coverage.
        """
        if not await self._check_auth(update):
            return

        raw_command = (update.effective_message.text or "").strip()
        # extract command without leading slash and args
        command_name = raw_command.split()[0].lstrip("/").lower() if raw_command else "finish"

        event = TelegramEvent.command(
            chat_id=update.effective_chat.id,
            command=command_name,
        )
        await self._dispatch_event(event)

    async def _handle_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /status command."""
        if not await self._check_auth(update):
            return

        event = TelegramEvent.command(
            chat_id=update.effective_chat.id,
            command="status",
        )
        await self._dispatch_event(event)

    async def _handle_transcripts(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /transcripts command."""
        if not await self._check_auth(update):
            return

        event = TelegramEvent.command(
            chat_id=update.effective_chat.id,
            command="transcripts",
        )
        await self._dispatch_event(event)

    async def _handle_process(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /process command."""
        if not await self._check_auth(update):
            return

        event = TelegramEvent.command(
            chat_id=update.effective_chat.id,
            command="process",
        )
        await self._dispatch_event(event)

    async def _handle_list(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /list command."""
        if not await self._check_auth(update):
            return

        event = TelegramEvent.command(
            chat_id=update.effective_chat.id,
            command="list",
        )
        await self._dispatch_event(event)

    async def _handle_sessions(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /sessions command - list all sessions."""
        if not await self._check_auth(update):
            return

        event = TelegramEvent.command(
            chat_id=update.effective_chat.id,
            command="sessions",
        )
        await self._dispatch_event(event)

    async def _handle_get(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /get <filename> command."""
        if not await self._check_auth(update):
            return

        # Extract filename from command args
        args = " ".join(context.args) if context.args else None

        if not args:
            await update.message.reply_text("❓ Usage: /get <filename>")
            return

        event = TelegramEvent.command(
            chat_id=update.effective_chat.id,
            command="get",
            args=args,
        )
        await self._dispatch_event(event)

    async def _handle_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /help command - delegate to event handler for contextual help."""
        if not await self._check_auth(update):
            return

        # Dispatch to event handler for contextual help with inline keyboard
        event = TelegramEvent.command(
            chat_id=update.effective_chat.id,
            command="help",
        )
        await self._dispatch_event(event)

    async def _handle_preferences(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /preferences command - delegate to event handler."""
        if not await self._check_auth(update):
            return

        args = " ".join(context.args) if context.args else None
        event = TelegramEvent.command(
            chat_id=update.effective_chat.id,
            command="preferences",
            args=args,
        )
        await self._dispatch_event(event)

    async def _handle_search(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /search command - delegate to event handler."""
        if not await self._check_auth(update):
            return

        args = " ".join(context.args) if context.args else None
        event = TelegramEvent.command(
            chat_id=update.effective_chat.id,
            command="search",
            args=args,
        )
        await self._dispatch_event(event)

    async def _handle_searchid(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /searchid command - search by session ID."""
        if not await self._check_auth(update):
            return

        args = " ".join(context.args) if context.args else None
        event = TelegramEvent.command(
            chat_id=update.effective_chat.id,
            command="searchid",
            args=args,
        )
        await self._dispatch_event(event)

    async def _handle_searchtxt(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /searchtxt command - search in transcripts."""
        if not await self._check_auth(update):
            return

        args = " ".join(context.args) if context.args else None
        event = TelegramEvent.command(
            chat_id=update.effective_chat.id,
            command="searchtxt",
            args=args,
        )
        await self._dispatch_event(event)

    async def _handle_searchid_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /searchid as text message (fallback when not registered with BotFather)."""
        if not await self._check_auth(update):
            return

        # Parse args from text: "/searchid arg1 arg2" -> "arg1 arg2"
        text = update.message.text or ""
        parts = text.split(maxsplit=1)
        args = parts[1] if len(parts) > 1 else None
        
        event = TelegramEvent.command(
            chat_id=update.effective_chat.id,
            command="searchid",
            args=args,
        )
        await self._dispatch_event(event)

    async def _handle_searchtxt_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /searchtxt as text message (fallback when not registered with BotFather)."""
        if not await self._check_auth(update):
            return

        # Parse args from text: "/searchtxt arg1 arg2" -> "arg1 arg2"
        text = update.message.text or ""
        parts = text.split(maxsplit=1)
        args = parts[1] if len(parts) > 1 else None
        
        event = TelegramEvent.command(
            chat_id=update.effective_chat.id,
            command="searchtxt",
            args=args,
        )
        await self._dispatch_event(event)

    async def _handle_session(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /session command - delegate to event handler."""
        if not await self._check_auth(update):
            return

        args = " ".join(context.args) if context.args else None
        event = TelegramEvent.command(
            chat_id=update.effective_chat.id,
            command="session",
            args=args,
        )
        await self._dispatch_event(event)

    async def _handle_reopen(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /reopen command - reopen finalized session."""
        if not await self._check_auth(update):
            return

        args = " ".join(context.args) if context.args else None
        event = TelegramEvent.command(
            chat_id=update.effective_chat.id,
            command="reopen",
            args=args,
        )
        await self._dispatch_event(event)

    async def _handle_reopen_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /reopen as text message (fallback when not registered with BotFather)."""
        if not await self._check_auth(update):
            return

        # Parse args from text: "/reopen arg1 arg2" -> "arg1 arg2"
        text = update.message.text or ""
        parts = text.split(maxsplit=1)
        args = parts[1] if len(parts) > 1 else None
        
        event = TelegramEvent.command(
            chat_id=update.effective_chat.id,
            command="reopen",
            args=args,
        )
        await self._dispatch_event(event)

    async def _handle_unknown(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle unknown commands with contract wording."""
        if not await self._check_auth(update):
            return

        await update.message.reply_text("❓ Comando desconhecido. Use /help para ver opções.")

    async def _handle_voice(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle voice message."""
        if not await self._check_auth(update):
            return

        voice = update.message.voice

        event = TelegramEvent.voice(
            chat_id=update.effective_chat.id,
            file_id=voice.file_id,
            duration=voice.duration,
            file_size=voice.file_size,
        )
        await self._dispatch_event(event)

    async def _handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Handle callback query from inline keyboard button press.
        
        Routes callbacks based on their prefix:
        - action:<name> - Direct actions (finalize, cancel, etc.)
        - nav:<direction>:<context> - Navigation (pagination)
        - help:<topic> - Contextual help
        - confirm:<type>:<response> - Confirmation dialog responses
        - recover:<action> - Crash recovery actions
        
        The event is dispatched to the event handler which routes to
        appropriate domain handlers.
        """
        query = update.callback_query
        
        if not query:
            return
            
        # Get chat_id from the callback query message
        chat_id = query.message.chat_id if query.message else update.effective_chat.id
        
        if not self._is_authorized(chat_id):
            logger.warning(f"Unauthorized callback from chat_id: {chat_id}")
            await query.answer("⛔ Unauthorized", show_alert=True)
            return
        
        # Always acknowledge the callback to remove loading state
        await query.answer()
        
        # Create normalized callback event
        event = TelegramEvent.callback(
            chat_id=chat_id,
            callback_data=query.data,
            message_id=query.message.message_id if query.message else None,
            user_id=query.from_user.id if query.from_user else None,
        )
        
        logger.debug(f"Callback received: {query.data}")
        await self._dispatch_event(event)

    # Message sending methods

    async def send_message(self, chat_id: int, text: str, parse_mode: str = None, reply_markup=None) -> None:
        """
        Send text message to user.

        Args:
            chat_id: Target chat ID
            text: Message text
            parse_mode: Optional parse mode (Markdown, HTML)
            reply_markup: Optional inline keyboard markup
        """
        if not self._app:
            raise RuntimeError("Bot not started")

        await self._app.bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
        )

    async def delete_message(self, chat_id: int, message_id: int) -> bool:
        """
        Delete a message.

        Args:
            chat_id: Chat ID where message is
            message_id: ID of message to delete

        Returns:
            True if deleted successfully
        """
        if not self._app:
            raise RuntimeError("Bot not started")

        try:
            await self._app.bot.delete_message(chat_id=chat_id, message_id=message_id)
            return True
        except Exception as e:
            logger.warning(f"Failed to delete message {message_id}: {e}")
            return False

    async def send_file(self, chat_id: int, file_path: Path, caption: str = None) -> None:
        """
        Send file to user.

        Args:
            chat_id: Target chat ID
            file_path: Path to file to send
            caption: Optional caption
        """
        if not self._app:
            raise RuntimeError("Bot not started")

        with open(file_path, "rb") as f:
            await self._app.bot.send_document(
                chat_id=chat_id,
                document=f,
                caption=caption,
            )

    async def download_voice(self, file_id: str, destination: Path) -> int:
        """
        Download voice message to local path.

        Args:
            file_id: Telegram file ID
            destination: Local path to save file

        Returns:
            File size in bytes
        """
        if not self._app:
            raise RuntimeError("Bot not started")

        file = await self._app.bot.get_file(file_id)
        await file.download_to_drive(destination)

        return destination.stat().st_size
