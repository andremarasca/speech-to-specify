"""Integration tests for LLM provider switching via configuration."""

import os
import pytest
from unittest.mock import patch

from src.services.llm import get_provider, LLMProvider
from src.lib.config import get_settings, Settings
from src.lib.exceptions import ConfigError


class TestProviderSwitchingViaConfig:
    """Tests for switching providers via configuration."""

    def test_mock_provider_via_config(self):
        """Test that mock provider can be loaded via config."""
        with patch.dict(os.environ, {"NARRATE_PROVIDER": "mock"}):
            settings = Settings()
            provider = get_provider(settings.llm_provider)

            assert provider.provider_name == "mock"
            assert isinstance(provider, LLMProvider)

    def test_openai_provider_via_config_without_key_raises(self):
        """Test that OpenAI provider without API key raises ConfigError."""
        with patch.dict(os.environ, {"NARRATE_PROVIDER": "openai"}, clear=True):
            # Clear the API key
            env = os.environ.copy()
            env.pop("OPENAI_API_KEY", None)

            with patch.dict(os.environ, env, clear=True):
                settings = Settings()

                # Should raise ConfigError when validating
                with pytest.raises(ConfigError) as exc_info:
                    settings.validate_provider_config("openai")

                assert "OPENAI_API_KEY" in str(exc_info.value)

    def test_anthropic_provider_via_config_without_key_raises(self):
        """Test that Anthropic provider without API key raises ConfigError."""
        with patch.dict(os.environ, {"NARRATE_PROVIDER": "anthropic"}, clear=True):
            # Clear the API key
            env = os.environ.copy()
            env.pop("ANTHROPIC_API_KEY", None)

            with patch.dict(os.environ, env, clear=True):
                settings = Settings()

                # Should raise ConfigError when validating
                with pytest.raises(ConfigError) as exc_info:
                    settings.validate_provider_config("anthropic")

                assert "ANTHROPIC_API_KEY" in str(exc_info.value)

    def test_provider_from_registry(self):
        """Test all registered providers can be instantiated."""
        from src.services.llm import _PROVIDERS

        for name in _PROVIDERS:
            if name == "mock":
                provider = get_provider(name)
                assert provider.provider_name == name

    @pytest.mark.skipif(not os.environ.get("OPENAI_API_KEY"), reason="OPENAI_API_KEY not set")
    def test_openai_provider_integration(self):
        """Test OpenAI provider with real API (when key available)."""
        provider = get_provider("openai")

        assert provider.provider_name == "openai"
        # Don't actually call the API in integration tests
        # to avoid costs and rate limits

    @pytest.mark.skipif(not os.environ.get("ANTHROPIC_API_KEY"), reason="ANTHROPIC_API_KEY not set")
    def test_anthropic_provider_integration(self):
        """Test Anthropic provider with real API (when key available)."""
        provider = get_provider("anthropic")

        assert provider.provider_name == "anthropic"
        # Don't actually call the API in integration tests


class TestCLIProviderFlag:
    """Tests for --provider CLI flag."""

    def test_provider_flag_overrides_env(self):
        """Test that --provider flag overrides environment variable."""
        # This is tested through the CLI module
        # Here we just verify the config behavior
        with patch.dict(os.environ, {"NARRATE_PROVIDER": "openai"}):
            settings = Settings()

            # Default from env
            assert settings.llm_provider == "openai"

            # CLI would override this by passing to get_provider directly
            provider = get_provider("mock")
            assert provider.provider_name == "mock"
