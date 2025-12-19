"""Progress reporter for real-time feedback during long operations.

Per contracts/progress-reporter.md for 005-telegram-ux-overhaul (T036-T044).

ProgressReporter tracks and reports progress of long-running operations
(transcription, embedding, pipeline processing). It manages throttling of
UI updates and timeout detection while delegating actual message rendering
to UIService.
"""

import asyncio
import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Callable, Awaitable, Optional, TYPE_CHECKING

from src.models.ui_state import (
    OperationType,
    ProgressState,
    ProgressStatus,
    UIPreferences,
)
from src.lib.config import get_ui_config

if TYPE_CHECKING:
    from telegram import Message
    from src.services.telegram.ui_service import UIServiceProtocol

logger = logging.getLogger(__name__)


# =============================================================================
# Progress Bar Formatting
# =============================================================================


def format_progress_bar(
    current: int,
    total: int,
    width: int = 10,
    simplified: bool = False,
) -> str:
    """Format visual progress bar.
    
    Args:
        current: Current step
        total: Total steps
        width: Bar width in characters
        simplified: Use text-only format
        
    Returns:
        Formatted progress string
        
    Examples:
        Standard: "▓▓▓▓▓░░░░░ 50%"
        Simplified: "Progresso: 50% (5 de 10)"
    """
    # Cap percentage at 100%
    if total <= 0:
        percentage = 0
    else:
        percentage = min(100, int((current / total) * 100))
    
    if simplified:
        return f"Progresso: {percentage}% ({current} de {total})"
    
    if total <= 0:
        filled = 0
    else:
        filled = min(width, int(width * current / total))
    
    bar = "▓" * filled + "░" * (width - filled)
    return f"{bar} {percentage}%"


def estimate_completion(
    started_at: datetime,
    current_step: int,
    total_steps: int,
    audio_minutes: Optional[float] = None,
    avg_seconds_per_minute: float = 10.0,
) -> Optional[datetime]:
    """Estimate operation completion time.
    
    For transcription: Uses audio duration heuristic
    For other operations: Uses elapsed time extrapolation
    
    Args:
        started_at: When the operation started
        current_step: Current progress step
        total_steps: Total steps in operation
        audio_minutes: Audio duration in minutes (for transcription)
        avg_seconds_per_minute: Heuristic for transcription time
        
    Returns:
        Estimated completion datetime, or None if cannot estimate
    """
    if current_step <= 0:
        return None
    
    now = datetime.now(timezone.utc)
    
    if audio_minutes is not None and audio_minutes > 0:
        # Transcription: estimate based on audio length
        remaining_fraction = 1 - (current_step / total_steps)
        remaining_minutes = audio_minutes * remaining_fraction
        remaining_seconds = remaining_minutes * avg_seconds_per_minute
    else:
        # General: extrapolate from elapsed time
        elapsed = (now - started_at).total_seconds()
        if elapsed <= 0:
            return None
        rate = elapsed / current_step
        remaining_seconds = rate * (total_steps - current_step)
    
    return now + timedelta(seconds=remaining_seconds)


# =============================================================================
# Protocol and Implementation
# =============================================================================


class ProgressReporterProtocol(ABC):
    """Protocol for progress tracking and reporting."""
    
    @abstractmethod
    async def start_operation(
        self,
        operation_type: OperationType,
        total_steps: int,
        chat_id: int,
        on_update: Optional[Callable[["ProgressState"], Awaitable[None]]] = None,
    ) -> str:
        """Initialize progress tracking for an operation."""
        ...
    
    @abstractmethod
    async def update_progress(
        self,
        operation_id: str,
        current_step: int,
        step_description: str,
    ) -> None:
        """Update progress for an operation."""
        ...
    
    @abstractmethod
    async def complete_operation(
        self,
        operation_id: str,
        success: bool = True,
    ) -> None:
        """Mark operation as complete."""
        ...
    
    @abstractmethod
    async def cancel_operation(self, operation_id: str) -> None:
        """Cancel an in-progress operation."""
        ...
    
    @abstractmethod
    def get_progress(self, operation_id: str) -> Optional[ProgressState]:
        """Get current progress state."""
        ...
    
    @abstractmethod
    def is_timed_out(self, operation_id: str) -> bool:
        """Check if operation has exceeded timeout threshold."""
        ...


@dataclass
class TrackedOperation:
    """Internal state for a tracked operation.
    
    Extends ProgressState with tracking-specific fields.
    """
    state: ProgressState
    chat_id: int
    message: Optional["Message"] = None
    on_update: Optional[Callable[[ProgressState], Awaitable[None]]] = None
    timeout_warned: bool = False
    audio_minutes: Optional[float] = None


class ProgressReporter(ProgressReporterProtocol):
    """Implementation with throttling and timeout detection.
    
    Per contracts/progress-reporter.md:
    - Tracks progress state per operation
    - Throttles UI updates to configured interval
    - Detects timeouts and triggers warnings
    - Delegates rendering to UIService
    
    Example:
        reporter = ProgressReporter(ui_service)
        
        op_id = await reporter.start_operation(
            operation_type=OperationType.TRANSCRIPTION,
            total_steps=10,
            chat_id=123,
        )
        
        for i in range(10):
            await reporter.update_progress(op_id, i + 1, f"Step {i + 1}")
            
        await reporter.complete_operation(op_id)
    """
    
    def __init__(
        self,
        ui_service: Optional["UIServiceProtocol"] = None,
        update_interval_seconds: Optional[float] = None,
        timeout_seconds: Optional[float] = None,
        avg_seconds_per_audio_minute: float = 10.0,
    ):
        """Initialize the progress reporter.
        
        Args:
            ui_service: UIService for rendering progress to Telegram
            update_interval_seconds: Minimum interval between UI updates
            timeout_seconds: Timeout threshold for operations
            avg_seconds_per_audio_minute: Heuristic for transcription ETA
        """
        self._ui_service = ui_service
        
        config = get_ui_config()
        self._update_interval = update_interval_seconds or config.progress_interval_seconds
        self._timeout_seconds = timeout_seconds or float(config.operation_timeout_seconds)
        self._avg_seconds_per_minute = avg_seconds_per_audio_minute
        
        self._operations: dict[str, TrackedOperation] = {}
        self._lock = asyncio.Lock()
        
    async def start_operation(
        self,
        operation_type: OperationType,
        total_steps: int,
        chat_id: int,
        on_update: Optional[Callable[[ProgressState], Awaitable[None]]] = None,
        audio_minutes: Optional[float] = None,
    ) -> str:
        """Initialize progress tracking for an operation.
        
        Args:
            operation_type: Type of operation (TRANSCRIPTION, etc.)
            total_steps: Total number of steps
            chat_id: Telegram chat for progress messages
            on_update: Optional callback for progress updates
            audio_minutes: Audio duration for ETA calculation
            
        Returns:
            operation_id for subsequent updates
        """
        operation_id = str(uuid.uuid4())[:8]
        now = datetime.now(timezone.utc)
        
        state = ProgressState(
            operation_id=operation_id,
            operation_type=operation_type,
            current_step=0,
            total_steps=total_steps,
            step_description="Iniciando...",
            started_at=now,
            last_update_at=now,
            status=ProgressStatus.ACTIVE,
        )
        
        tracked = TrackedOperation(
            state=state,
            chat_id=chat_id,
            on_update=on_update,
            audio_minutes=audio_minutes,
        )
        
        async with self._lock:
            self._operations[operation_id] = tracked
        
        # Send initial progress message if UI service available
        if self._ui_service:
            try:
                preferences = UIPreferences(simplified_ui=False)
                message = await self._ui_service.send_progress(
                    chat_id=chat_id,
                    progress=state,
                    preferences=preferences,
                )
                tracked.message = message
            except Exception as e:
                logger.warning(f"Failed to send initial progress: {e}")
        
        logger.debug(f"Started operation {operation_id}: {operation_type.value}")
        return operation_id
        
    async def update_progress(
        self,
        operation_id: str,
        current_step: int,
        step_description: str,
    ) -> None:
        """Update progress for an operation.
        
        Args:
            operation_id: ID from start_operation
            current_step: Current step number (1-indexed)
            step_description: Human-readable description
            
        Side Effects:
            - Updates progress message if throttle interval passed
            - Checks for timeout condition
        """
        async with self._lock:
            tracked = self._operations.get(operation_id)
            if not tracked:
                logger.warning(f"Unknown operation: {operation_id}")
                return
            
            now = datetime.now(timezone.utc)
            
            # Update state
            tracked.state = ProgressState(
                operation_id=operation_id,
                operation_type=tracked.state.operation_type,
                current_step=current_step,
                total_steps=tracked.state.total_steps,
                step_description=step_description,
                started_at=tracked.state.started_at,
                last_update_at=now,
                status=ProgressStatus.ACTIVE,
                estimated_completion=estimate_completion(
                    started_at=tracked.state.started_at,
                    current_step=current_step,
                    total_steps=tracked.state.total_steps,
                    audio_minutes=tracked.audio_minutes,
                    avg_seconds_per_minute=self._avg_seconds_per_minute,
                ),
            )
        
        # Check if should update UI (throttled)
        should_update = await self._should_update_ui(operation_id)
        
        if should_update:
            await self._update_ui(tracked)
            
        # Call custom callback if provided
        if tracked.on_update:
            try:
                await tracked.on_update(tracked.state)
            except Exception as e:
                logger.warning(f"Progress callback error: {e}")
                
        # Check for timeout
        await self._check_timeout(operation_id)
        
    async def complete_operation(
        self,
        operation_id: str,
        success: bool = True,
    ) -> None:
        """Mark operation as complete.
        
        Args:
            operation_id: ID from start_operation
            success: Whether operation completed successfully
            
        Side Effects:
            - Sends final progress update (100% or error)
            - Cleans up operation state
        """
        async with self._lock:
            tracked = self._operations.get(operation_id)
            if not tracked:
                return
            
            now = datetime.now(timezone.utc)
            
            # Set to 100% complete
            tracked.state = ProgressState(
                operation_id=operation_id,
                operation_type=tracked.state.operation_type,
                current_step=tracked.state.total_steps,
                total_steps=tracked.state.total_steps,
                step_description="Concluído!" if success else "Erro",
                started_at=tracked.state.started_at,
                last_update_at=now,
                status=ProgressStatus.COMPLETED if success else ProgressStatus.ERROR,
            )
        
        # Send final update
        await self._update_ui(tracked)
        
        # Clean up after a short delay to allow UI to update
        await asyncio.sleep(0.5)
        async with self._lock:
            self._operations.pop(operation_id, None)
            
        logger.debug(f"Completed operation {operation_id}: success={success}")
        
    async def cancel_operation(self, operation_id: str) -> None:
        """Cancel an in-progress operation.
        
        Args:
            operation_id: ID from start_operation
            
        Side Effects:
            - Sends cancellation confirmation
            - Cleans up operation state
        """
        async with self._lock:
            tracked = self._operations.pop(operation_id, None)
            
        if tracked:
            now = datetime.now(timezone.utc)
            tracked.state = ProgressState(
                operation_id=operation_id,
                operation_type=tracked.state.operation_type,
                current_step=tracked.state.current_step,
                total_steps=tracked.state.total_steps,
                step_description="Cancelado",
                started_at=tracked.state.started_at,
                last_update_at=now,
                status=ProgressStatus.CANCELLED,
            )
            
            await self._update_ui(tracked)
            logger.debug(f"Cancelled operation {operation_id}")
        
    def get_progress(self, operation_id: str) -> Optional[ProgressState]:
        """Get current progress state.
        
        Args:
            operation_id: ID from start_operation
            
        Returns:
            Current ProgressState or None if not found
        """
        tracked = self._operations.get(operation_id)
        return tracked.state if tracked else None
        
    def is_timed_out(self, operation_id: str) -> bool:
        """Check if operation has exceeded timeout threshold.
        
        Args:
            operation_id: ID from start_operation
            
        Returns:
            True if operation should trigger timeout warning
        """
        tracked = self._operations.get(operation_id)
        if not tracked:
            return False
            
        elapsed = (datetime.now(timezone.utc) - tracked.state.started_at).total_seconds()
        return elapsed > self._timeout_seconds
        
    async def _should_update_ui(self, operation_id: str) -> bool:
        """Check if enough time has passed for next UI update."""
        tracked = self._operations.get(operation_id)
        if not tracked:
            return False
            
        elapsed = (datetime.now(timezone.utc) - tracked.state.last_update_at).total_seconds()
        return elapsed >= self._update_interval
        
    async def _update_ui(self, tracked: TrackedOperation) -> None:
        """Send progress update to UI service."""
        if not self._ui_service:
            return
            
        preferences = UIPreferences(simplified_ui=False)
        
        try:
            if tracked.message:
                await self._ui_service.update_progress(
                    message=tracked.message,
                    progress=tracked.state,
                    preferences=preferences,
                )
            else:
                # No message to update - send a new one
                message = await self._ui_service.send_progress(
                    chat_id=tracked.chat_id,
                    progress=tracked.state,
                    preferences=preferences,
                )
                tracked.message = message
        except Exception as e:
            logger.warning(f"Failed to update progress UI: {e}")
            
    async def _check_timeout(self, operation_id: str) -> None:
        """Check and handle timeout condition."""
        tracked = self._operations.get(operation_id)
        if not tracked:
            return
            
        if self.is_timed_out(operation_id) and not tracked.timeout_warned:
            tracked.timeout_warned = True
            
            if self._ui_service:
                elapsed = (datetime.now(timezone.utc) - tracked.state.started_at).total_seconds()
                try:
                    await self._ui_service.send_timeout_warning(
                        chat_id=tracked.chat_id,
                        operation_id=operation_id,
                        elapsed_seconds=elapsed,
                    )
                except Exception as e:
                    logger.warning(f"Failed to send timeout warning: {e}")
                    
            logger.warning(f"Operation {operation_id} timed out")


# Singleton instance for global access
_progress_reporter: Optional[ProgressReporter] = None


def get_progress_reporter(ui_service: Optional["UIServiceProtocol"] = None) -> ProgressReporter:
    """Get the global progress reporter instance."""
    global _progress_reporter
    if _progress_reporter is None:
        _progress_reporter = ProgressReporter(ui_service=ui_service)
    return _progress_reporter


def reset_progress_reporter() -> None:
    """Reset the global progress reporter (for testing)."""
    global _progress_reporter
    _progress_reporter = None
