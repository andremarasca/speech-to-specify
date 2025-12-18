"""Transcription service package for speech-to-text."""

from src.services.transcription.base import TranscriptionService, TranscriptionResult
from src.services.transcription.whisper import WhisperTranscriptionService

__all__ = ["TranscriptionService", "TranscriptionResult", "WhisperTranscriptionService"]
