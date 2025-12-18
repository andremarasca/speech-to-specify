"""Contract tests for TranscriptionService.

These tests validate the TranscriptionService interface contract
defined in contracts/transcription-service.md.

Note: These tests use a mock implementation to verify the interface
contract without requiring GPU/Whisper installation.
"""

import pytest
from pathlib import Path
from typing import Callable, Optional

from src.services.transcription.base import (
    TranscriptionService,
    TranscriptionResult,
    ModelLoadError,
)


class MockTranscriptionService(TranscriptionService):
    """Mock implementation for testing the interface contract."""

    def __init__(self, should_fail_load: bool = False):
        self._ready = False
        self._should_fail_load = should_fail_load

    def is_ready(self) -> bool:
        return self._ready

    def load_model(self) -> None:
        if self._should_fail_load:
            raise ModelLoadError("Mock load failure")
        self._ready = True

    def transcribe(self, audio_path: Path) -> TranscriptionResult:
        if not self._ready:
            return TranscriptionResult.failure("Model not loaded")

        if not audio_path.exists():
            return TranscriptionResult.failure(f"File not found: {audio_path}")

        # Mock successful transcription
        return TranscriptionResult(
            text=f"Mock transcription of {audio_path.name}",
            language="en",
            duration_seconds=30.0,
            success=True,
        )

    def transcribe_batch(
        self,
        audio_paths: list[Path],
        on_progress: Optional[Callable[[int, int], None]] = None,
    ) -> list[TranscriptionResult]:
        results = []
        total = len(audio_paths)

        for i, path in enumerate(audio_paths):
            result = self.transcribe(path)
            results.append(result)

            if on_progress:
                on_progress(i + 1, total)

        return results

    def unload_model(self) -> None:
        self._ready = False


@pytest.fixture
def mock_service() -> MockTranscriptionService:
    """Create a mock transcription service."""
    return MockTranscriptionService()


@pytest.fixture
def audio_file(tmp_path: Path) -> Path:
    """Create a mock audio file for testing."""
    audio = tmp_path / "test_audio.ogg"
    audio.write_bytes(b"mock audio content")
    return audio


class TestTranscriptionServiceInterface:
    """Test the TranscriptionService interface contract."""

    def test_is_ready_false_before_load(self, mock_service: MockTranscriptionService):
        """Service should not be ready before load_model()."""
        assert not mock_service.is_ready()

    def test_is_ready_true_after_load(self, mock_service: MockTranscriptionService):
        """Service should be ready after successful load_model()."""
        mock_service.load_model()
        assert mock_service.is_ready()

    def test_load_model_raises_on_failure(self):
        """load_model() should raise ModelLoadError on failure."""
        service = MockTranscriptionService(should_fail_load=True)

        with pytest.raises(ModelLoadError):
            service.load_model()

    def test_unload_model_clears_ready(self, mock_service: MockTranscriptionService):
        """unload_model() should set is_ready to False."""
        mock_service.load_model()
        assert mock_service.is_ready()

        mock_service.unload_model()
        assert not mock_service.is_ready()


class TestTranscribeMethod:
    """Test the transcribe() method contract."""

    def test_transcribe_returns_result(
        self, mock_service: MockTranscriptionService, audio_file: Path
    ):
        """transcribe() should return TranscriptionResult."""
        mock_service.load_model()
        result = mock_service.transcribe(audio_file)

        assert isinstance(result, TranscriptionResult)
        assert result.success
        assert len(result.text) > 0

    def test_transcribe_without_load_fails(
        self, mock_service: MockTranscriptionService, audio_file: Path
    ):
        """transcribe() without load_model() should fail."""
        result = mock_service.transcribe(audio_file)

        assert not result.success
        assert result.error_message is not None

    def test_transcribe_missing_file_fails(
        self, mock_service: MockTranscriptionService, tmp_path: Path
    ):
        """transcribe() with missing file should fail."""
        mock_service.load_model()
        missing = tmp_path / "nonexistent.ogg"

        result = mock_service.transcribe(missing)

        assert not result.success
        assert "not found" in result.error_message.lower()

    def test_transcribe_result_has_required_fields(
        self, mock_service: MockTranscriptionService, audio_file: Path
    ):
        """TranscriptionResult should have all required fields."""
        mock_service.load_model()
        result = mock_service.transcribe(audio_file)

        assert hasattr(result, "text")
        assert hasattr(result, "language")
        assert hasattr(result, "duration_seconds")
        assert hasattr(result, "success")
        assert hasattr(result, "error_message")


class TestTranscribeBatchMethod:
    """Test the transcribe_batch() method contract."""

    def test_batch_returns_list(
        self, mock_service: MockTranscriptionService, tmp_path: Path
    ):
        """transcribe_batch() should return list of results."""
        mock_service.load_model()

        # Create multiple audio files
        files = []
        for i in range(3):
            f = tmp_path / f"audio_{i}.ogg"
            f.write_bytes(b"content")
            files.append(f)

        results = mock_service.transcribe_batch(files)

        assert isinstance(results, list)
        assert len(results) == 3
        assert all(isinstance(r, TranscriptionResult) for r in results)

    def test_batch_calls_progress_callback(
        self, mock_service: MockTranscriptionService, tmp_path: Path
    ):
        """transcribe_batch() should call progress callback."""
        mock_service.load_model()

        files = []
        for i in range(3):
            f = tmp_path / f"audio_{i}.ogg"
            f.write_bytes(b"content")
            files.append(f)

        progress_calls = []

        def on_progress(completed: int, total: int):
            progress_calls.append((completed, total))

        mock_service.transcribe_batch(files, on_progress=on_progress)

        assert len(progress_calls) == 3
        assert progress_calls == [(1, 3), (2, 3), (3, 3)]

    def test_batch_preserves_order(
        self, mock_service: MockTranscriptionService, tmp_path: Path
    ):
        """transcribe_batch() should return results in input order."""
        mock_service.load_model()

        files = []
        for name in ["first", "second", "third"]:
            f = tmp_path / f"{name}.ogg"
            f.write_bytes(b"content")
            files.append(f)

        results = mock_service.transcribe_batch(files)

        assert "first" in results[0].text
        assert "second" in results[1].text
        assert "third" in results[2].text


class TestTranscriptionResult:
    """Test the TranscriptionResult dataclass."""

    def test_success_result(self):
        """Successful result should have expected values."""
        result = TranscriptionResult(
            text="Hello world",
            language="en",
            duration_seconds=5.5,
            success=True,
        )

        assert result.success
        assert result.text == "Hello world"
        assert result.error_message is None

    def test_failure_factory(self):
        """failure() factory should create failed result."""
        result = TranscriptionResult.failure("Something went wrong")

        assert not result.success
        assert result.error_message == "Something went wrong"
        assert result.text == ""
        assert result.duration_seconds == 0.0
