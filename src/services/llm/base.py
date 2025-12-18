"""LLM Provider Protocol and base error class."""

from typing import Protocol, runtime_checkable

from src.lib.exceptions import LLMError


@runtime_checkable
class LLMProvider(Protocol):
    """
    Contract for LLM provider implementations.

    All providers MUST implement this interface to be used by the orchestrator.
    The interface is intentionally minimal to ensure maximum compatibility.

    Example:
        >>> provider = get_provider("openai")
        >>> response = provider.complete("Transform this text...")
        >>> print(f"Response from {provider.provider_name}: {response[:100]}...")
    """

    @property
    def provider_name(self) -> str:
        """
        Return the canonical name of this provider.

        Returns:
            str: Provider identifier (e.g., "openai", "anthropic", "mock")

        Contract:
            - MUST return a non-empty string
            - MUST be consistent across calls (same instance, same value)
            - SHOULD be lowercase, alphanumeric with hyphens
        """
        ...

    def complete(self, prompt: str) -> str:
        """
        Send a prompt and return the completion text.

        Args:
            prompt: The text prompt to send to the LLM.
                   MUST be non-empty.

        Returns:
            str: The completion text from the LLM.
                 Will never be None (raise exception instead).

        Raises:
            LLMError: If the provider fails to return a valid response.
                     This includes: network errors, rate limits, invalid responses,
                     authentication errors, timeout.

        Contract:
            - MUST raise LLMError on any failure (never return None or empty)
            - MUST NOT modify the prompt
            - MUST NOT have side effects beyond the API call
            - MAY take significant time (seconds to minutes)
            - SHOULD respect provider-specific timeout settings
        """
        ...


__all__ = ["LLMProvider", "LLMError"]
