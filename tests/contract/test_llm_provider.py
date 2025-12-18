"""Contract tests for LLM Provider Protocol compliance."""

import pytest

from src.services.llm import get_provider, LLMProvider, LLMError
from src.services.llm.mock import MockProvider


class TestLLMProviderProtocol:
    """Tests verifying Protocol compliance for LLM providers."""
    
    def test_mock_provider_is_llm_provider(self):
        """Test that MockProvider satisfies LLMProvider Protocol."""
        provider = MockProvider()
        
        # runtime_checkable Protocol allows isinstance check
        assert isinstance(provider, LLMProvider)
    
    def test_provider_name_not_empty(self):
        """Test that provider_name returns non-empty string."""
        provider = MockProvider()
        
        name = provider.provider_name
        
        assert isinstance(name, str)
        assert len(name) > 0
    
    def test_provider_name_consistent(self):
        """Test that provider_name is consistent across calls."""
        provider = MockProvider()
        
        name1 = provider.provider_name
        name2 = provider.provider_name
        
        assert name1 == name2
    
    def test_complete_returns_string(self):
        """Test that complete() returns a string."""
        provider = MockProvider()
        
        response = provider.complete("Test prompt")
        
        assert isinstance(response, str)
        assert len(response) > 0
    
    def test_complete_with_empty_prompt_raises(self):
        """Test that complete() raises LLMError for empty prompt."""
        provider = MockProvider()
        
        with pytest.raises(LLMError):
            provider.complete("")
    
    def test_complete_with_whitespace_prompt_raises(self):
        """Test that complete() raises LLMError for whitespace-only prompt."""
        provider = MockProvider()
        
        with pytest.raises(LLMError):
            provider.complete("   ")


class TestMockProviderBehavior:
    """Tests for MockProvider specific behavior."""
    
    def test_deterministic_response(self):
        """Test that same prompt produces same response."""
        provider = MockProvider()
        
        response1 = provider.complete("test prompt")
        response2 = provider.complete("test prompt")
        
        assert response1 == response2
    
    def test_different_prompts_different_responses(self):
        """Test that different prompts produce different responses."""
        provider = MockProvider()
        
        response1 = provider.complete("prompt A")
        response2 = provider.complete("prompt B")
        
        assert response1 != response2
    
    def test_configurable_delay(self):
        """Test that delay can be configured."""
        import time
        
        provider = MockProvider(delay_ms=100)
        
        start = time.time()
        provider.complete("test")
        elapsed = time.time() - start
        
        assert elapsed >= 0.1  # At least 100ms
    
    def test_configurable_failure(self):
        """Test that failures can be configured."""
        provider = MockProvider(fail_on_prompts=["FAIL_TRIGGER"])
        
        # Normal prompt works
        provider.complete("normal prompt")
        
        # Trigger prompt fails
        with pytest.raises(LLMError) as exc_info:
            provider.complete("This has FAIL_TRIGGER in it")
        
        assert "FAIL_TRIGGER" in str(exc_info.value)
    
    def test_step_detection_constitution(self):
        """Test that constitution prompts get constitution-like responses."""
        provider = MockProvider()
        
        response = provider.complete("Generate a constitution for...")
        
        assert "Constitution" in response or "Principles" in response
    
    def test_step_detection_specification(self):
        """Test that specification prompts get specification-like responses."""
        provider = MockProvider()
        
        response = provider.complete("Create a specification based on...")
        
        assert "Specification" in response or "Requirements" in response


class TestProviderRegistry:
    """Tests for the provider registry."""
    
    def test_get_mock_provider(self):
        """Test getting mock provider from registry."""
        provider = get_provider("mock")
        
        assert isinstance(provider, MockProvider)
    
    def test_unknown_provider_raises(self):
        """Test that unknown provider raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            get_provider("nonexistent")
        
        assert "Unknown provider" in str(exc_info.value)
