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
import signal
import sys
from datetime import datetime
from pathlib import Path
from typing import NoReturn

from src.lib.config import (
    get_telegram_config,
    get_whisper_config,
    get_session_config,
)
from src.lib.timestamps import generate_timestamp
from src.models.session import AudioEntry, ErrorEntry, SessionState, TranscriptionStatus
from src.services.session.storage import SessionStorage
from src.services.session.manager import SessionManager, InvalidStateError
from src.services.telegram.adapter import TelegramEvent
from src.services.telegram.bot import TelegramBotAdapter
from src.services.transcription.base import TranscriptionService
from src.services.transcription.whisper import WhisperTranscriptionService
from src.services.session.processor import DownstreamProcessor, ProcessingError

# Configure logging
logger = logging.getLogger(__name__)


class VoiceOrchestrator:
    """
    Main orchestrator coordinating Telegram bot, session manager, and transcription.

    This class handles the event loop and coordinates between:
    - TelegramBotAdapter: Receives commands and voice messages
    - SessionManager: Manages session lifecycle and persistence
    - TranscriptionService: Converts audio to text using local Whisper
    - DownstreamProcessor: Integrates with narrative pipeline
    """

    def __init__(
        self,
        bot: TelegramBotAdapter,
        session_manager: SessionManager,
        transcription_service: TranscriptionService | None = None,
        downstream_processor: DownstreamProcessor | None = None,
    ):
        self.bot = bot
        self.session_manager = session_manager
        self.transcription_service = transcription_service
        self.downstream_processor = downstream_processor
        self._chat_id: int = 0  # Will be set from config

    def set_chat_id(self, chat_id: int) -> None:
        """Set the authorized chat ID for sending messages."""
        self._chat_id = chat_id

    async def handle_event(self, event: TelegramEvent) -> None:
        """
        Handle incoming Telegram events.

        Routes events to appropriate handlers based on event type.
        """
        logger.debug(f"Handling event: {event.event_type} from {event.chat_id}")

        if event.is_command:
            await self._handle_command(event)
        elif event.is_voice:
            await self._handle_voice(event)

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
        }

        handler = handlers.get(command)
        if handler:
            await handler(event)
        else:
            logger.warning(f"Unknown command: {command}")

    async def _cmd_start(self, event: TelegramEvent) -> None:
        """Handle /start command - create new session."""
        try:
            # Check for existing active session
            active = self.session_manager.get_active_session()
            if active:
                await self.bot.send_message(
                    event.chat_id,
                    f"⚠️ Auto-finalizing previous session: `{active.id}`\n"
                    f"   ({active.audio_count} audio(s))",
                    parse_mode="Markdown",
                )

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

        for i, audio_entry in enumerate(session.audio_entries, 1):
            # Send progress notification
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
        """Handle /status command - show current session status."""
        active = self.session_manager.get_active_session()

        if active:
            await self.bot.send_message(
                event.chat_id,
                f"📊 *Active Session*\n\n"
                f"🆔 Session: `{active.id}`\n"
                f"📁 Status: {active.state.value}\n"
                f"🎙️ Audio files: {active.audio_count}\n"
                f"📅 Created: {active.created_at.strftime('%Y-%m-%d %H:%M:%S')} UTC\n\n"
                f"*Available actions:*\n"
                f"• Send voice messages to add audio\n"
                f"• /done to finalize and transcribe",
                parse_mode="Markdown",
            )
        else:
            # List recent sessions
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
                    session_lines.append(
                        f"{status_emoji} `{s.id}` - {s.state.value} ({s.audio_count} audio)"
                    )

                await self.bot.send_message(
                    event.chat_id,
                    f"📊 *No Active Session*\n\n"
                    f"*Recent sessions:*\n" + "\n".join(session_lines) + "\n\n"
                    f"Use /start to begin a new session.",
                    parse_mode="Markdown",
                )
            else:
                await self.bot.send_message(
                    event.chat_id,
                    "📊 No sessions found.\n\nUse /start to begin.",
                )

    async def _cmd_transcripts(self, event: TelegramEvent) -> None:
        """Handle /transcripts command - retrieve transcriptions."""
        # Find most recent TRANSCRIBED or later session
        sessions = self.session_manager.list_sessions(limit=10)
        target_session = None

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
                "❌ No transcribed session found.\n\n"
                "Complete a session with /done first.",
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
                f"📝 *Transcripts for session `{target_session.id}`*\n\n{full_text}",
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

        # Find most recent TRANSCRIBED session
        sessions = self.session_manager.list_sessions(limit=10)
        target_session = None

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
            output_names = [p.name for p in outputs[:10]]  # Limit to first 10

            # Transition to PROCESSED state
            self.session_manager.transition_state(target_session.id, SessionState.PROCESSED)

            await self.bot.send_message(
                event.chat_id,
                f"✅ *Processing Complete*\n\n"
                f"🆔 Session: `{target_session.id}`\n"
                f"📁 Status: PROCESSED\n"
                f"📄 Outputs: {len(outputs)} files\n\n"
                f"*Generated files:*\n" + "\n".join(f"• {name}" for name in output_names) + "\n\n"
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

            await self.bot.send_message(
                event.chat_id,
                f"❌ *Processing Failed*\n\n"
                f"🆔 Session: `{target_session.id}`\n"
                f"⚠️ Error: {e}\n\n"
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
            file_lines.append(f"{emoji} `{name}` ({size_str})")

        await self.bot.send_message(
            event.chat_id,
            f"📂 *Files in session `{target_session.id}`*\n"
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
                f"❌ File not found: `{filename}`\n\nUse /list to see available files.",
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

    async def _handle_voice(self, event: TelegramEvent) -> None:
        """Handle voice message - download and add to session."""
        active = self.session_manager.get_active_session()

        if not active:
            await self.bot.send_message(
                event.chat_id,
                "❌ No active session.\n\nUse /start to begin a session first.",
            )
            return

        if not active.can_add_audio:
            await self.bot.send_message(
                event.chat_id,
                f"❌ Session `{active.id}` is {active.state.value}.\n"
                f"Cannot add audio to finalized session.\n\n"
                f"Use /start to begin a new session.",
                parse_mode="Markdown",
            )
            return

        try:
            # Determine sequence number and filename
            sequence = active.next_sequence
            filename = f"{sequence:03d}_audio.ogg"
            audio_dir = active.audio_path(self.session_manager.sessions_dir)
            audio_dir.mkdir(exist_ok=True)
            destination = audio_dir / filename

            # Download voice file
            await self.bot.send_message(
                event.chat_id,
                f"⏳ Receiving audio #{sequence}...",
            )

            file_size = await self.bot.download_voice(event.file_id, destination)

            # Create audio entry
            audio_entry = AudioEntry(
                sequence=sequence,
                received_at=generate_timestamp(),
                telegram_file_id=event.file_id,
                local_filename=filename,
                file_size_bytes=file_size,
                duration_seconds=float(event.duration) if event.duration else None,
            )

            # Add to session
            self.session_manager.add_audio(active.id, audio_entry)

            duration_str = f"{event.duration}s" if event.duration else "unknown"
            await self.bot.send_message(
                event.chat_id,
                f"✅ Audio #{sequence} received\n"
                f"   📁 {filename}\n"
                f"   ⏱️ Duration: {duration_str}\n"
                f"   💾 Size: {file_size:,} bytes",
            )

            logger.info(f"Added audio #{sequence} to session {active.id}")

        except Exception as e:
            logger.exception(f"Error handling voice message: {e}")

            # Log error to session
            error_entry = ErrorEntry(
                timestamp=generate_timestamp(),
                operation="download",
                target=event.file_id,
                message=str(e),
                recoverable=True,
            )
            self.session_manager.add_error(active.id, error_entry)

            await self.bot.send_message(
                event.chat_id,
                f"❌ Failed to receive audio: {e}",
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

    # Create orchestrator and register event handler
    orchestrator = VoiceOrchestrator(
        bot, session_manager, transcription_service, downstream_processor
    )
    orchestrator.set_chat_id(telegram_config.allowed_chat_id)
    bot.on_event(orchestrator.handle_event)

    # Start the bot
    await bot.start()

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
