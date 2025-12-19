"""Command handlers for CLI and Telegram interactions.

This module provides command handlers that can be used by both CLI and Telegram
interfaces. Each handler returns a structured result that can be formatted
for the target interface.

Implements handlers for 004-resilient-voice-capture user stories:
- /start: Start new recording session
- /close: Finalize session and queue for transcription
- /status: Show current session status
- /reopen: Reopen finalized session
- /sessions: Search/list sessions
- /help: Show available commands
- /recover: Recover interrupted sessions
- /retry: Retry failed operations
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional, Protocol

from src.models.session import ProcessingStatus, Session, SessionState

logger = logging.getLogger(__name__)


class CommandStatus(Enum):
    """Status of command execution."""
    SUCCESS = "success"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class StatusIndicator:
    """Status indicator for visual feedback.
    
    Attributes:
        emoji: Emoji to display (e.g., "✅", "❌", "⏳")
        label: Short status label (e.g., "Recording", "Processing")
        color: Optional color hint for rich displays
    """
    emoji: str
    label: str
    color: Optional[str] = None


@dataclass
class CommandResult:
    """Result of a command execution.
    
    Attributes:
        status: Overall command status
        message: Human-readable message
        data: Optional structured data for programmatic use
        indicator: Visual status indicator
        suggestions: Optional list of follow-up commands
    """
    status: CommandStatus
    message: str
    data: Optional[dict] = None
    indicator: Optional[StatusIndicator] = None
    suggestions: list[str] = field(default_factory=list)


# Session state to status indicator mapping
SESSION_STATE_INDICATORS: dict[SessionState, StatusIndicator] = {
    SessionState.COLLECTING: StatusIndicator("🎙️", "Recording", "green"),
    SessionState.TRANSCRIBING: StatusIndicator("⏳", "Transcribing", "yellow"),
    SessionState.TRANSCRIBED: StatusIndicator("📝", "Transcribed", "blue"),
    SessionState.PROCESSING: StatusIndicator("⚙️", "Processing", "yellow"),
    SessionState.PROCESSED: StatusIndicator("✅", "Processed", "green"),
    SessionState.READY: StatusIndicator("✓", "Ready", "green"),
    SessionState.EMBEDDING: StatusIndicator("🔍", "Indexing", "purple"),
    SessionState.INTERRUPTED: StatusIndicator("⚠️", "Interrupted", "orange"),
    SessionState.ERROR: StatusIndicator("❌", "Error", "red"),
}


def get_status_indicator(state: SessionState) -> StatusIndicator:
    """Get status indicator for a session state.
    
    Args:
        state: Session state to get indicator for
        
    Returns:
        StatusIndicator for visual feedback
    """
    return SESSION_STATE_INDICATORS.get(
        state, 
        StatusIndicator("❓", "Unknown", "gray")
    )


class CommandHandler(Protocol):
    """Protocol for command handlers."""
    
    async def execute(self, *args: Any, **kwargs: Any) -> CommandResult:
        """Execute the command and return result."""
        ...


@dataclass
class StartResult:
    """Result of /start command.
    
    Attributes:
        session_id: ID of the created session
        was_auto_finalized: Whether a previous session was auto-finalized
        previous_session_id: ID of auto-finalized session (if any)
        indicator: Status indicator for the new session
    """
    session_id: str
    was_auto_finalized: bool = False
    previous_session_id: Optional[str] = None
    indicator: StatusIndicator = field(
        default_factory=lambda: StatusIndicator("🎙️", "Recording", "green")
    )


class StartCommandHandler:
    """Handler for /start command - create new recording session.
    
    Creates a new session in COLLECTING state. If an active session exists,
    it will be auto-finalized first per spec FR-004.
    """
    
    def __init__(self, session_manager):
        """Initialize handler with dependencies.
        
        Args:
            session_manager: SessionManager for session operations
        """
        self.session_manager = session_manager
    
    async def execute(self, chat_id: int) -> CommandResult:
        """Execute /start command.
        
        Args:
            chat_id: Chat ID for the new session
            
        Returns:
            CommandResult with session info
        """
        logger.info(f"/start command invoked for chat_id={chat_id}")
        try:
            # Check for existing active session
            active = self.session_manager.get_active_session()
            was_auto_finalized = False
            previous_id = None
            
            if active:
                was_auto_finalized = True
                previous_id = active.id
                logger.info(f"Auto-finalizing existing session {previous_id}")
            
            # Create new session (auto-finalizes active if exists)
            session = self.session_manager.create_session(chat_id=chat_id)
            logger.info(f"Created new session {session.id}")
            
            result = StartResult(
                session_id=session.id,
                was_auto_finalized=was_auto_finalized,
                previous_session_id=previous_id,
                indicator=get_status_indicator(session.state),
            )
            
            # Build message
            if was_auto_finalized:
                message = (
                    f"Session Started (previous auto-finalized)\n\n"
                    f"🆔 New Session: {session.id}\n"
                    f"📁 Previous: {previous_id}\n"
                    f"📊 Status: {result.indicator.label}\n\n"
                    f"Send voice messages to record audio."
                )
            else:
                message = (
                    f"Session Started\n\n"
                    f"🆔 Session: {session.id}\n"
                    f"📊 Status: {result.indicator.label}\n\n"
                    f"Send voice messages to record audio."
                )
            
            return CommandResult(
                status=CommandStatus.SUCCESS,
                message=message,
                data={
                    "session_id": session.id,
                    "was_auto_finalized": was_auto_finalized,
                    "previous_session_id": previous_id,
                    "state": session.state.value,
                    "reopen_count": session.reopen_count,
                },
                indicator=result.indicator,
                suggestions=["/close", "/status"],
            )
            
        except Exception as e:
            return CommandResult(
                status=CommandStatus.ERROR,
                message=f"Failed to start session: {str(e)}",
                indicator=StatusIndicator("❌", "Error", "red"),
            )


@dataclass 
class StatusResult:
    """Result of /status command.
    
    Attributes:
        session: Current session info (if any)
        has_active_session: Whether an active session exists
        indicator: Status indicator
    """
    session: Optional[Session]
    has_active_session: bool
    indicator: StatusIndicator


class StatusCommandHandler:
    """Handler for /status command - show current session status."""
    
    def __init__(self, session_manager):
        """Initialize handler with dependencies."""
        self.session_manager = session_manager
    
    async def execute(self) -> CommandResult:
        """Execute /status command.
        
        Returns:
            CommandResult with current session status
        """
        try:
            active = self.session_manager.get_active_session()
            
            if not active:
                return CommandResult(
                    status=CommandStatus.INFO,
                    message="No active session.\n\nUse /start to begin recording.",
                    indicator=StatusIndicator("ℹ️", "No Session", "gray"),
                    suggestions=["/start", "/sessions"],
                )
            
            indicator = get_status_indicator(active.state)
            
            # Calculate totals
            total_duration = sum(
                e.duration_seconds or 0.0 
                for e in active.audio_entries
            )
            
            message = (
                f"Current Session Status\n\n"
                f"🆔 Session: {active.id}\n"
                f"{indicator.emoji} Status: {indicator.label}\n"
                f"🎙️ Audio files: {active.audio_count}\n"
                f"⏱️ Total duration: {total_duration:.1f}s\n"
                f"🔄 Reopen count: {active.reopen_count}\n"
            )
            
            return CommandResult(
                status=CommandStatus.SUCCESS,
                message=message,
                data={
                    "session_id": active.id,
                    "state": active.state.value,
                    "audio_count": active.audio_count,
                    "total_duration": total_duration,
                    "reopen_count": active.reopen_count,
                },
                indicator=indicator,
                suggestions=["/close", "/start"],
            )
            
        except Exception as e:
            return CommandResult(
                status=CommandStatus.ERROR,
                message=f"Failed to get status: {str(e)}",
                indicator=StatusIndicator("❌", "Error", "red"),
            )


def format_session_status_message(session: Session) -> str:
    """Format a session status message with indicator.
    
    Args:
        session: Session to format
        
    Returns:
        Formatted status message string
    """
    indicator = get_status_indicator(session.state)
    
    duration = sum(
        e.duration_seconds or 0.0 
        for e in session.audio_entries
    )
    
    return (
        f"🆔 Session: {session.id}\n"
        f"{indicator.emoji} Status: {indicator.label}\n"
        f"🎙️ Audio: {session.audio_count} files ({duration:.1f}s)\n"
        f"🔄 Reopened: {session.reopen_count} times"
    )


@dataclass
class FinalizeResult:
    """Result of session finalization.
    
    Attributes:
        session_id: ID of finalized session
        audio_count: Number of audio files in session
        total_duration: Total duration in seconds
        queued_count: Number of segments queued for transcription
        indicator: Status indicator for the finalized session
    """
    session_id: str
    audio_count: int
    total_duration: float
    queued_count: int
    indicator: StatusIndicator = field(
        default_factory=lambda: StatusIndicator("⏳", "Transcribing", "yellow")
    )


class CloseCommandHandler:
    """Handler for /close command - finalize session and queue for transcription.
    
    Finalizes the active session (COLLECTING → TRANSCRIBING) and queues
    all audio segments for background transcription.
    """
    
    def __init__(self, session_manager, queue_service=None):
        """Initialize handler with dependencies.
        
        Args:
            session_manager: SessionManager for session operations
            queue_service: Optional TranscriptionQueueService for queuing
        """
        self.session_manager = session_manager
        self.queue_service = queue_service
    
    async def execute(self) -> CommandResult:
        """Execute /close command.
        
        Returns:
            CommandResult with finalization info
        """
        try:
            # Get active session
            active = self.session_manager.get_active_session()
            
            if not active:
                return CommandResult(
                    status=CommandStatus.ERROR,
                    message="No active session to close.\n\nUse /start to begin recording.",
                    indicator=StatusIndicator("❌", "No Session", "gray"),
                    suggestions=["/start"],
                )
            
            # Check for audio
            if active.audio_count == 0:
                return CommandResult(
                    status=CommandStatus.ERROR,
                    message=(
                        "Cannot close session with no audio.\n\n"
                        "Send voice messages first, or use /start to start over."
                    ),
                    indicator=StatusIndicator("⚠️", "No Audio", "orange"),
                    suggestions=["/start"],
                )
            
            # Finalize session
            finalized = self.session_manager.finalize_session(active.id)
            
            # Calculate totals
            total_duration = sum(
                e.duration_seconds or 0.0 
                for e in finalized.audio_entries
            )
            
            # Queue for transcription if service available
            queued_count = 0
            if self.queue_service:
                result = self.queue_service.queue_session(finalized.id)
                queued_count = result.queued_count
            
            indicator = get_status_indicator(finalized.state)
            
            result = FinalizeResult(
                session_id=finalized.id,
                audio_count=finalized.audio_count,
                total_duration=total_duration,
                queued_count=queued_count,
                indicator=indicator,
            )
            
            message = (
                f"Session Finalized\n\n"
                f"🆔 Session: {finalized.id}\n"
                f"{indicator.emoji} Status: {indicator.label}\n"
                f"🎙️ Audio files: {finalized.audio_count}\n"
                f"⏱️ Total duration: {total_duration:.1f}s\n"
            )
            
            if queued_count > 0:
                message += f"\n⏳ Queued {queued_count} segment(s) for transcription"
            
            return CommandResult(
                status=CommandStatus.SUCCESS,
                message=message,
                data={
                    "session_id": finalized.id,
                    "state": finalized.state.value,
                    "audio_count": finalized.audio_count,
                    "total_duration": total_duration,
                    "queued_count": queued_count,
                },
                indicator=indicator,
                suggestions=["/status", "/sessions"],
            )
            
        except Exception as e:
            return CommandResult(
                status=CommandStatus.ERROR,
                message=f"Failed to close session: {str(e)}",
                indicator=StatusIndicator("❌", "Error", "red"),
            )


@dataclass
class QueueStatusResult:
    """Result of queue status query.
    
    Attributes:
        pending_count: Items waiting to be processed
        processing_count: Items currently being processed
        completed_today: Items completed today
        failed_count: Items that failed
        current_session_progress: Progress for current session (if any)
    """
    pending_count: int
    processing_count: int
    completed_today: int
    failed_count: int
    current_session_progress: Optional[dict] = None


class QueueStatusCommandHandler:
    """Handler for /qstatus command - show transcription queue status."""
    
    def __init__(self, queue_service):
        """Initialize handler with dependencies."""
        self.queue_service = queue_service
    
    async def execute(self, session_id: Optional[str] = None) -> CommandResult:
        """Execute /qstatus command.
        
        Args:
            session_id: Optional session to show specific progress
            
        Returns:
            CommandResult with queue status
        """
        try:
            status = self.queue_service.get_queue_status()
            
            message = (
                f"Transcription Queue Status\n\n"
                f"⏳ Pending: {status.pending_count}\n"
                f"⚙️ Processing: {status.processing_count}\n"
                f"✅ Completed today: {status.completed_today}\n"
                f"❌ Failed: {status.failed_count}\n"
                f"🔄 Worker: {'Running' if status.worker_running else 'Stopped'}\n"
            )
            
            if status.current_item:
                message += (
                    f"\nCurrently processing:\n"
                    f"  Session: {status.current_item.session_id}\n"
                    f"  Segment: #{status.current_item.sequence}\n"
                )
            
            data = {
                "pending_count": status.pending_count,
                "processing_count": status.processing_count,
                "completed_today": status.completed_today,
                "failed_count": status.failed_count,
                "worker_running": status.worker_running,
            }
            
            # Add session-specific progress if requested
            if session_id:
                try:
                    progress = self.queue_service.get_session_progress(session_id)
                    message += (
                        f"\nSession {session_id} Progress:\n"
                        f"  Total: {progress.total_segments}\n"
                        f"  Completed: {progress.completed}\n"
                        f"  Pending: {progress.pending}\n"
                        f"  Failed: {progress.failed}\n"
                        f"  Progress: {progress.progress_percent:.1f}%\n"
                    )
                    data["session_progress"] = progress.to_dict()
                except Exception:
                    pass  # Session not found, ignore
            
            return CommandResult(
                status=CommandStatus.SUCCESS,
                message=message,
                data=data,
                indicator=StatusIndicator(
                    "⚙️" if status.processing_count > 0 else "✓",
                    "Processing" if status.processing_count > 0 else "Idle",
                    "yellow" if status.processing_count > 0 else "green",
                ),
            )
            
        except Exception as e:
            return CommandResult(
                status=CommandStatus.ERROR,
                message=f"Failed to get queue status: {str(e)}",
                indicator=StatusIndicator("❌", "Error", "red"),
            )


@dataclass
class ReopenResult:
    """Result of session reopen operation.
    
    Attributes:
        session_id: ID of reopened session
        reopen_count: Number of times session has been reopened
        original_audio_count: Number of audio files from before reopen
        indicator: Status indicator
    """
    session_id: str
    reopen_count: int
    original_audio_count: int
    indicator: StatusIndicator = field(
        default_factory=lambda: StatusIndicator("🔄", "Reopened", "blue")
    )


class ReopenCommandHandler:
    """Handler for /reopen command - reopen session for additional audio.
    
    Reopens a READY session, allowing more audio to be added. Original
    audio entries are preserved. New audio will have a new reopen_epoch.
    """
    
    def __init__(self, session_manager):
        """Initialize handler with dependencies.
        
        Args:
            session_manager: SessionManager for session operations
        """
        self.session_manager = session_manager
    
    async def execute(self, session_ref: Optional[str] = None) -> CommandResult:
        """Execute /reopen command.
        
        Args:
            session_ref: Optional session ID or name to reopen.
                         If not provided, uses most recent READY session.
            
        Returns:
            CommandResult with reopen info
        """
        try:
            session = None
            
            if session_ref:
                # Try to find by ID first
                session = self.session_manager.get_session(session_ref)
                
                if not session:
                    # Try to find by searching recent sessions
                    sessions = self.session_manager.list_sessions(limit=20)
                    for s in sessions:
                        if (s.intelligible_name and 
                            session_ref.lower() in s.intelligible_name.lower()):
                            session = s
                            break
                        if session_ref in s.id:
                            session = s
                            break
                
                if not session:
                    return CommandResult(
                        status=CommandStatus.ERROR,
                        message=f"Session not found: {session_ref}",
                        indicator=StatusIndicator("❌", "Not Found", "red"),
                        suggestions=["/sessions"],
                    )
            else:
                # Find most recent READY session
                sessions = self.session_manager.list_sessions(limit=20)
                for s in sessions:
                    if s.state == SessionState.READY:
                        session = s
                        break
                
                if not session:
                    return CommandResult(
                        status=CommandStatus.ERROR,
                        message="No READY sessions found to reopen.",
                        indicator=StatusIndicator("ℹ️", "No Session", "gray"),
                        suggestions=["/sessions", "/start"],
                    )
            
            # Check if session can be reopened
            if not session.can_reopen:
                return CommandResult(
                    status=CommandStatus.ERROR,
                    message=(
                        f"Cannot reopen session in {session.state.value} state.\n"
                        f"Session must be in READY state to reopen."
                    ),
                    indicator=StatusIndicator("⚠️", "Cannot Reopen", "orange"),
                )
            
            # Store original audio count before reopen
            original_audio_count = session.audio_count
            
            # Reopen session
            reopened = self.session_manager.reopen_session(session.id)
            
            indicator = get_status_indicator(reopened.state)
            
            result = ReopenResult(
                session_id=reopened.id,
                reopen_count=reopened.reopen_count,
                original_audio_count=original_audio_count,
                indicator=indicator,
            )
            
            message = (
                f"Session Reopened\n\n"
                f"🆔 Session: {reopened.id}\n"
                f"{indicator.emoji} Status: {indicator.label}\n"
                f"🎙️ Original audio: {original_audio_count} files\n"
                f"🔄 Reopen count: {reopened.reopen_count}\n\n"
                f"Send voice messages to add more audio."
            )
            
            return CommandResult(
                status=CommandStatus.SUCCESS,
                message=message,
                data={
                    "session_id": reopened.id,
                    "state": reopened.state.value,
                    "reopen_count": reopened.reopen_count,
                    "original_audio_count": original_audio_count,
                },
                indicator=indicator,
                suggestions=["/close", "/status"],
            )
            
        except Exception as e:
            return CommandResult(
                status=CommandStatus.ERROR,
                message=f"Failed to reopen session: {str(e)}",
                indicator=StatusIndicator("❌", "Error", "red"),
            )


@dataclass
class SessionsResult:
    """Result of /sessions command.
    
    Attributes:
        sessions: List of sessions found
        total_found: Total sessions matching query
        search_method: How search was performed
        query: Search query (if any)
    """
    sessions: list
    total_found: int
    search_method: str
    query: Optional[str] = None


class SessionsCommandHandler:
    """Handler for /sessions command - search and list sessions.
    
    Provides two modes:
    1. With query: Semantic/text search
    2. Without query: Chronological listing
    """
    
    def __init__(self, search_service, session_manager=None):
        """Initialize handler with dependencies.
        
        Args:
            search_service: SearchService for searching sessions
            session_manager: Optional SessionManager for fallback listing
        """
        self.search_service = search_service
        self.session_manager = session_manager
    
    async def execute(
        self, 
        query: Optional[str] = None,
        limit: int = 10,
        offset: int = 0,
        chat_id: Optional[int] = None
    ) -> CommandResult:
        """Execute /sessions command.
        
        Args:
            query: Optional search query
            limit: Max results to return
            offset: Pagination offset
            chat_id: Filter by chat/user ID
            
        Returns:
            CommandResult with session list
        """
        try:
            if query:
                # Search mode
                response = self.search_service.search(
                    query=query,
                    chat_id=chat_id,
                    limit=limit,
                )
            else:
                # List mode
                response = self.search_service.list_chronological(
                    chat_id=chat_id,
                    limit=limit,
                    offset=offset,
                )
            
            if not response.results:
                if query:
                    # No search results
                    message = (
                        f"No sessions found for: {query}\n\n"
                        "Try:\n"
                        "• Different keywords\n"
                        "• /sessions (list all)\n"
                        "• /start (new session)"
                    )
                    if response.suggestions:
                        message += "\n\n💡 Suggestions:\n"
                        message += "\n".join(f"  • {s}" for s in response.suggestions)
                else:
                    message = "No sessions found.\n\nUse /start to create a new session."
                
                return CommandResult(
                    status=CommandStatus.INFO,
                    message=message,
                    data={
                        "query": query,
                        "total_found": 0,
                        "sessions": [],
                        "search_method": response.search_method.value,
                    },
                    indicator=StatusIndicator("ℹ️", "No Results", "gray"),
                    suggestions=["/start"] + response.suggestions,
                )
            
            # Format session list
            if query:
                header = f"🔍 Sessions matching: {query}\n"
            else:
                header = "📋 Recent Sessions\n"
            
            lines = [header, ""]
            
            for i, result in enumerate(response.results, 1):
                # Format each result
                score_bar = self._format_score(result.relevance_score)
                duration = self._format_duration(result.total_audio_duration)
                
                lines.append(
                    f"{i}. {result.session_name}\n"
                    f"   🆔 {result.session_id[:12]}...\n"
                    f"   🎙️ {result.audio_count} files ({duration})\n"
                )
                if query and result.relevance_score < 1.0:
                    lines.append(f"   📊 Match: {score_bar}\n")
            
            if response.total_found > limit:
                lines.append(f"\n... and {response.total_found - limit} more")
            
            message = "".join(lines)
            
            # Build data
            data = {
                "query": query,
                "total_found": response.total_found,
                "search_method": response.search_method.value,
                "duration_ms": response.duration_ms,
                "sessions": [
                    {
                        "session_id": r.session_id,
                        "session_name": r.session_name,
                        "relevance_score": r.relevance_score,
                        "audio_count": r.audio_count,
                        "total_duration": r.total_audio_duration,
                    }
                    for r in response.results
                ],
            }
            
            if response.fallback_used:
                data["fallback_used"] = True
                data["fallback_reason"] = response.fallback_reason
            
            return CommandResult(
                status=CommandStatus.SUCCESS,
                message=message,
                data=data,
                indicator=StatusIndicator(
                    "🔍" if query else "📋",
                    f"{response.total_found} found",
                    "blue",
                ),
                suggestions=["/reopen <session>", "/start"],
            )
            
        except Exception as e:
            return CommandResult(
                status=CommandStatus.ERROR,
                message=f"Failed to search sessions: {str(e)}",
                indicator=StatusIndicator("❌", "Error", "red"),
            )
    
    def _format_score(self, score: float) -> str:
        """Format relevance score as visual bar."""
        filled = int(score * 5)
        return "█" * filled + "░" * (5 - filled)
    
    def _format_duration(self, seconds: float) -> str:
        """Format duration in human-readable format."""
        if seconds < 60:
            return f"{seconds:.0f}s"
        elif seconds < 3600:
            minutes = seconds / 60
            return f"{minutes:.1f}m"
        else:
            hours = seconds / 3600
            return f"{hours:.1f}h"


@dataclass
class HelpResult:
    """Result of /help command.
    
    Attributes:
        command: Specific command requested (if any)
        commands: List of available commands
        categories: Available categories
    """
    command: Optional[str] = None
    commands: list = field(default_factory=list)
    categories: list[str] = field(default_factory=list)


class HelpCommandHandler:
    """Handler for /help command - show available commands.
    
    Provides exhaustive documentation for all registered commands.
    Per contracts/help-system.md for Constitution Pillar II compliance.
    """
    
    def __init__(self, help_system):
        """Initialize handler with dependencies.
        
        Args:
            help_system: HelpSystem for command documentation
        """
        self.help_system = help_system
    
    async def execute(self, command: Optional[str] = None) -> CommandResult:
        """Execute /help command.
        
        Args:
            command: Optional specific command to get help for
            
        Returns:
            CommandResult with help documentation
        """
        try:
            response = self.help_system.get_help(command)
            
            if command and not response.found:
                # Command not found
                return CommandResult(
                    status=CommandStatus.ERROR,
                    message=response.text,
                    data={"command": command, "found": False},
                    indicator=StatusIndicator("❌", "Not Found", "red"),
                    suggestions=["/help"],
                )
            
            # Build data
            data = {
                "command": command,
                "found": response.found,
                "commands": [c.to_dict() for c in response.commands],
                "categories": response.categories,
            }
            
            return CommandResult(
                status=CommandStatus.SUCCESS,
                message=response.text,
                data=data,
                indicator=StatusIndicator("📖", "Help", "blue"),
            )
            
        except Exception as e:
            return CommandResult(
                status=CommandStatus.ERROR,
                message=f"Failed to get help: {str(e)}",
                indicator=StatusIndicator("❌", "Error", "red"),
            )


@dataclass
class RecoverResult:
    """Result of /recover command.
    
    Attributes:
        interrupted_sessions: List of interrupted sessions found
        recovered_session: Session that was recovered (if action taken)
        action_taken: Recovery action performed (if any)
    """
    interrupted_sessions: list
    recovered_session: Optional[str] = None
    action_taken: Optional[str] = None


class RecoverCommandHandler:
    """Handler for /recover command - show and recover interrupted sessions.
    
    Lists sessions that were interrupted (e.g., by crash) and provides
    options to resume, finalize, or discard them.
    """
    
    def __init__(self, session_manager):
        """Initialize handler with dependencies.
        
        Args:
            session_manager: SessionManager for session operations
        """
        self.session_manager = session_manager
    
    async def execute(
        self,
        session_id: Optional[str] = None,
        action: Optional[str] = None
    ) -> CommandResult:
        """Execute /recover command.
        
        Args:
            session_id: Optional specific session to recover
            action: Optional action to take (RESUME, FINALIZE, DISCARD)
            
        Returns:
            CommandResult with recovery info
        """
        from src.services.session.manager import RecoveryAction
        
        try:
            if session_id and action:
                # Perform recovery action
                try:
                    recovery_action = RecoveryAction(action.upper())
                except ValueError:
                    return CommandResult(
                        status=CommandStatus.ERROR,
                        message=f"Invalid action: {action}. Use RESUME, FINALIZE, or DISCARD.",
                        indicator=StatusIndicator("❌", "Invalid Action", "red"),
                    )
                
                result = self.session_manager.recover_session(session_id, recovery_action)
                
                return CommandResult(
                    status=CommandStatus.SUCCESS,
                    message=result.message,
                    data={
                        "session_id": result.session_id,
                        "action_taken": result.action_taken.value,
                        "new_state": result.new_state.value,
                    },
                    indicator=StatusIndicator("✅", "Recovered", "green"),
                    suggestions=["/status", "/start"],
                )
            
            # List interrupted sessions
            interrupted = self.session_manager.detect_interrupted_sessions()
            
            if not interrupted:
                return CommandResult(
                    status=CommandStatus.INFO,
                    message="No interrupted sessions found.\n\nAll sessions are in normal state.",
                    indicator=StatusIndicator("✓", "No Issues", "green"),
                    suggestions=["/start", "/sessions"],
                )
            
            # Format list
            lines = [
                "⚠️ Interrupted Sessions\n",
                "The following sessions may need recovery:\n",
            ]
            
            for i, sess in enumerate(interrupted, 1):
                lines.append(f"{i}. Session: {sess.session_id}")
                lines.append(f"   🎙️ Audio files: {sess.audio_count}")
                if sess.last_audio_at:
                    lines.append(f"   ⏱️ Last audio: {sess.last_audio_at.strftime('%Y-%m-%d %H:%M')}")
                actions = ", ".join(a.value for a in sess.recovery_options)
                lines.append(f"   📋 Actions: {actions}")
                lines.append("")
            
            lines.append("To recover, use: /recover <session_id> <action>")
            lines.append("Actions: RESUME, FINALIZE, DISCARD")
            
            return CommandResult(
                status=CommandStatus.WARNING,
                message="\n".join(lines),
                data={
                    "interrupted_count": len(interrupted),
                    "sessions": [
                        {
                            "session_id": s.session_id,
                            "audio_count": s.audio_count,
                            "last_audio_at": s.last_audio_at.isoformat() if s.last_audio_at else None,
                            "recovery_options": [a.value for a in s.recovery_options],
                        }
                        for s in interrupted
                    ],
                },
                indicator=StatusIndicator("⚠️", f"{len(interrupted)} interrupted", "orange"),
            )
            
        except Exception as e:
            return CommandResult(
                status=CommandStatus.ERROR,
                message=f"Failed to recover: {str(e)}",
                indicator=StatusIndicator("❌", "Error", "red"),
            )


@dataclass
class RetryResult:
    """Result of /retry command.
    
    Attributes:
        session_id: Session that was retried
        retried_count: Number of segments retried
        failed_segments: Segments that couldn't be retried
    """
    session_id: str
    retried_count: int
    failed_segments: list[str] = None


class RetryCommandHandler:
    """Handler for /retry command - retry failed transcriptions.
    
    Retries transcription for segments that failed during processing.
    """
    
    def __init__(self, session_manager, queue_service=None):
        """Initialize handler with dependencies.
        
        Args:
            session_manager: SessionManager for session operations
            queue_service: Optional TranscriptionQueueService for retry
        """
        self.session_manager = session_manager
        self.queue_service = queue_service
    
    async def execute(self, session_id: str) -> CommandResult:
        """Execute /retry command.
        
        Args:
            session_id: Session to retry failed transcriptions for
            
        Returns:
            CommandResult with retry info
        """
        try:
            # Get session
            session = self.session_manager.get_session(session_id)
            
            if not session:
                return CommandResult(
                    status=CommandStatus.ERROR,
                    message=f"Session not found: {session_id}",
                    indicator=StatusIndicator("❌", "Not Found", "red"),
                    suggestions=["/sessions"],
                )
            
            # Find failed segments
            from src.models.session import TranscriptionStatus
            failed_segments = [
                e for e in session.audio_entries
                if e.transcription_status == TranscriptionStatus.FAILED
            ]
            
            if not failed_segments:
                return CommandResult(
                    status=CommandStatus.INFO,
                    message=f"No failed transcriptions in session {session_id}.",
                    data={"session_id": session_id, "retried_count": 0},
                    indicator=StatusIndicator("✓", "No Failures", "green"),
                )
            
            # Retry if queue service available
            retried_count = 0
            if self.queue_service:
                result = self.queue_service.retry_failed(session_id)
                retried_count = result.retried_count if hasattr(result, 'retried_count') else len(failed_segments)
            else:
                # Mark segments for retry by resetting status
                for segment in failed_segments:
                    segment.transcription_status = TranscriptionStatus.PENDING
                self.session_manager.storage.save(session)
                retried_count = len(failed_segments)
            
            return CommandResult(
                status=CommandStatus.SUCCESS,
                message=(
                    f"Retrying {retried_count} failed transcription(s) for session {session_id}.\n\n"
                    f"Use /status to monitor progress."
                ),
                data={
                    "session_id": session_id,
                    "retried_count": retried_count,
                },
                indicator=StatusIndicator("🔄", "Retrying", "yellow"),
                suggestions=["/status"],
            )
            
        except Exception as e:
            return CommandResult(
                status=CommandStatus.ERROR,
                message=f"Failed to retry: {str(e)}",
                indicator=StatusIndicator("❌", "Error", "red"),
            )


def register_all_commands(help_system):
    """Register all standard commands with the help system.
    
    This function must be called during application initialization
    to ensure all commands are documented.
    
    Args:
        help_system: HelpSystem to register commands with
        
    Returns:
        dict: Mapping of command names to handlers (for wiring)
    """
    from src.services.help.registry import DefaultHelpSystem
    
    # Define command documentation
    commands = [
        {
            "name": "/help",
            "description": "Show all available commands or help for a specific command",
            "params": {"command": "Optional command name to get detailed help"},
            "examples": ["/help", "/help close", "/help sessions"],
            "category": "system",
        },
        {
            "name": "/start",
            "description": "Start a new recording session",
            "params": {},
            "examples": ["/start"],
            "category": "session",
        },
        {
            "name": "/close",
            "description": "Finalize the current session and queue for transcription",
            "params": {"--force": "Skip confirmation (not yet implemented)"},
            "examples": ["/close"],
            "category": "session",
        },
        {
            "name": "/status",
            "description": "Show current session status",
            "params": {},
            "examples": ["/status"],
            "category": "session",
        },
        {
            "name": "/reopen",
            "description": "Reopen a finalized session to add more audio",
            "params": {"session": "Session ID or name to reopen (optional)"},
            "examples": ["/reopen", "/reopen 2024-01-15_14-30-00", "/reopen meeting"],
            "category": "session",
        },
        {
            "name": "/sessions",
            "description": "List recent sessions or search by keyword",
            "params": {"query": "Optional search query"},
            "examples": ["/sessions", "/sessions python", "/sessions meeting notes"],
            "category": "search",
        },
        {
            "name": "/recover",
            "description": "Show and recover interrupted sessions",
            "params": {},
            "examples": ["/recover"],
            "category": "recovery",
        },
        {
            "name": "/retry",
            "description": "Retry failed transcriptions for a session",
            "params": {"session": "Session ID to retry"},
            "examples": ["/retry 2024-01-15_14-30-00"],
            "category": "recovery",
        },
    ]
    
    # Placeholder handler for registration
    async def placeholder_handler(*args, **kwargs):
        pass
    
    for cmd in commands:
        help_system.register(
            name=cmd["name"],
            description=cmd["description"],
            handler=placeholder_handler,
            params=cmd.get("params"),
            examples=cmd.get("examples"),
            category=cmd.get("category", "general"),
        )
