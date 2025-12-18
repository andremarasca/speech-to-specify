"""Whisper-based transcription service.

This module implements the TranscriptionService interface using
OpenAI's Whisper model for local speech-to-text conversion.

Following research.md decision:
- Model: small.en (fits RTX 3050 4GB VRAM)
- Device: cuda (forced GPU)
- FP16: enabled for speed and memory efficiency
"""

import logging
from pathlib import Path
from typing import Callable, Optional

from src.lib.config import WhisperConfig
from src.services.transcription.base import (
    TranscriptionService,
    TranscriptionResult,
    ModelLoadError,
    CudaNotAvailableError,
    UnsupportedAudioFormatError,
)

logger = logging.getLogger(__name__)

# Supported audio formats
SUPPORTED_FORMATS = {".ogg", ".mp3", ".wav", ".m4a", ".webm", ".flac"}


class WhisperTranscriptionService(TranscriptionService):
    """
    Whisper-based transcription service.

    Uses OpenAI's Whisper model for local speech-to-text conversion.
    The model is loaded once at startup and reused for all transcriptions.
    """

    def __init__(self, config: WhisperConfig):
        """
        Initialize the Whisper transcription service.

        Args:
            config: Whisper configuration (model name, device, fp16)
        """
        self.config = config
        self._model = None
        self._ready = False

    def is_ready(self) -> bool:
        """Check if the model is loaded and ready."""
        return self._ready and self._model is not None

    def load_model(self) -> None:
        """
        Load the Whisper model into memory.

        Raises:
            CudaNotAvailableError: If device is cuda but CUDA is not available
            ModelLoadError: If model loading fails for any other reason
        """
        try:
            import torch
            import whisper

            # Check CUDA availability if required
            if self.config.device == "cuda":
                if not torch.cuda.is_available():
                    raise CudaNotAvailableError(
                        "CUDA requested but not available. "
                        "Install PyTorch with CUDA support or set WHISPER_DEVICE=cpu"
                    )
                logger.info(f"CUDA available: {torch.cuda.get_device_name(0)}")

            logger.info(f"Loading Whisper model: {self.config.model_name}")
            logger.info(f"Device: {self.config.device}, FP16: {self.config.fp16}")

            # Load model
            self._model = whisper.load_model(
                self.config.model_name,
                device=self.config.device,
                download_root=self.config.cache_dir,
            )

            self._ready = True
            logger.info("Whisper model loaded successfully")

        except ImportError as e:
            raise ModelLoadError(
                f"Whisper not installed. Run: pip install openai-whisper\n{e}"
            ) from e

        except Exception as e:
            self._ready = False
            raise ModelLoadError(f"Failed to load Whisper model: {e}") from e

    def transcribe(self, audio_path: Path) -> TranscriptionResult:
        """
        Transcribe a single audio file.

        Args:
            audio_path: Path to audio file

        Returns:
            TranscriptionResult with transcribed text or error
        """
        if not self.is_ready():
            return TranscriptionResult.failure("Model not loaded")

        # Validate file exists
        if not audio_path.exists():
            return TranscriptionResult.failure(f"Audio file not found: {audio_path}")

        # Validate format
        suffix = audio_path.suffix.lower()
        if suffix not in SUPPORTED_FORMATS:
            return TranscriptionResult.failure(
                f"Unsupported audio format: {suffix}. "
                f"Supported: {', '.join(SUPPORTED_FORMATS)}"
            )

        try:
            logger.debug(f"Transcribing: {audio_path}")

            # Transcribe with Whisper
            result = self._model.transcribe(
                str(audio_path),
                fp16=self.config.fp16,
                language="en",  # Force English for small.en model
            )

            text = result.get("text", "").strip()
            language = result.get("language", "en")

            # Calculate duration from segments if available
            segments = result.get("segments", [])
            if segments:
                duration = segments[-1].get("end", 0.0)
            else:
                duration = 0.0

            logger.debug(f"Transcription complete: {len(text)} chars, {duration:.1f}s")

            return TranscriptionResult(
                text=text,
                language=language,
                duration_seconds=duration,
                success=True,
            )

        except Exception as e:
            logger.exception(f"Transcription failed for {audio_path}: {e}")
            return TranscriptionResult.failure(str(e))

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
        results = []
        total = len(audio_paths)

        for i, audio_path in enumerate(audio_paths):
            result = self.transcribe(audio_path)
            results.append(result)

            if on_progress:
                on_progress(i + 1, total)

        return results

    def unload_model(self) -> None:
        """Release model from memory."""
        if self._model is not None:
            logger.info("Unloading Whisper model")

            # Clear model reference
            del self._model
            self._model = None
            self._ready = False

            # Force garbage collection and clear CUDA cache
            try:
                import gc
                import torch

                gc.collect()
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()

            except ImportError:
                pass

            logger.info("Whisper model unloaded")
