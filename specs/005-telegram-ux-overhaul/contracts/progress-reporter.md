# Contract: ProgressReporter

**Feature**: 005-telegram-ux-overhaul  
**Module**: `src/services/presentation/progress.py`  
**Date**: 2025-12-19

## Purpose

ProgressReporter tracks and reports progress of long-running operations (transcription, embedding, pipeline processing). It manages throttling of UI updates and timeout detection while delegating actual message rendering to UIService.

## Interface

```python
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Callable, Awaitable
from src.models.ui_state import ProgressState, OperationType

class ProgressReporterProtocol(ABC):
    """Protocol for progress tracking and reporting."""
    
    @abstractmethod
    async def start_operation(
        self, 
        operation_type: OperationType,
        total_steps: int,
        chat_id: int,
        on_update: Callable[[ProgressState], Awaitable[None]] | None = None
    ) -> str:
        """
        Initialize progress tracking for an operation.
        
        Args:
            operation_type: Type of operation (TRANSCRIPTION, etc.)
            total_steps: Total number of steps
            chat_id: Telegram chat for progress messages
            on_update: Optional callback for progress updates
            
        Returns:
            operation_id for subsequent updates
        """
        ...
    
    @abstractmethod
    async def update_progress(
        self, 
        operation_id: str,
        current_step: int,
        step_description: str
    ) -> None:
        """
        Update progress for an operation.
        
        Args:
            operation_id: ID from start_operation
            current_step: Current step number (1-indexed)
            step_description: Human-readable description
            
        Side Effects:
            - Updates progress message if throttle interval passed
            - Checks for timeout condition
        """
        ...
    
    @abstractmethod
    async def complete_operation(
        self, 
        operation_id: str,
        success: bool = True
    ) -> None:
        """
        Mark operation as complete.
        
        Args:
            operation_id: ID from start_operation
            success: Whether operation completed successfully
            
        Side Effects:
            - Sends final progress update (100% or error)
            - Cleans up operation state
        """
        ...
    
    @abstractmethod
    async def cancel_operation(self, operation_id: str) -> None:
        """
        Cancel an in-progress operation.
        
        Args:
            operation_id: ID from start_operation
            
        Side Effects:
            - Sends cancellation confirmation
            - Cleans up operation state
        """
        ...
    
    @abstractmethod
    def get_progress(self, operation_id: str) -> ProgressState | None:
        """
        Get current progress state.
        
        Args:
            operation_id: ID from start_operation
            
        Returns:
            Current ProgressState or None if not found
        """
        ...
    
    @abstractmethod
    def is_timed_out(self, operation_id: str) -> bool:
        """
        Check if operation has exceeded timeout threshold.
        
        Args:
            operation_id: ID from start_operation
            
        Returns:
            True if operation should trigger timeout warning
        """
        ...


class ProgressReporter(ProgressReporterProtocol):
    """Implementation with throttling and timeout detection."""
    
    def __init__(
        self,
        ui_service: "UIServiceProtocol",
        update_interval_seconds: float = 5.0,  # From config
        timeout_seconds: float = 120.0,        # From config
        avg_seconds_per_audio_minute: float = 10.0  # For ETA estimation
    ):
        ...
```

## Progress Bar Formatting

```python
def format_progress_bar(
    current: int, 
    total: int, 
    width: int = 10,
    simplified: bool = False
) -> str:
    """
    Format visual progress bar.
    
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
    percentage = int((current / total) * 100) if total > 0 else 0
    
    if simplified:
        return f"Progresso: {percentage}% ({current} de {total})"
    
    filled = int(width * current / total) if total > 0 else 0
    bar = "▓" * filled + "░" * (width - filled)
    return f"{bar} {percentage}%"
```

## ETA Calculation

```python
def estimate_completion(
    started_at: datetime,
    current_step: int,
    total_steps: int,
    audio_minutes: float | None = None,
    avg_seconds_per_minute: float = 10.0
) -> datetime | None:
    """
    Estimate operation completion time.
    
    For transcription: Uses audio duration heuristic
    For other operations: Uses elapsed time extrapolation
    
    Returns None if estimation not possible (step 0, etc.)
    """
    if current_step == 0:
        return None
    
    if audio_minutes is not None:
        # Transcription: estimate based on audio length
        remaining_minutes = audio_minutes * (1 - current_step / total_steps)
        remaining_seconds = remaining_minutes * avg_seconds_per_minute
    else:
        # General: extrapolate from elapsed time
        elapsed = (datetime.utcnow() - started_at).total_seconds()
        rate = elapsed / current_step
        remaining_seconds = rate * (total_steps - current_step)
    
    return datetime.utcnow() + timedelta(seconds=remaining_seconds)
```

## Throttling Logic

```python
async def _should_update_ui(self, operation_id: str) -> bool:
    """Check if enough time has passed for next UI update."""
    state = self._operations.get(operation_id)
    if not state:
        return False
    
    elapsed = (datetime.utcnow() - state.last_update_at).total_seconds()
    return elapsed >= self._update_interval_seconds
```

## Timeout Handling

```python
async def _check_timeout(self, operation_id: str) -> None:
    """Check and handle timeout condition."""
    state = self._operations.get(operation_id)
    if not state:
        return
    
    elapsed = (datetime.utcnow() - state.started_at).total_seconds()
    
    if elapsed > self._timeout_seconds and not state.timeout_warned:
        state.timeout_warned = True
        await self._ui_service.send_timeout_warning(
            chat_id=state.chat_id,
            operation_id=operation_id,
            elapsed_seconds=elapsed
        )
```

## Testing Contract

```python
# tests/contract/test_progress_reporter.py

async def test_start_operation_returns_unique_id():
    """Each operation gets a unique ID."""

async def test_update_respects_throttle_interval():
    """UI updates are throttled to configured interval."""

async def test_progress_bar_never_exceeds_100():
    """Progress percentage capped at 100%."""

async def test_timeout_warning_sent_once():
    """Timeout warning sent only once per operation."""

async def test_eta_updates_as_progress_advances():
    """ETA recalculated on each progress update."""

async def test_complete_operation_shows_100_percent():
    """Completion always shows 100% regardless of step count."""

async def test_cancel_cleans_up_state():
    """Cancelled operations are removed from tracking."""
```

## Configuration Parameters

| Parameter | Default | Config Key | Description |
|-----------|---------|------------|-------------|
| Update interval | 5.0s | `UI_PROGRESS_INTERVAL_SECONDS` | Minimum time between UI updates |
| Timeout threshold | 120.0s | `OPERATION_TIMEOUT_SECONDS` | When to show timeout warning |
| ETA smoothing | 10.0s/min | `AVG_SECONDS_PER_AUDIO_MINUTE` | Heuristic for transcription ETA |

## Integration with UIService

ProgressReporter delegates all Telegram message operations to UIService:

```python
# In ProgressReporter
await self._ui_service.send_progress(chat_id, progress_state, preferences)
await self._ui_service.update_progress(message, progress_state, preferences)
```

This maintains single responsibility: ProgressReporter tracks state, UIService renders UI.
