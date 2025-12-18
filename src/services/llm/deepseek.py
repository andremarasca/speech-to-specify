"""DeepSeek LLM Provider implementation using httpx."""

import os
import httpx

from src.lib.exceptions import LLMError


class DeepSeekProvider:
    """
    DeepSeek LLM provider using the Chat Completions API.

    Implements the LLMProvider Protocol for DeepSeek's models.
    DeepSeek uses an OpenAI-compatible API format.

    Environment Variables:
        DEEPSEEK_API_KEY: Required. Your DeepSeek API key.
        DEEPSEEK_MODEL: Optional. Model to use (default: deepseek-chat).
        DEEPSEEK_BASE_URL: Optional. API base URL (default: https://api.deepseek.com).

    Example:
        >>> provider = DeepSeekProvider()
        >>> response = provider.complete("Hello, world!")
        >>> print(response)
    """

    DEFAULT_BASE_URL = "https://api.deepseek.com"
    DEFAULT_MODEL = "deepseek-chat"
    DEFAULT_TIMEOUT = 120

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        timeout: int | None = None,
        base_url: str | None = None,
    ):
        """
        Initialize DeepSeek provider.

        Args:
            api_key: DeepSeek API key (or from DEEPSEEK_API_KEY env var)
            model: Model to use (default: deepseek-chat)
            timeout: Request timeout in seconds (default: 120)
            base_url: API base URL (default: https://api.deepseek.com)
        """
        self._api_key = api_key or os.environ.get("DEEPSEEK_API_KEY")
        self._model = model or os.environ.get("DEEPSEEK_MODEL", self.DEFAULT_MODEL)
        self._timeout = timeout or self.DEFAULT_TIMEOUT
        self._base_url = base_url or os.environ.get("DEEPSEEK_BASE_URL", self.DEFAULT_BASE_URL)
        self._api_url = f"{self._base_url.rstrip('/')}/chat/completions"

    @property
    def provider_name(self) -> str:
        """Return the provider identifier."""
        return "deepseek"

    def complete(self, prompt: str) -> str:
        """
        Send a prompt to DeepSeek and return the completion.

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
            raise LLMError(provider=self.provider_name, message="DEEPSEEK_API_KEY not set")

        # Build request
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self._model,
            "messages": [{"role": "user", "content": prompt}],
        }

        try:
            with httpx.Client(timeout=self._timeout) as client:
                response = client.post(
                    self._api_url,
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

                if not data.get("choices"):
                    raise LLMError(provider=self.provider_name, message="No choices in response")

                content = data["choices"][0]["message"]["content"]

                if not content:
                    raise LLMError(provider=self.provider_name, message="Empty response content")

                return content

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
