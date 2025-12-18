"""Base interface for transcription service.

This module defines the TranscriptionService abstract base class
and TranscriptionResult dataclass following contracts/transcription-service.md.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional


@dataclass
class TranscriptionResult:
    """
    Result of a transcription operation.

    Attributes:
        text: Transcribed text content
        language: Detected or configured language code
        duration_seconds: Duration of audio processed
        success: Whether transcription completed successfully
        error_message: Error description if success is False
    """

    text: str
    language: str
    duration_seconds: float
    success: bool
    error_message: Optional[str] = None

    @classmethod
    def failure(cls, error_message: str) -> "TranscriptionResult":
        """Create a failed transcription result."""
        return cls(
            text="",
            language="",
            duration_seconds=0.0,
            success=False,
            error_message=error_message,
        )


class TranscriptionService(ABC):
    """
    Abstract base class for transcription services.

    Defines the interface for speech-to-text services as specified
    in contracts/transcription-service.md.
    """

    @abstractmethod
    def is_ready(self) -> bool:
        """
        Check if the model is loaded and ready for transcription.

        Returns:
            True if ready, False otherwise
        """
        pass

    @abstractmethod
    def load_model(self) -> None:
        """
        Load the transcription model into memory.

        Should be called once at daemon startup. Loading the model
        can take several seconds and require significant memory.

        Raises:
            ModelLoadError: If model loading fails (e.g., CUDA not available)
        """
        pass

    @abstractmethod
    def transcribe(self, audio_path: Path) -> TranscriptionResult:
        """
        Transcribe a single audio file.

        Args:
            audio_path: Path to audio file (ogg, mp3, wav, m4a, webm)

        Returns:
            TranscriptionResult with transcribed text or error
        """
        pass

    @abstractmethod
    def transcribe_batch(
        self,
        audio_paths: list[Path],
        on_progress: Optional[Callable[[int, int], None]] = None,
    ) -> list[TranscriptionResult]:
        """
        Transcribe multiple audio files sequentially.

        Args:
            audio_paths: List of paths to audio files
            on_progress: Optional callback(completed, total) after each file

        Returns:
            List of TranscriptionResult in same order as input
        """
        pass

    @abstractmethod
    def unload_model(self) -> None:
        """
        Release model from memory.

        Should be called during graceful shutdown to free resources.
        """
        pass


class ModelLoadError(Exception):
    """Raised when model loading fails."""

    pass


class CudaNotAvailableError(ModelLoadError):
    """Raised when CUDA is required but not available."""

    pass


class UnsupportedAudioFormatError(Exception):
    """Raised when audio format is not supported."""

    pass
