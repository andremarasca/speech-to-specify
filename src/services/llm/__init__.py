"""LLM provider abstraction layer."""

from src.services.llm.base import LLMProvider, LLMError
from src.services.llm.mock import MockProvider
from src.services.llm.openai import OpenAIProvider
from src.services.llm.anthropic import AnthropicProvider

_PROVIDERS: dict[str, type] = {
    "mock": MockProvider,
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
}


def get_provider(name: str, **kwargs) -> LLMProvider:
    """
    Get an LLM provider instance by name.

    Args:
        name: Provider identifier (e.g., "openai", "anthropic", "mock")
        **kwargs: Provider-specific configuration

    Returns:
        LLMProvider instance

    Raises:
        ValueError: If provider name is not registered
    """
    if name not in _PROVIDERS:
        available = ", ".join(_PROVIDERS.keys())
        raise ValueError(f"Unknown provider '{name}'. Available: {available}")

    return _PROVIDERS[name](**kwargs)


def register_provider(name: str, provider_class: type) -> None:
    """Register a new provider class."""
    _PROVIDERS[name] = provider_class


__all__ = ["LLMProvider", "LLMError", "get_provider", "register_provider"]
