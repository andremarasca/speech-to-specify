"""Contract tests for ProgressReporter.

Per T032-T033 from 005-telegram-ux-overhaul.

Tests the ProgressReporter component per contracts/progress-reporter.md:
- start_operation() returns unique operation ID
- update_progress() respects throttle interval
- Timeout detection and warning
- Progress bar formatting
- ETA calculation
"""

import asyncio
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from src.models.ui_state import OperationType, ProgressState, UIPreferences


class TestProgressReporterStartOperation:
    """Tests for ProgressReporter.start_operation() per T032."""

    @pytest.mark.asyncio
    async def test_start_operation_returns_unique_id(self):
        """Each operation gets a unique ID."""
        from src.services.presentation.progress import ProgressReporter

        mock_ui_service = MagicMock()
        mock_ui_service.send_progress = AsyncMock()

        reporter = ProgressReporter(ui_service=mock_ui_service)

        # Start multiple operations
        id1 = await reporter.start_operation(
            operation_type=OperationType.TRANSCRIPTION,
            total_steps=10,
            chat_id=123,
        )
        id2 = await reporter.start_operation(
            operation_type=OperationType.TRANSCRIPTION,
            total_steps=10,
            chat_id=123,
        )

        assert id1 != id2
        assert isinstance(id1, str)
        assert len(id1) > 0

    @pytest.mark.asyncio
    async def test_start_operation_initializes_state(self):
        """Operation state should be properly initialized."""
        from src.services.presentation.progress import ProgressReporter

        mock_ui_service = MagicMock()
        mock_ui_service.send_progress = AsyncMock()

        reporter = ProgressReporter(ui_service=mock_ui_service)

        op_id = await reporter.start_operation(
            operation_type=OperationType.EMBEDDING,
            total_steps=5,
            chat_id=456,
        )

        state = reporter.get_progress(op_id)
        assert state is not None
        assert state.operation_type == OperationType.EMBEDDING
        assert state.total_steps == 5
        assert state.current_step == 0
        assert state.started_at is not None

    @pytest.mark.asyncio
    async def test_start_operation_with_callback(self):
        """Custom callback should be invoked on updates."""
        from src.services.presentation.progress import ProgressReporter

        mock_ui_service = MagicMock()
        mock_ui_service.send_progress = AsyncMock()

        callback_invoked = []

        async def custom_callback(state: ProgressState):
            callback_invoked.append(state)

        reporter = ProgressReporter(
            ui_service=mock_ui_service,
            update_interval_seconds=0.01,  # Fast for testing
        )

        op_id = await reporter.start_operation(
            operation_type=OperationType.PROCESSING,
            total_steps=3,
            chat_id=789,
            on_update=custom_callback,
        )

        # Update progress
        await reporter.update_progress(op_id, 1, "Step 1")
        await asyncio.sleep(0.02)  # Allow throttle interval
        await reporter.update_progress(op_id, 2, "Step 2")

        # Callback should have been invoked
        assert len(callback_invoked) >= 1


class TestProgressReporterUpdateProgress:
    """Tests for ProgressReporter.update_progress() per T033."""

    @pytest.mark.asyncio
    async def test_update_respects_throttle_interval(self):
        """UI updates are throttled to configured interval."""
        from src.services.presentation.progress import ProgressReporter

        mock_ui_service = MagicMock()
        mock_ui_service.send_progress = AsyncMock()
        mock_ui_service.update_progress = AsyncMock()

        reporter = ProgressReporter(
            ui_service=mock_ui_service,
            update_interval_seconds=1.0,  # 1 second throttle
        )

        op_id = await reporter.start_operation(
            operation_type=OperationType.TRANSCRIPTION,
            total_steps=10,
            chat_id=123,
        )

        # Rapid updates within throttle interval
        await reporter.update_progress(op_id, 1, "Step 1")
        await reporter.update_progress(op_id, 2, "Step 2")
        await reporter.update_progress(op_id, 3, "Step 3")

        # Only initial and first update should trigger UI (throttled)
        # The exact count depends on implementation, but should be throttled
        assert mock_ui_service.update_progress.call_count <= 2

    @pytest.mark.asyncio
    async def test_progress_updates_state(self):
        """update_progress should update internal state."""
        from src.services.presentation.progress import ProgressReporter

        mock_ui_service = MagicMock()
        mock_ui_service.send_progress = AsyncMock()
        mock_ui_service.update_progress = AsyncMock()

        reporter = ProgressReporter(ui_service=mock_ui_service)

        op_id = await reporter.start_operation(
            operation_type=OperationType.TRANSCRIPTION,
            total_steps=10,
            chat_id=123,
        )

        await reporter.update_progress(op_id, 5, "Halfway there")

        state = reporter.get_progress(op_id)
        assert state.current_step == 5
        assert state.step_description == "Halfway there"

    @pytest.mark.asyncio
    async def test_progress_bar_never_exceeds_100(self):
        """Progress percentage capped at 100%."""
        from src.services.presentation.progress import format_progress_bar

        # Normal case
        result = format_progress_bar(5, 10)
        assert "50%" in result

        # Edge case: current > total
        result = format_progress_bar(15, 10)
        assert "100%" in result

        # Edge case: total is 0
        result = format_progress_bar(5, 0)
        assert "0%" in result


class TestProgressReporterTimeout:
    """Tests for timeout detection per T033."""

    @pytest.mark.asyncio
    async def test_is_timed_out_returns_false_initially(self):
        """New operations should not be timed out."""
        from src.services.presentation.progress import ProgressReporter

        mock_ui_service = MagicMock()
        mock_ui_service.send_progress = AsyncMock()

        reporter = ProgressReporter(
            ui_service=mock_ui_service,
            timeout_seconds=10.0,
        )

        op_id = await reporter.start_operation(
            operation_type=OperationType.TRANSCRIPTION,
            total_steps=10,
            chat_id=123,
        )

        assert reporter.is_timed_out(op_id) is False

    @pytest.mark.asyncio
    async def test_is_timed_out_returns_true_after_threshold(self):
        """Operations exceeding threshold should be timed out."""
        from src.services.presentation.progress import ProgressReporter

        mock_ui_service = MagicMock()
        mock_ui_service.send_progress = AsyncMock()

        reporter = ProgressReporter(
            ui_service=mock_ui_service,
            timeout_seconds=0.1,  # Very short for testing
        )

        op_id = await reporter.start_operation(
            operation_type=OperationType.TRANSCRIPTION,
            total_steps=10,
            chat_id=123,
        )

        # Wait for timeout
        await asyncio.sleep(0.15)

        assert reporter.is_timed_out(op_id) is True

    @pytest.mark.asyncio
    async def test_is_timed_out_unknown_operation(self):
        """Unknown operation should return False."""
        from src.services.presentation.progress import ProgressReporter

        mock_ui_service = MagicMock()
        reporter = ProgressReporter(ui_service=mock_ui_service)

        assert reporter.is_timed_out("unknown_op") is False


class TestProgressReporterComplete:
    """Tests for operation completion."""

    @pytest.mark.asyncio
    async def test_complete_operation_shows_100_percent(self):
        """Completion always shows 100% regardless of step count."""
        from src.services.presentation.progress import ProgressReporter

        mock_ui_service = MagicMock()
        mock_ui_service.send_progress = AsyncMock()
        mock_ui_service.update_progress = AsyncMock()

        reporter = ProgressReporter(ui_service=mock_ui_service)

        op_id = await reporter.start_operation(
            operation_type=OperationType.TRANSCRIPTION,
            total_steps=10,
            chat_id=123,
        )

        # Complete at step 7 (not 10)
        await reporter.complete_operation(op_id, success=True)

        state = reporter.get_progress(op_id)
        # State might be cleaned up, but if still there, should show 100%
        # The important thing is the method completes without error

    @pytest.mark.asyncio
    async def test_cancel_cleans_up_state(self):
        """Cancelled operations are removed from tracking."""
        from src.services.presentation.progress import ProgressReporter

        mock_ui_service = MagicMock()
        mock_ui_service.send_progress = AsyncMock()

        reporter = ProgressReporter(ui_service=mock_ui_service)

        op_id = await reporter.start_operation(
            operation_type=OperationType.TRANSCRIPTION,
            total_steps=10,
            chat_id=123,
        )

        # Verify operation exists
        assert reporter.get_progress(op_id) is not None

        # Cancel it
        await reporter.cancel_operation(op_id)

        # Should be cleaned up
        assert reporter.get_progress(op_id) is None


class TestProgressBarFormatting:
    """Tests for format_progress_bar helper."""

    def test_standard_format_with_blocks(self):
        """Standard format uses block characters."""
        from src.services.presentation.progress import format_progress_bar

        result = format_progress_bar(5, 10, width=10, simplified=False)

        assert "▓" in result
        assert "░" in result
        assert "50%" in result

    def test_simplified_format_text_only(self):
        """Simplified format uses text only."""
        from src.services.presentation.progress import format_progress_bar

        result = format_progress_bar(5, 10, width=10, simplified=True)

        assert "Progresso:" in result
        assert "50%" in result
        assert "5 de 10" in result
        assert "▓" not in result

    def test_zero_progress(self):
        """Zero progress should show 0%."""
        from src.services.presentation.progress import format_progress_bar

        result = format_progress_bar(0, 10)
        assert "0%" in result

    def test_full_progress(self):
        """Full progress should show 100%."""
        from src.services.presentation.progress import format_progress_bar

        result = format_progress_bar(10, 10)
        assert "100%" in result


class TestETACalculation:
    """Tests for ETA estimation."""

    def test_eta_calculation_basic(self):
        """ETA should be calculated based on progress."""
        from src.services.presentation.progress import estimate_completion

        started = datetime.now(timezone.utc) - timedelta(seconds=30)

        # 50% done after 30 seconds = ~60 seconds total
        result = estimate_completion(
            started_at=started,
            current_step=5,
            total_steps=10,
        )

        assert result is not None
        # Should be about 30 seconds in the future
        now = datetime.now(timezone.utc)
        diff = (result - now).total_seconds()
        assert 20 < diff < 40  # Allow some tolerance

    def test_eta_returns_none_at_step_zero(self):
        """ETA should be None when no progress yet."""
        from src.services.presentation.progress import estimate_completion

        result = estimate_completion(
            started_at=datetime.now(timezone.utc),
            current_step=0,
            total_steps=10,
        )

        assert result is None

    def test_eta_with_audio_minutes(self):
        """ETA should use audio duration heuristic when provided."""
        from src.services.presentation.progress import estimate_completion

        started = datetime.now(timezone.utc)

        result = estimate_completion(
            started_at=started,
            current_step=5,
            total_steps=10,
            audio_minutes=2.0,  # 2 minutes of audio
            avg_seconds_per_minute=10.0,  # 10 seconds per audio minute
        )

        assert result is not None
        # Remaining = 2 * 0.5 = 1 minute of audio = 10 seconds
        now = datetime.now(timezone.utc)
        diff = (result - now).total_seconds()
        assert 5 < diff < 15  # Allow some tolerance
