"""Exception hierarchy for the narrative pipeline.

All custom exceptions inherit from NarrativeError to enable
selective catching at different levels.

Hierarchy:
    NarrativeError (base)
    ├── ConfigError - Configuration issues (missing env vars)
    ├── ValidationError - Input/artifact validation failures
    ├── LLMError - LLM provider communication errors
    └── PersistenceError - Storage read/write failures
"""


class NarrativeError(Exception):
    """
    Base exception for all narrative pipeline errors.

    Catching this will catch all custom exceptions from this module.
    """

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class ConfigError(NarrativeError):
    """
    Configuration error.

    Raised when required configuration is missing or invalid.
    Examples: missing API key, invalid provider name.

    CLI Exit Code: 2
    """

    pass


class ValidationError(NarrativeError):
    """
    Input or artifact validation error.

    Raised when input data fails validation rules.
    Examples: empty content, invalid format, missing required fields.

    CLI Exit Code: 3
    """

    def __init__(self, message: str, field: str | None = None):
        self.field = field
        super().__init__(message)


class LLMError(NarrativeError):
    """
    LLM provider communication error.

    Raised when an LLM provider fails to return a valid response.
    Examples: network error, rate limit, authentication failure, timeout.

    CLI Exit Code: 4

    Attributes:
        provider: Name of the provider that failed
        original_error: Original exception if wrapping
    """

    def __init__(
        self, message: str, provider: str = "unknown", original_error: Exception | None = None
    ):
        self.provider = provider
        self.original_error = original_error
        full_message = f"[{provider}] {message}"
        super().__init__(full_message)


class PersistenceError(NarrativeError):
    """
    Storage read/write error.

    Raised when persistence operations fail.
    Examples: file not found, permission denied, disk full.

    CLI Exit Code: 5

    Attributes:
        path: Path that caused the error
        operation: Operation that failed (read, write, delete)
    """

    def __init__(self, message: str, path: str | None = None, operation: str | None = None):
        self.path = path
        self.operation = operation
        super().__init__(message)


class AudioPersistenceError(PersistenceError):
    """
    Critical audio persistence error.

    Raised when audio data cannot be saved to disk.
    This is the only critical error in audio handling -
    zero data loss requires audio to be persisted.

    CLI Exit Code: 5 (inherits from PersistenceError)

    Added for: 003-auto-session-audio feature
    """

    def __init__(self, message: str, path: str | None = None):
        super().__init__(message, path=path, operation="write")
