"""Unit tests for OracleClient.

Per tasks.md T043 for 007-contextual-oracle-feedback.

Tests error handling, timeout behavior, and response handling.

Note: OracleClient uses ORACLE_PROVIDER/ORACLE_MODEL configuration
which is independent from NARRATE_PROVIDER.
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock

from src.services.llm.oracle_client import OracleClient, OracleResponse
from src.lib.exceptions import LLMError


class TestOracleClientResponse:
    """Tests for OracleResponse dataclass."""
    
    def test_success_response(self):
        """Success response has content and no error."""
        response = OracleResponse(
            success=True,
            content="LLM response content",
        )
        
        assert response.success
        assert response.content == "LLM response content"
        assert response.error_message is None
        assert not response.timed_out
    
    def test_error_response(self):
        """Error response has message and no content."""
        response = OracleResponse(
            success=False,
            error_message="Something went wrong",
        )
        
        assert not response.success
        assert response.content is None
        assert response.error_message == "Something went wrong"
        assert not response.timed_out
    
    def test_timeout_response(self):
        """Timeout response has timed_out flag."""
        response = OracleResponse(
            success=False,
            error_message="Timed out",
            timed_out=True,
        )
        
        assert not response.success
        assert response.timed_out


class TestOracleClientInit:
    """Tests for OracleClient initialization."""
    
    @patch('src.services.llm.oracle_client.get_oracle_config')
    def test_uses_config_timeout(self, mock_config):
        """Client uses timeout from config by default."""
        mock_config.return_value = Mock(
            llm_timeout_seconds=45,
            oracle_provider="mock",
            oracle_model="test-model",
        )
        
        client = OracleClient()
        
        assert client.timeout_seconds == 45
    
    @patch('src.services.llm.oracle_client.get_oracle_config')
    def test_override_timeout(self, mock_config):
        """Client accepts custom timeout override."""
        mock_config.return_value = Mock(
            llm_timeout_seconds=30,
            oracle_provider="mock",
            oracle_model="test-model",
        )
        
        client = OracleClient(timeout_seconds=60)
        
        assert client.timeout_seconds == 60


class TestOracleClientRequestFeedback:
    """Tests for OracleClient.request_feedback() method."""
    
    @pytest.mark.asyncio
    @patch('src.services.llm.oracle_client.get_oracle_config')
    async def test_successful_request(self, mock_config):
        """Successful LLM request returns content."""
        mock_config.return_value = Mock(
            llm_timeout_seconds=30,
            oracle_provider="mock",
            oracle_model="test-model",
        )
        
        client = OracleClient()
        
        # Mock the provider
        with patch.object(client, '_get_provider') as mock_provider:
            provider_instance = Mock()
            provider_instance.complete.return_value = "LLM generated response"
            mock_provider.return_value = provider_instance
            
            response = await client.request_feedback("Test prompt")
        
        assert response.success
        assert response.content == "LLM generated response"
        assert not response.timed_out
    
    @pytest.mark.asyncio
    @patch('src.services.llm.oracle_client.get_oracle_config')
    async def test_empty_response(self, mock_config):
        """Empty LLM response returns error."""
        mock_config.return_value = Mock(
            llm_timeout_seconds=30,
            oracle_provider="mock",
            oracle_model="test-model",
        )
        
        client = OracleClient()
        
        with patch.object(client, '_get_provider') as mock_provider:
            provider_instance = Mock()
            provider_instance.complete.return_value = ""
            mock_provider.return_value = provider_instance
            
            response = await client.request_feedback("Test prompt")
        
        assert not response.success
        assert "vazia" in response.error_message.lower()
    
    @pytest.mark.asyncio
    @patch('src.services.llm.oracle_client.get_oracle_config')
    async def test_timeout_handling(self, mock_config):
        """Timeout returns timed_out flag."""
        mock_config.return_value = Mock(
            llm_timeout_seconds=1,  # Short timeout
            oracle_provider="mock",
            oracle_model="test-model",
        )
        
        client = OracleClient()
        
        with patch.object(client, '_get_provider') as mock_provider:
            # Simulate slow provider
            async def slow_complete(prompt):
                await asyncio.sleep(5)  # Sleep longer than timeout
                return "Response"
            
            provider_instance = Mock()
            # Make complete block synchronously
            def blocking_complete(prompt):
                import time
                time.sleep(3)  # Sleep longer than timeout
                return "Response"
            provider_instance.complete.side_effect = blocking_complete
            mock_provider.return_value = provider_instance
            
            response = await client.request_feedback("Test prompt")
        
        assert not response.success
        assert response.timed_out
        assert "tempo" in response.error_message.lower() or "segundos" in response.error_message.lower()
    
    @pytest.mark.asyncio
    @patch('src.services.llm.oracle_client.get_oracle_config')
    async def test_llm_error_handling(self, mock_config):
        """LLMError returns structured error response."""
        mock_config.return_value = Mock(
            llm_timeout_seconds=30,
            oracle_provider="mock",
            oracle_model="test-model",
        )
        
        client = OracleClient()
        
        with patch.object(client, '_get_provider') as mock_provider:
            provider_instance = Mock()
            provider_instance.complete.side_effect = LLMError(
                provider="test",
                message="API rate limit exceeded",
            )
            mock_provider.return_value = provider_instance
            
            response = await client.request_feedback("Test prompt")
        
        assert not response.success
        assert not response.timed_out
        assert "rate limit" in response.error_message.lower()
    
    @pytest.mark.asyncio
    @patch('src.services.llm.oracle_client.get_oracle_config')
    async def test_unexpected_error_handling(self, mock_config):
        """Unexpected exceptions return generic error."""
        mock_config.return_value = Mock(
            llm_timeout_seconds=30,
            oracle_provider="mock",
            oracle_model="test-model",
        )
        
        client = OracleClient()
        
        with patch.object(client, '_get_provider') as mock_provider:
            provider_instance = Mock()
            provider_instance.complete.side_effect = RuntimeError("Something unexpected")
            mock_provider.return_value = provider_instance
            
            response = await client.request_feedback("Test prompt")
        
        assert not response.success
        assert not response.timed_out
        assert "RuntimeError" in response.error_message or "inesperado" in response.error_message.lower()


class TestOracleClientGetProvider:
    """Tests for provider instantiation."""
    
    @patch('src.services.llm.oracle_client.get_oracle_config')
    def test_unknown_provider_raises_error(self, mock_config):
        """Unknown provider name raises LLMError."""
        mock_config.return_value = Mock(
            llm_timeout_seconds=30,
            oracle_provider="unknown_provider",
            oracle_model="test-model",
        )
        
        client = OracleClient()
        
        with pytest.raises(LLMError):
            client._get_provider()
