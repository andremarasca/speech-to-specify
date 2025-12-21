"""Unit tests for TTSConfig.

Per T013 [US1] from tasks.md for 008-async-audio-response.

Tests configuration validation and defaults for TTS settings.
"""

import os
from unittest.mock import patch

import pytest

from src.lib.config import TTSConfig, get_tts_config, reset_all_configs


class TestTTSConfigDefaults:
    """Tests for TTSConfig default values."""
    
    def test_default_enabled(self):
        """Should be enabled by default."""
        config = TTSConfig()
        assert config.enabled is True
    
    def test_default_voice(self):
        """Should use pt-BR-AntonioNeural by default."""
        config = TTSConfig()
        assert config.voice == "pt-BR-AntonioNeural"
    
    def test_default_format(self):
        """Should use ogg format by default."""
        config = TTSConfig()
        assert config.format == "ogg"
    
    def test_default_timeout(self):
        """Should have 60s timeout by default."""
        config = TTSConfig()
        assert config.timeout_seconds == 60
    
    def test_default_max_text_length(self):
        """Should have 5000 chars max by default."""
        config = TTSConfig()
        assert config.max_text_length == 5000
    
    def test_default_gc_retention(self):
        """Should retain for 24 hours by default."""
        config = TTSConfig()
        assert config.gc_retention_hours == 24
    
    def test_default_gc_storage(self):
        """Should allow 500MB storage by default."""
        config = TTSConfig()
        assert config.gc_max_storage_mb == 500


class TestTTSConfigEnvironment:
    """Tests for TTSConfig environment variable loading."""
    
    def setup_method(self):
        """Reset configs before each test."""
        reset_all_configs()
    
    def teardown_method(self):
        """Reset configs after each test."""
        reset_all_configs()
    
    @patch.dict(os.environ, {"TTS_ENABLED": "false"})
    def test_load_enabled_from_env(self):
        """Should load enabled from environment."""
        config = TTSConfig()
        assert config.enabled is False
    
    @patch.dict(os.environ, {"TTS_VOICE": "pt-BR-FranciscaNeural"})
    def test_load_voice_from_env(self):
        """Should load voice from environment."""
        config = TTSConfig()
        assert config.voice == "pt-BR-FranciscaNeural"
    
    @patch.dict(os.environ, {"TTS_FORMAT": "mp3"})
    def test_load_format_from_env(self):
        """Should load format from environment."""
        config = TTSConfig()
        assert config.format == "mp3"
    
    @patch.dict(os.environ, {"TTS_TIMEOUT_SECONDS": "30"})
    def test_load_timeout_from_env(self):
        """Should load timeout from environment."""
        config = TTSConfig()
        assert config.timeout_seconds == 30
    
    @patch.dict(os.environ, {"TTS_MAX_TEXT_LENGTH": "10000"})
    def test_load_max_text_length_from_env(self):
        """Should load max text length from environment."""
        config = TTSConfig()
        assert config.max_text_length == 10000
    
    @patch.dict(os.environ, {"TTS_GC_RETENTION_HOURS": "48"})
    def test_load_gc_retention_from_env(self):
        """Should load GC retention from environment."""
        config = TTSConfig()
        assert config.gc_retention_hours == 48
    
    @patch.dict(os.environ, {"TTS_GC_MAX_STORAGE_MB": "1000"})
    def test_load_gc_storage_from_env(self):
        """Should load GC storage limit from environment."""
        config = TTSConfig()
        assert config.gc_max_storage_mb == 1000


class TestGetTTSConfig:
    """Tests for get_tts_config() factory function."""
    
    def setup_method(self):
        """Reset configs before each test."""
        reset_all_configs()
    
    def teardown_method(self):
        """Reset configs after each test."""
        reset_all_configs()
    
    def test_returns_tts_config(self):
        """Should return TTSConfig instance."""
        config = get_tts_config()
        assert isinstance(config, TTSConfig)
    
    def test_singleton_pattern(self):
        """Should return same instance on multiple calls."""
        config1 = get_tts_config()
        config2 = get_tts_config()
        assert config1 is config2
    
    def test_reset_creates_new_instance(self):
        """Should create new instance after reset."""
        config1 = get_tts_config()
        reset_all_configs()
        config2 = get_tts_config()
        assert config1 is not config2


class TestTTSConfigValidation:
    """Tests for TTSConfig value validation."""
    
    def test_valid_format_ogg(self):
        """Should accept ogg format."""
        config = TTSConfig(format="ogg")
        assert config.format == "ogg"
    
    def test_valid_format_mp3(self):
        """Should accept mp3 format."""
        config = TTSConfig(format="mp3")
        assert config.format == "mp3"
    
    def test_valid_format_wav(self):
        """Should accept wav format."""
        config = TTSConfig(format="wav")
        assert config.format == "wav"
    
    def test_positive_timeout(self):
        """Should accept positive timeout."""
        config = TTSConfig(timeout_seconds=120)
        assert config.timeout_seconds == 120
    
    def test_zero_gc_retention_disables(self):
        """Should accept 0 to disable time-based GC."""
        config = TTSConfig(gc_retention_hours=0)
        assert config.gc_retention_hours == 0


class TestTTSConfigIntegration:
    """Integration tests for TTSConfig with real .env loading."""
    
    def setup_method(self):
        """Reset configs before each test."""
        reset_all_configs()
    
    def teardown_method(self):
        """Reset configs after each test."""
        reset_all_configs()
    
    def test_loads_from_dotenv(self):
        """Should load values from .env file if present."""
        # This test just verifies no errors occur during loading
        # Actual values depend on the .env file state
        config = get_tts_config()
        assert config is not None
        assert isinstance(config.enabled, bool)
        assert isinstance(config.voice, str)
        assert isinstance(config.format, str)
        assert isinstance(config.timeout_seconds, int)
