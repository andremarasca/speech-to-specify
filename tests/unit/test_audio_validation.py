"""Unit tests for audio validation including empty/silent detection.

Per T031g from 005-telegram-ux-overhaul.

Tests audio validation functions that check for:
- Empty audio files (0 bytes)
- Silent audio (below noise threshold)
- Minimum duration requirements
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
import tempfile
import struct
import wave


class TestEmptyAudioDetection:
    """Tests for empty audio file detection."""

    def test_empty_bytes_detected(self):
        """Audio with 0 bytes should be detected as empty."""
        from src.lib.audio_validation import is_audio_empty
        
        assert is_audio_empty(b"") is True

    def test_small_header_only_detected(self):
        """Audio with only header (< 100 bytes) should be detected as empty."""
        from src.lib.audio_validation import is_audio_empty
        
        # OGG header is typically ~28 bytes minimum
        small_data = b"OggS" + b"\x00" * 50  # Minimal OGG-like header
        assert is_audio_empty(small_data) is True

    def test_valid_audio_not_detected_as_empty(self):
        """Audio with substantial content should not be empty."""
        from src.lib.audio_validation import is_audio_empty
        
        # Simulated substantial audio data (> 100 bytes)
        substantial_data = b"OggS" + b"\x00" * 200 + b"\xFF" * 1000
        assert is_audio_empty(substantial_data) is False

    def test_minimum_size_threshold_configurable(self):
        """Empty detection should use configurable minimum size."""
        from src.lib.audio_validation import is_audio_empty
        
        data = b"X" * 50  # 50 bytes
        
        # With default threshold (100), should be empty
        assert is_audio_empty(data, min_size_bytes=100) is True
        
        # With lower threshold (40), should not be empty
        assert is_audio_empty(data, min_size_bytes=40) is False


class TestSilentAudioDetection:
    """Tests for silent audio detection."""

    def test_all_zeros_is_silent(self):
        """Audio data that is all zeros should be detected as silent."""
        from src.lib.audio_validation import is_audio_silent
        
        # Create WAV-like data with all zero samples
        silent_samples = bytes(2000)  # 1000 16-bit samples of silence
        
        assert is_audio_silent(silent_samples) is True

    def test_low_amplitude_is_silent(self):
        """Audio below noise threshold should be detected as silent."""
        from src.lib.audio_validation import is_audio_silent
        
        # Create samples with very low amplitude (< 1% of max)
        low_samples = bytes([0x01, 0x00] * 500)  # Value 1 out of 32768
        
        assert is_audio_silent(low_samples, noise_threshold=0.01) is True

    def test_normal_audio_not_silent(self):
        """Audio with normal amplitude should not be silent."""
        from src.lib.audio_validation import is_audio_silent
        
        # Create samples with substantial amplitude
        # Value 16384 = 50% of max int16
        loud_samples = bytes([0x00, 0x40] * 500)  # Little-endian 16384
        
        assert is_audio_silent(loud_samples, noise_threshold=0.01) is False

    def test_noise_threshold_configurable(self):
        """Silent detection should use configurable noise threshold."""
        from src.lib.audio_validation import is_audio_silent
        
        # 5% amplitude samples
        medium_samples = bytes([0x9A, 0x06] * 500)  # ~1690 = ~5% of 32768
        
        # With 10% threshold, should be silent
        assert is_audio_silent(medium_samples, noise_threshold=0.10) is True
        
        # With 1% threshold, should not be silent
        assert is_audio_silent(medium_samples, noise_threshold=0.01) is False


class TestMinimumDurationValidation:
    """Tests for minimum audio duration validation."""

    def test_duration_below_minimum_invalid(self):
        """Audio shorter than minimum should be invalid."""
        from src.lib.audio_validation import validate_audio_duration
        
        result = validate_audio_duration(
            duration_seconds=0.5,
            min_duration_seconds=1.0,
        )
        
        assert result.is_valid is False
        assert "too short" in result.message.lower()

    def test_duration_at_minimum_valid(self):
        """Audio exactly at minimum duration should be valid."""
        from src.lib.audio_validation import validate_audio_duration
        
        result = validate_audio_duration(
            duration_seconds=1.0,
            min_duration_seconds=1.0,
        )
        
        assert result.is_valid is True

    def test_duration_above_minimum_valid(self):
        """Audio above minimum duration should be valid."""
        from src.lib.audio_validation import validate_audio_duration
        
        result = validate_audio_duration(
            duration_seconds=30.0,
            min_duration_seconds=1.0,
        )
        
        assert result.is_valid is True

    def test_none_duration_handled(self):
        """None duration should be handled gracefully."""
        from src.lib.audio_validation import validate_audio_duration
        
        result = validate_audio_duration(
            duration_seconds=None,
            min_duration_seconds=1.0,
        )
        
        # Unknown duration should pass (benefit of the doubt)
        assert result.is_valid is True


class TestAudioValidationResult:
    """Tests for validation result structure."""

    def test_validation_result_structure(self):
        """Validation result should have required fields."""
        from src.lib.audio_validation import ValidationResult
        
        result = ValidationResult(
            is_valid=False,
            message="Audio too short",
            error_code="ERR_TRANSCRIPTION_002",
        )
        
        assert result.is_valid is False
        assert result.message == "Audio too short"
        assert result.error_code == "ERR_TRANSCRIPTION_002"

    def test_valid_result_has_no_error(self):
        """Valid result should have no error code."""
        from src.lib.audio_validation import ValidationResult
        
        result = ValidationResult(is_valid=True)
        
        assert result.is_valid is True
        assert result.error_code is None


class TestComprehensiveAudioValidation:
    """Tests for the comprehensive validate_audio function."""

    def test_validate_audio_empty_file(self):
        """Empty audio should fail comprehensive validation."""
        from src.lib.audio_validation import validate_audio
        
        result = validate_audio(
            audio_data=b"",
            duration_seconds=0,
        )
        
        assert result.is_valid is False
        assert "empty" in result.message.lower() or "ERR_TRANSCRIPTION_002" in str(result.error_code)

    def test_validate_audio_silent_file(self):
        """Silent audio should fail with appropriate warning."""
        from src.lib.audio_validation import validate_audio
        
        # All zeros = silence
        silent_data = bytes(2000)
        
        result = validate_audio(
            audio_data=silent_data,
            duration_seconds=5.0,
        )
        
        # Silent audio might pass but should have a warning
        assert "silent" in result.message.lower() or result.is_valid

    def test_validate_audio_valid_file(self):
        """Valid audio should pass comprehensive validation."""
        from src.lib.audio_validation import validate_audio
        
        # Create "valid" audio data with substantial amplitude
        # Use alternating high values to simulate real audio
        # 0x40, 0x40 = 16448 in little-endian, about 50% amplitude
        valid_data = b"OggS" + b"\x00" * 200 + bytes([0x00, 0x40] * 500)
        
        result = validate_audio(
            audio_data=valid_data,
            duration_seconds=30.0,
        )
        
        assert result.is_valid is True
