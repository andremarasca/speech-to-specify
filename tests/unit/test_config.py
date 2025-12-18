"""Unit tests for configuration management."""

import os
import pytest

from src.lib.config import Settings, get_settings, reset_settings
from src.lib.exceptions import ConfigError


class TestSettings:
    """Tests for the Settings class."""
    
    def setup_method(self):
        """Reset settings before each test."""
        reset_settings()
    
    def test_default_values(self):
        """Test that defaults are applied when no env vars set."""
        settings = Settings()
        
        assert settings.llm_provider == "openai"
        assert settings.output_dir == "./output"
        assert settings.verbose is False
        assert settings.timeout == 120
    
    def test_env_var_override(self, monkeypatch):
        """Test that env vars override defaults."""
        monkeypatch.setenv("NARRATE_PROVIDER", "anthropic")
        monkeypatch.setenv("NARRATE_OUTPUT_DIR", "/custom/output")
        monkeypatch.setenv("NARRATE_VERBOSE", "true")
        
        settings = Settings()
        
        assert settings.llm_provider == "anthropic"
        assert settings.output_dir == "/custom/output"
        assert settings.verbose is True
    
    def test_api_key_retrieval(self, monkeypatch):
        """Test get_api_key method."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-test")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-anthropic-test")
        
        settings = Settings()
        
        assert settings.get_api_key("openai") == "sk-openai-test"
        assert settings.get_api_key("anthropic") == "sk-anthropic-test"
        assert settings.get_api_key("mock") == "mock-key"
        assert settings.get_api_key("unknown") is None
    
    def test_validate_provider_config_success(self, monkeypatch):
        """Test validation passes when API key is present."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        
        settings = Settings()
        
        # Should not raise
        settings.validate_provider_config("openai")
    
    def test_validate_provider_config_missing_key(self, monkeypatch):
        """Test validation fails when API key is missing."""
        # Ensure no API key is set
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        
        settings = Settings()
        
        with pytest.raises(ConfigError) as exc_info:
            settings.validate_provider_config("openai")
        
        assert "OPENAI_API_KEY" in str(exc_info.value)
    
    def test_validate_provider_config_mock_no_key_needed(self):
        """Test that mock provider doesn't need API key."""
        settings = Settings()
        
        # Should not raise
        settings.validate_provider_config("mock")


class TestGetSettings:
    """Tests for the get_settings singleton."""
    
    def setup_method(self):
        """Reset settings before each test."""
        reset_settings()
    
    def test_returns_same_instance(self):
        """Test that get_settings returns the same instance."""
        settings1 = get_settings()
        settings2 = get_settings()
        
        assert settings1 is settings2
    
    def test_reset_creates_new_instance(self):
        """Test that reset_settings allows new instance creation."""
        settings1 = get_settings()
        reset_settings()
        settings2 = get_settings()
        
        assert settings1 is not settings2
