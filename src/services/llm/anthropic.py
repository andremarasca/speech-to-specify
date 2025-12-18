"""Anthropic LLM Provider implementation using httpx."""

import os
import httpx

from src.lib.exceptions import LLMError


class AnthropicProvider:
    """
    Anthropic LLM provider using the Messages API.

    Implements the LLMProvider Protocol for Anthropic's Claude models.

    Environment Variables:
        ANTHROPIC_API_KEY: Required. Your Anthropic API key.
        ANTHROPIC_MODEL: Optional. Model to use (default: claude-3-sonnet-20240229).

    Example:
        >>> provider = AnthropicProvider()
        >>> response = provider.complete("Hello, world!")
        >>> print(response)
    """

    ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
    DEFAULT_MODEL = "claude-3-sonnet-20240229"
    DEFAULT_TIMEOUT = 120
    DEFAULT_MAX_TOKENS = 4096
    API_VERSION = "2023-06-01"

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        timeout: int | None = None,
        max_tokens: int | None = None,
    ):
        """
        Initialize Anthropic provider.

        Args:
            api_key: Anthropic API key (or from ANTHROPIC_API_KEY env var)
            model: Model to use (default: claude-3-sonnet-20240229)
            timeout: Request timeout in seconds (default: 120)
            max_tokens: Maximum tokens in response (default: 4096)
        """
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self._model = model or os.environ.get("ANTHROPIC_MODEL", self.DEFAULT_MODEL)
        self._timeout = timeout or self.DEFAULT_TIMEOUT
        self._max_tokens = max_tokens or self.DEFAULT_MAX_TOKENS

    @property
    def provider_name(self) -> str:
        """Return the provider identifier."""
        return "anthropic"

    def complete(self, prompt: str) -> str:
        """
        Send a prompt to Anthropic and return the completion.

        Args:
            prompt: The text prompt to send

        Returns:
            str: The completion text

        Raises:
            LLMError: On any failure
        """
        # Validate prompt
        if not prompt or not prompt.strip():
            raise LLMError(provider=self.provider_name, message="Prompt cannot be empty")

        # Validate API key
        if not self._api_key:
            raise LLMError(provider=self.provider_name, message="ANTHROPIC_API_KEY not set")

        # Build request
        headers = {
            "x-api-key": self._api_key,
            "anthropic-version": self.API_VERSION,
            "Content-Type": "application/json",
        }

        payload = {
            "model": self._model,
            "max_tokens": self._max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }

        try:
            with httpx.Client(timeout=self._timeout) as client:
                response = client.post(
                    self.ANTHROPIC_API_URL,
                    headers=headers,
                    json=payload,
                )

                # Check for HTTP errors
                if response.status_code != 200:
                    error_data = response.json() if response.text else {}
                    error_message = error_data.get("error", {}).get(
                        "message", f"HTTP {response.status_code}"
                    )
                    raise LLMError(
                        provider=self.provider_name, message=f"API error: {error_message}"
                    )

                # Parse response
                data = response.json()

                if not data.get("content"):
                    raise LLMError(provider=self.provider_name, message="No content in response")

                # Anthropic returns content as an array of blocks
                content_blocks = data["content"]
                text_content = ""

                for block in content_blocks:
                    if block.get("type") == "text":
                        text_content += block.get("text", "")

                if not text_content:
                    raise LLMError(provider=self.provider_name, message="Empty response content")

                return text_content

        except httpx.TimeoutException as e:
            raise LLMError(
                provider=self.provider_name,
                message=f"Request timed out after {self._timeout}s",
                original_error=e,
            )
        except httpx.RequestError as e:
            raise LLMError(
                provider=self.provider_name,
                message=f"Network error: {str(e)}",
                original_error=e,
            )
        except LLMError:
            # Re-raise our own errors
            raise
        except Exception as e:
            raise LLMError(
                provider=self.provider_name,
                message=f"Unexpected error: {str(e)}",
                original_error=e,
            )
