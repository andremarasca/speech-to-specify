# LLM Provider Contract

**Interface**: `LLMProvider`  
**Purpose**: Abstração para provedores de LLM intercambiáveis

## Protocol Definition

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class LLMProvider(Protocol):
    """
    Contract for LLM provider implementations.
    
    All providers MUST implement this interface to be used by the orchestrator.
    The interface is intentionally minimal to ensure maximum compatibility.
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
```

## Error Contract

```python
class LLMError(Exception):
    """
    Base exception for LLM provider errors.
    
    Attributes:
        provider: Name of the provider that failed
        message: Human-readable error description
        original_error: Original exception if wrapping (optional)
    """
    
    def __init__(
        self, 
        provider: str, 
        message: str, 
        original_error: Exception | None = None
    ):
        self.provider = provider
        self.message = message
        self.original_error = original_error
        super().__init__(f"[{provider}] {message}")
```

## Implementation Requirements

### OpenAI Adapter

| Requirement | Implementation |
|-------------|----------------|
| API Version | Chat Completions API (v1) |
| Model | Configurable, default: `gpt-4` |
| Authentication | `OPENAI_API_KEY` env var |
| Timeout | 120 seconds |
| Retries | None (fail fast for auditability) |

### Anthropic Adapter

| Requirement | Implementation |
|-------------|----------------|
| API Version | Messages API |
| Model | Configurable, default: `claude-3-sonnet-20240229` |
| Authentication | `ANTHROPIC_API_KEY` env var |
| Timeout | 120 seconds |
| Retries | None (fail fast for auditability) |

### Mock Adapter (Testing)

| Requirement | Implementation |
|-------------|----------------|
| Behavior | Return deterministic response based on prompt hash |
| Latency | Configurable delay (default: 0ms) |
| Failures | Can be configured to fail on specific prompts |

## Usage Example

```python
from src.services.llm import get_provider
from src.services.llm.base import LLMError

# Get provider from configuration
provider = get_provider("openai")

try:
    response = provider.complete("Transform this text into a structured narrative...")
    print(f"Response from {provider.provider_name}: {response[:100]}...")
except LLMError as e:
    print(f"Provider {e.provider} failed: {e.message}")
```

## Validation

Contract tests MUST verify:

1. `provider_name` returns non-empty string
2. `provider_name` is consistent across multiple calls
3. `complete()` with valid prompt returns non-empty string
4. `complete()` with empty prompt raises appropriate error
5. Provider is `runtime_checkable` (isinstance works)

## Extensibility

To add a new provider:

1. Create new file in `src/services/llm/{provider_name}.py`
2. Implement class that satisfies `LLMProvider` protocol
3. Register in `src/services/llm/__init__.py` provider registry
4. Add contract tests in `tests/contract/test_llm_provider.py`
5. Document required environment variables

No changes to orchestrator or core logic required.
