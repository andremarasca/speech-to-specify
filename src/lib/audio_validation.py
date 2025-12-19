"""Audio validation utilities for detecting empty/silent audio.

Per T031e and T031g from 005-telegram-ux-overhaul.

This module provides functions to validate audio data before transcription:
- Empty audio detection (0 bytes or header-only)
- Silent audio detection (below noise threshold)
- Minimum duration validation
"""

import struct
from dataclasses import dataclass
from typing import Optional


@dataclass
class ValidationResult:
    """Result of audio validation.
    
    Attributes:
        is_valid: Whether the audio passed validation
        message: Human-readable message about the validation result
        error_code: Error code if validation failed (e.g., ERR_TRANSCRIPTION_002)
    """
    is_valid: bool
    message: str = ""
    error_code: Optional[str] = None


def is_audio_empty(
    audio_data: bytes,
    min_size_bytes: int = 100,
) -> bool:
    """Check if audio data is empty or too small to contain meaningful content.
    
    Audio files typically have headers (OGG: ~28 bytes, WAV: 44 bytes).
    Files smaller than min_size_bytes are considered empty.
    
    Args:
        audio_data: Raw audio bytes
        min_size_bytes: Minimum size to be considered non-empty (default: 100)
        
    Returns:
        True if audio is empty or too small
    """
    return len(audio_data) < min_size_bytes


def is_audio_silent(
    audio_data: bytes,
    noise_threshold: float = 0.01,
    sample_size: int = 1000,
) -> bool:
    """Check if audio data is silent (below noise threshold).
    
    Analyzes the audio samples to determine if the amplitude is
    below the noise threshold. Works with raw PCM data or attempts
    to skip headers for common formats.
    
    Args:
        audio_data: Raw audio bytes (assumed 16-bit PCM samples)
        noise_threshold: Maximum amplitude ratio to be considered silent (0.0-1.0)
        sample_size: Number of samples to analyze
        
    Returns:
        True if audio appears to be silent
    """
    if len(audio_data) < 2:
        return True
    
    # Skip potential headers (OGG, WAV, etc.) - look for audio data
    # This is a simple heuristic, not a full format parser
    start_offset = 0
    
    # Try to detect OGG header
    if audio_data[:4] == b"OggS":
        start_offset = min(200, len(audio_data) // 2)
    # Try to detect WAV header
    elif audio_data[:4] == b"RIFF" and len(audio_data) > 44:
        start_offset = 44
    
    # Ensure we have enough data after header
    remaining = audio_data[start_offset:]
    if len(remaining) < 4:
        return True
    
    # Analyze samples (assume 16-bit little-endian PCM)
    max_amplitude = 0
    samples_analyzed = 0
    
    for i in range(0, min(len(remaining) - 1, sample_size * 2), 2):
        try:
            # Unpack as signed 16-bit little-endian
            sample = struct.unpack("<h", remaining[i:i+2])[0]
            max_amplitude = max(max_amplitude, abs(sample))
            samples_analyzed += 1
        except struct.error:
            continue
    
    if samples_analyzed == 0:
        return True
    
    # Compare to maximum possible amplitude (32768 for 16-bit)
    amplitude_ratio = max_amplitude / 32768.0
    
    return amplitude_ratio < noise_threshold


def validate_audio_duration(
    duration_seconds: Optional[float],
    min_duration_seconds: float = 1.0,
) -> ValidationResult:
    """Validate audio duration against minimum requirement.
    
    Args:
        duration_seconds: Duration of audio in seconds (None if unknown)
        min_duration_seconds: Minimum acceptable duration
        
    Returns:
        ValidationResult indicating if duration is acceptable
    """
    if duration_seconds is None:
        # Unknown duration - give benefit of the doubt
        return ValidationResult(
            is_valid=True,
            message="Duration unknown, proceeding with transcription",
        )
    
    if duration_seconds < min_duration_seconds:
        return ValidationResult(
            is_valid=False,
            message=f"Audio too short ({duration_seconds:.1f}s). Minimum is {min_duration_seconds:.1f}s.",
            error_code="ERR_TRANSCRIPTION_002",
        )
    
    return ValidationResult(
        is_valid=True,
        message=f"Duration acceptable ({duration_seconds:.1f}s)",
    )


def validate_audio(
    audio_data: bytes,
    duration_seconds: Optional[float] = None,
    min_size_bytes: int = 100,
    noise_threshold: float = 0.01,
    min_duration_seconds: float = 1.0,
) -> ValidationResult:
    """Comprehensive audio validation.
    
    Checks:
    1. Audio is not empty (has content beyond headers)
    2. Audio is not silent (has amplitude above noise threshold)
    3. Audio meets minimum duration (if duration is known)
    
    Args:
        audio_data: Raw audio bytes
        duration_seconds: Duration in seconds (if known)
        min_size_bytes: Minimum file size to be considered non-empty
        noise_threshold: Maximum amplitude ratio to be considered silent
        min_duration_seconds: Minimum acceptable duration
        
    Returns:
        ValidationResult with combined validation status
    """
    # Check for empty audio
    if is_audio_empty(audio_data, min_size_bytes):
        return ValidationResult(
            is_valid=False,
            message="Audio file is empty or too small to contain meaningful content",
            error_code="ERR_TRANSCRIPTION_002",
        )
    
    # Check duration if available
    if duration_seconds is not None:
        duration_result = validate_audio_duration(duration_seconds, min_duration_seconds)
        if not duration_result.is_valid:
            return duration_result
    
    # Check for silence
    if is_audio_silent(audio_data, noise_threshold):
        return ValidationResult(
            is_valid=False,
            message="Audio appears to be silent or below noise threshold. "
                    "Please check your microphone and try again.",
            error_code="ERR_TRANSCRIPTION_002",
        )
    
    return ValidationResult(
        is_valid=True,
        message="Audio validation passed",
    )
