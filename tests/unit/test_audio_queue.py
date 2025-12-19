"""Unit tests for audio queue with rate limit handling.

Per T031f from 005-telegram-ux-overhaul.

Tests the AudioQueue component that manages rate limiting
and provides position feedback for queued audio messages.
"""

import asyncio
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from src.services.audio.queue import (
    AudioQueue,
    QueuedAudio,
    QueueStatus,
    QueueFullError,
    get_audio_queue,
    reset_audio_queue,
)


class TestAudioQueue:
    """Tests for AudioQueue class."""

    @pytest.fixture
    def queue(self):
        """Create a fresh queue for each test."""
        return AudioQueue(max_size=5, process_delay_seconds=0.01)

    @pytest.fixture
    def mock_processor(self):
        """Create a mock audio processor."""
        return AsyncMock(return_value=None)

    @pytest.mark.asyncio
    async def test_enqueue_single_item(self, queue, mock_processor):
        """Single item should be processed immediately."""
        queue.on_process(mock_processor)

        status = await queue.enqueue(
            chat_id=123,
            file_id="file_abc",
            duration=10,
        )

        # Should be first in queue
        assert status.position == 1
        assert status.queue_size == 1

        # Wait for processing
        await asyncio.sleep(0.1)

        # Should have been processed
        mock_processor.assert_called_once()
        assert queue.is_empty

    @pytest.mark.asyncio
    async def test_enqueue_multiple_items_sequential(self, queue, mock_processor):
        """Multiple items should be processed in order."""
        processed_order = []

        async def track_processor(item: QueuedAudio):
            processed_order.append(item.file_id)
            await asyncio.sleep(0.02)

        queue.on_process(track_processor)

        # Enqueue multiple items quickly
        status1 = await queue.enqueue(123, "file_1", 10)
        status2 = await queue.enqueue(123, "file_2", 10)
        status3 = await queue.enqueue(123, "file_3", 10)

        assert status1.position == 1
        assert status2.position == 2
        assert status3.position == 3

        # Wait for all processing
        await asyncio.sleep(0.2)

        # Should be processed in order
        assert processed_order == ["file_1", "file_2", "file_3"]
        assert queue.is_empty

    @pytest.mark.asyncio
    async def test_queue_full_raises_error(self, queue):
        """Should raise QueueFullError when at capacity."""
        queue.on_process(AsyncMock(side_effect=asyncio.sleep(10)))

        # Fill the queue
        for i in range(5):
            await queue.enqueue(123, f"file_{i}", 10)

        # Should raise when full
        with pytest.raises(QueueFullError):
            await queue.enqueue(123, "file_overflow", 10)

    @pytest.mark.asyncio
    async def test_position_update_callback(self, queue):
        """Position updates should be notified when items complete."""
        position_updates = []

        async def track_positions(chat_id, position, total):
            position_updates.append((chat_id, position, total))

        async def slow_processor(item: QueuedAudio):
            await asyncio.sleep(0.03)

        queue.on_process(slow_processor)
        queue.on_position_update(track_positions)

        # Enqueue multiple items
        await queue.enqueue(111, "file_1", 10)
        await queue.enqueue(222, "file_2", 10)
        await queue.enqueue(333, "file_3", 10)

        # Wait for processing
        await asyncio.sleep(0.2)

        # Items 2 and 3 should have received position updates
        # When item 1 completes, item 2 moves to position 1, item 3 to position 2
        assert len(position_updates) > 0

    @pytest.mark.asyncio
    async def test_get_status_for_chat(self, queue):
        """Should return correct status for specific chat."""
        async def slow_processor(item: QueuedAudio):
            await asyncio.sleep(0.5)

        queue.on_process(slow_processor)

        await queue.enqueue(111, "file_1", 10)
        await queue.enqueue(222, "file_2", 10)
        await queue.enqueue(333, "file_3", 10)

        # Check status for each chat
        status_222 = queue.get_status(222)
        assert status_222.position == 2
        assert status_222.queue_size == 3

        status_333 = queue.get_status(333)
        assert status_333.position == 3

        # Unknown chat should have position 0
        status_unknown = queue.get_status(999)
        assert status_unknown.position == 0

        # Cleanup
        await queue.shutdown()

    @pytest.mark.asyncio
    async def test_clear_queue(self, queue):
        """Should clear all pending items."""
        async def slow_processor(item: QueuedAudio):
            await asyncio.sleep(1)

        queue.on_process(slow_processor)

        await queue.enqueue(123, "file_1", 10)
        await queue.enqueue(123, "file_2", 10)
        await queue.enqueue(123, "file_3", 10)

        # Clear the queue
        cleared = await queue.clear()
        assert cleared == 3
        assert queue.is_empty

        # Cleanup
        await queue.shutdown()

    @pytest.mark.asyncio
    async def test_estimated_wait_time(self, queue):
        """Should calculate estimated wait time."""
        queue._avg_process_time = 5.0  # 5 seconds per item

        async def slow_processor(item: QueuedAudio):
            await asyncio.sleep(0.5)

        queue.on_process(slow_processor)

        await queue.enqueue(111, "file_1", 10)
        status = await queue.enqueue(222, "file_2", 10)

        # Position 2 should wait for 1 item = ~5 seconds
        # But processing started, so add half the avg time
        assert status.estimated_wait_seconds > 0

        # Cleanup
        await queue.shutdown()

    @pytest.mark.asyncio
    async def test_shutdown_stops_processing(self, queue):
        """Shutdown should stop processing and clear queue."""
        process_count = 0

        async def slow_processor(item: QueuedAudio):
            nonlocal process_count
            await asyncio.sleep(0.1)
            process_count += 1

        queue.on_process(slow_processor)

        # Enqueue items
        await queue.enqueue(123, "file_1", 10)
        await queue.enqueue(123, "file_2", 10)
        await queue.enqueue(123, "file_3", 10)

        # Shutdown immediately
        await queue.shutdown()

        # Queue should be empty
        assert queue.is_empty
        assert not queue.is_processing

    @pytest.mark.asyncio
    async def test_processor_error_continues(self, queue):
        """Errors in processor should not stop queue."""
        process_count = 0

        async def flaky_processor(item: QueuedAudio):
            nonlocal process_count
            process_count += 1
            if process_count == 1:
                raise ValueError("Simulated error")

        queue.on_process(flaky_processor)

        await queue.enqueue(123, "file_1", 10)
        await queue.enqueue(123, "file_2", 10)

        # Wait for processing
        await asyncio.sleep(0.1)

        # Both should have been attempted
        assert process_count == 2
        assert queue.is_empty


class TestQueuedAudio:
    """Tests for QueuedAudio dataclass."""

    def test_queued_audio_creation(self):
        """Should create QueuedAudio with correct defaults."""
        item = QueuedAudio(
            chat_id=123,
            file_id="file_abc",
            duration=30,
        )

        assert item.chat_id == 123
        assert item.file_id == "file_abc"
        assert item.duration == 30
        assert item.position == 0
        assert item.queued_at is not None

    def test_queued_audio_with_all_fields(self):
        """Should accept all optional fields."""
        now = datetime.now(timezone.utc)
        item = QueuedAudio(
            chat_id=123,
            file_id="file_abc",
            duration=30,
            file_size=12345,
            queued_at=now,
            position=5,
        )

        assert item.file_size == 12345
        assert item.queued_at == now
        assert item.position == 5


class TestQueueStatus:
    """Tests for QueueStatus dataclass."""

    def test_queue_status_basic(self):
        """Should create QueueStatus with required fields."""
        status = QueueStatus(
            queue_size=5,
            is_processing=True,
        )

        assert status.queue_size == 5
        assert status.is_processing is True
        assert status.position == 0
        assert status.estimated_wait_seconds == 0.0

    def test_queue_status_with_position(self):
        """Should include position when specified."""
        status = QueueStatus(
            queue_size=5,
            is_processing=True,
            position=3,
            estimated_wait_seconds=10.0,
        )

        assert status.position == 3
        assert status.estimated_wait_seconds == 10.0


class TestGlobalQueue:
    """Tests for global queue singleton."""

    def test_get_audio_queue_singleton(self):
        """Should return same instance."""
        reset_audio_queue()

        queue1 = get_audio_queue()
        queue2 = get_audio_queue()

        assert queue1 is queue2

    def test_reset_audio_queue(self):
        """Reset should create new instance."""
        queue1 = get_audio_queue()
        reset_audio_queue()
        queue2 = get_audio_queue()

        assert queue1 is not queue2
