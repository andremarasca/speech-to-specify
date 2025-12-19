"""Audio queue for rate limit handling with position feedback.

Per T031f from 005-telegram-ux-overhaul.

When users send many voice messages rapidly, this queue provides:
- Rate limiting with configurable thresholds
- Position feedback (ERR_TELEGRAM_002)
- Sequential processing to avoid Telegram API rate limits
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Awaitable, Optional, Any
from collections import deque

from src.lib.config import get_ui_config

logger = logging.getLogger(__name__)


@dataclass
class QueuedAudio:
    """An audio item waiting in the queue.
    
    Attributes:
        chat_id: Telegram chat ID
        file_id: Telegram file ID for downloading
        duration: Audio duration in seconds
        queued_at: When the item was added to queue
        position: Position in queue (1-indexed, updated dynamically)
    """
    chat_id: int
    file_id: str
    duration: Optional[int] = None
    file_size: Optional[int] = None
    queued_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    position: int = 0


@dataclass
class QueueStatus:
    """Status of the audio queue.
    
    Attributes:
        queue_size: Current number of items in queue
        is_processing: Whether an item is currently being processed
        position: Position of a specific item (if requested)
        estimated_wait_seconds: Rough estimate of wait time
    """
    queue_size: int
    is_processing: bool
    position: int = 0
    estimated_wait_seconds: float = 0.0


class AudioQueue:
    """Rate-limited audio processing queue.
    
    Manages incoming audio messages and processes them sequentially
    to avoid Telegram API rate limits. Provides position feedback
    when queue is active.
    
    Example:
        queue = AudioQueue(max_size=10)
        queue.on_process(handle_audio)
        
        # When voice message arrives
        status = await queue.enqueue(chat_id, file_id, duration)
        if status.position > 1:
            # Show queue position to user
    """
    
    def __init__(
        self,
        max_size: Optional[int] = None,
        process_delay_seconds: float = 0.5,
        avg_process_time_seconds: float = 5.0,
    ):
        """Initialize the audio queue.
        
        Args:
            max_size: Maximum queue size (None = use config default)
            process_delay_seconds: Delay between processing items
            avg_process_time_seconds: Average time to process one item (for ETA)
        """
        config = get_ui_config()
        self._max_size = max_size or config.audio_queue_max_size
        self._process_delay = process_delay_seconds
        self._avg_process_time = avg_process_time_seconds
        
        self._queue: deque[QueuedAudio] = deque()
        self._is_processing = False
        self._processor: Optional[Callable[[QueuedAudio], Awaitable[Any]]] = None
        self._on_position_update: Optional[Callable[[int, int, int], Awaitable[None]]] = None
        self._processing_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()
        
    def on_process(
        self,
        handler: Callable[[QueuedAudio], Awaitable[Any]],
    ) -> None:
        """Register handler for processing queued audio.
        
        Args:
            handler: Async function that processes a QueuedAudio item
        """
        self._processor = handler
        
    def on_position_update(
        self,
        handler: Callable[[int, int, int], Awaitable[None]],
    ) -> None:
        """Register handler for position updates.
        
        Called when queue position changes for waiting items.
        
        Args:
            handler: Async function(chat_id, position, total) called on updates
        """
        self._on_position_update = handler
        
    async def enqueue(
        self,
        chat_id: int,
        file_id: str,
        duration: Optional[int] = None,
        file_size: Optional[int] = None,
    ) -> QueueStatus:
        """Add audio to the processing queue.
        
        If queue is empty and not processing, processes immediately.
        Otherwise queues the item and returns position.
        
        Args:
            chat_id: Telegram chat ID
            file_id: Telegram file ID
            duration: Audio duration in seconds
            file_size: File size in bytes
            
        Returns:
            QueueStatus with position info
            
        Raises:
            QueueFullError: If queue has reached max_size
        """
        async with self._lock:
            # Check if queue is at capacity
            if len(self._queue) >= self._max_size:
                raise QueueFullError(
                    f"Audio queue is full ({self._max_size} items). "
                    "Please wait for processing to complete."
                )
            
            # Create queued item
            item = QueuedAudio(
                chat_id=chat_id,
                file_id=file_id,
                duration=duration,
                file_size=file_size,
            )
            
            # Add to queue
            self._queue.append(item)
            position = len(self._queue)
            item.position = position
            
            # Calculate estimated wait
            estimated_wait = (position - 1) * self._avg_process_time
            if self._is_processing:
                estimated_wait += self._avg_process_time / 2  # Assume half done
                
            status = QueueStatus(
                queue_size=len(self._queue),
                is_processing=self._is_processing,
                position=position,
                estimated_wait_seconds=estimated_wait,
            )
            
            # Start processing if not already running
            if not self._is_processing and self._processor:
                self._start_processing()
                
            logger.debug(
                f"Audio queued: position={position}, total={len(self._queue)}, "
                f"is_processing={self._is_processing}"
            )
            
            return status
            
    def _start_processing(self) -> None:
        """Start the background processing task."""
        if self._processing_task is None or self._processing_task.done():
            self._processing_task = asyncio.create_task(self._process_loop())
            
    async def _process_loop(self) -> None:
        """Background loop that processes queued items."""
        self._is_processing = True
        
        try:
            while True:
                async with self._lock:
                    if not self._queue:
                        self._is_processing = False
                        break
                        
                    item = self._queue.popleft()
                    
                    # Update positions for remaining items
                    await self._update_positions()
                    
                if self._processor:
                    try:
                        await self._processor(item)
                    except Exception as e:
                        logger.error(f"Error processing audio: {e}")
                        
                # Small delay between processing to avoid rate limits
                if self._queue:
                    await asyncio.sleep(self._process_delay)
                    
        except asyncio.CancelledError:
            logger.info("Audio queue processing cancelled")
            self._is_processing = False
            raise
        except Exception as e:
            logger.error(f"Error in queue processing loop: {e}")
            self._is_processing = False
            
    async def _update_positions(self) -> None:
        """Update positions for all items in queue and notify."""
        for i, item in enumerate(self._queue, 1):
            old_position = item.position
            item.position = i
            
            # Notify if position changed and handler registered
            if old_position != i and self._on_position_update:
                try:
                    await self._on_position_update(
                        item.chat_id,
                        item.position,
                        len(self._queue),
                    )
                except Exception as e:
                    logger.warning(f"Error notifying position update: {e}")
                    
    def get_status(self, chat_id: int) -> QueueStatus:
        """Get queue status for a specific chat.
        
        Args:
            chat_id: Telegram chat ID
            
        Returns:
            QueueStatus with position if item found
        """
        position = 0
        for i, item in enumerate(self._queue, 1):
            if item.chat_id == chat_id:
                position = i
                break
                
        estimated_wait = (position - 1) * self._avg_process_time if position > 0 else 0
        
        return QueueStatus(
            queue_size=len(self._queue),
            is_processing=self._is_processing,
            position=position,
            estimated_wait_seconds=estimated_wait,
        )
        
    @property
    def size(self) -> int:
        """Current queue size."""
        return len(self._queue)
        
    @property
    def is_empty(self) -> bool:
        """Check if queue is empty."""
        return len(self._queue) == 0
        
    @property
    def is_processing(self) -> bool:
        """Check if currently processing."""
        return self._is_processing
        
    async def clear(self) -> int:
        """Clear all pending items from queue.
        
        Returns:
            Number of items cleared
        """
        async with self._lock:
            count = len(self._queue)
            self._queue.clear()
            return count
            
    async def shutdown(self) -> None:
        """Gracefully shutdown the queue processor."""
        if self._processing_task and not self._processing_task.done():
            self._processing_task.cancel()
            try:
                await self._processing_task
            except asyncio.CancelledError:
                pass
        self._queue.clear()
        self._is_processing = False


class QueueFullError(Exception):
    """Raised when the audio queue is at capacity."""
    pass


# Singleton instance for global queue access
_audio_queue: Optional[AudioQueue] = None


def get_audio_queue() -> AudioQueue:
    """Get the global audio queue instance."""
    global _audio_queue
    if _audio_queue is None:
        _audio_queue = AudioQueue()
    return _audio_queue


def reset_audio_queue() -> None:
    """Reset the global audio queue (for testing)."""
    global _audio_queue
    _audio_queue = None
