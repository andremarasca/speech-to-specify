"""Oracle client for LLM API requests.

Per contracts/telegram-callbacks.md for 007-contextual-oracle-feedback.

This module handles LLM API requests with timeout handling and
error recovery for oracle feedback.
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import Optional

from src.lib.config import get_settings, get_oracle_config
from src.lib.exceptions import LLMError

logger = logging.getLogger(__name__)


@dataclass
class OracleResponse:
    """
    Result of an oracle LLM request.
    
    Attributes:
        success: Whether the request succeeded
        content: Response content (if successful)
        error_message: Error description (if failed)
        timed_out: Whether the request timed out
    """
    
    success: bool
    content: Optional[str] = None
    error_message: Optional[str] = None
    timed_out: bool = False


class OracleClient:
    """
    LLM client for oracle feedback requests.
    
    Per contracts/telegram-callbacks.md.
    
    Handles:
        - LLM API requests with configurable timeout
        - Error handling and recovery
        - Provider abstraction
    """
    
    def __init__(self, timeout_seconds: Optional[int] = None):
        """
        Initialize oracle client.
        
        Args:
            timeout_seconds: Override default timeout (from config)
        """
        oracle_config = get_oracle_config()
        self.timeout_seconds = timeout_seconds or oracle_config.llm_timeout_seconds
        self._settings = get_settings()
    
    async def request_feedback(self, prompt: str) -> OracleResponse:
        """
        Send prompt to LLM and return response.
        
        Per BC-TC-006, BC-TC-007, BC-TC-008:
            - Returns structured response with success/error state
            - Handles timeout with specific flag
            - Captures error messages for user display
        
        Args:
            prompt: Complete prompt with context injected
            
        Returns:
            OracleResponse with content or error details
        """
        try:
            # Get the configured LLM provider
            provider = self._get_provider()
            
            # Run synchronous provider.complete() in thread pool with timeout
            # This allows async timeout handling while using sync LLM providers
            try:
                content = await asyncio.wait_for(
                    asyncio.to_thread(provider.complete, prompt),
                    timeout=self.timeout_seconds,
                )
                
                if not content:
                    return OracleResponse(
                        success=False,
                        error_message="LLM retornou resposta vazia",
                    )
                
                return OracleResponse(
                    success=True,
                    content=content,
                )
                
            except asyncio.TimeoutError:
                logger.warning(
                    f"Oracle request timed out after {self.timeout_seconds}s"
                )
                return OracleResponse(
                    success=False,
                    error_message=f"Tempo esgotado após {self.timeout_seconds} segundos",
                    timed_out=True,
                )
                
        except LLMError as e:
            logger.error(f"LLM error during oracle request: {e}")
            return OracleResponse(
                success=False,
                error_message=str(e),
            )
        except Exception as e:
            logger.exception(f"Unexpected error during oracle request: {e}")
            return OracleResponse(
                success=False,
                error_message=f"Erro inesperado: {type(e).__name__}",
            )
    
    def _get_provider(self):
        """
        Get the configured LLM provider instance.
        
        Returns:
            LLMProvider implementation
        """
        provider_name = self._settings.llm_provider
        
        if provider_name == "openai":
            from src.services.llm.openai import OpenAIProvider
            return OpenAIProvider(timeout=self.timeout_seconds)
        elif provider_name == "anthropic":
            from src.services.llm.anthropic import AnthropicProvider
            return AnthropicProvider(timeout=self.timeout_seconds)
        elif provider_name == "deepseek":
            from src.services.llm.deepseek import DeepSeekProvider
            return DeepSeekProvider(timeout=self.timeout_seconds)
        elif provider_name == "mock":
            from src.services.llm.mock import MockProvider
            return MockProvider()
        else:
            raise LLMError(
                provider=provider_name,
                message=f"Unknown LLM provider: {provider_name}",
            )
