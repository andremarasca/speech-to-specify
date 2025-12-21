"""Configuration management via environment variables and pydantic-settings."""

from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import Field


class TelegramConfig(BaseSettings):
    """Configuration for Telegram Voice Orchestrator."""

    bot_token: str = Field(
        default="",
        alias="TELEGRAM_BOT_TOKEN",
        description="Telegram bot token from @BotFather",
    )

    allowed_chat_id: int = Field(
        default=0,
        alias="TELEGRAM_ALLOWED_CHAT_ID",
        description="Authorized Telegram chat ID (single user)",
    )

    download_timeout: int = Field(
        default=60,
        alias="TELEGRAM_DOWNLOAD_TIMEOUT",
        description="Timeout for voice file downloads in seconds",
    )

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
        "populate_by_name": True,
    }

    def is_configured(self) -> bool:
        """Check if Telegram is properly configured."""
        return bool(self.bot_token) and self.allowed_chat_id > 0


class WhisperConfig(BaseSettings):
    """Configuration for Whisper speech-to-text."""

    model_name: str = Field(
        default="small.en",
        alias="WHISPER_MODEL",
        description="Whisper model: tiny, base, small, small.en, medium, large",
    )

    device: str = Field(
        default="cuda",
        alias="WHISPER_DEVICE",
        description="Device for inference: cuda or cpu",
    )

    fp16: bool = Field(
        default=True,
        alias="WHISPER_FP16",
        description="Use FP16 precision (recommended for GPU)",
    )

    cache_dir: str | None = Field(
        default=None,
        alias="WHISPER_CACHE_DIR",
        description="Directory for model cache",
    )

    language: str = Field(
        default="pt",
        alias="WHISPER_LANGUAGE",
        description="Language code for transcription (e.g., pt, en, es)",
    )

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
        "populate_by_name": True,
    }


class SessionConfig(BaseSettings):
    """Configuration for session storage."""

    sessions_dir: str = Field(
        default="./sessions",
        alias="SESSIONS_DIR",
        description="Root directory for session storage",
    )

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
        "populate_by_name": True,
    }

    @property
    def sessions_path(self) -> Path:
        """Get sessions directory as Path."""
        return Path(self.sessions_dir)


class SearchConfig(BaseSettings):
    """Configuration for semantic search.
    
    Per data-model.md for 006-semantic-session-search.
    """

    min_similarity_score: float = Field(
        default=0.6,
        alias="SEARCH_MIN_SCORE",
        description="Minimum similarity score threshold for search results",
    )

    max_results: int = Field(
        default=5,
        alias="SEARCH_MAX_RESULTS",
        description="Maximum number of search results to display",
    )

    query_timeout_seconds: int = Field(
        default=60,
        alias="SEARCH_QUERY_TIMEOUT",
        description="Timeout in seconds for search query input",
    )

    # Contract values for Telegram interface (001-telegram-contract-fix)
    search_timeout_seconds: int = Field(
        default=5,
        alias="SEARCH_TIMEOUT",
        description="Timeout for executing semantic search before warning the user (seconds)",
    )

    page_size: int = Field(
        default=5,
        alias="PAGINATION_PAGE_SIZE",
        description="Page size for paginated search results",
    )

    help_fallback_enabled: bool = Field(
        default=True,
        alias="HELP_FALLBACK_ENABLED",
        description="Allow fallback help message when UIService is unavailable",
    )

    orphan_recovery_prompt: bool = Field(
        default=True,
        alias="ORPHAN_RECOVERY_PROMPT",
        description="Enable prompting users to recover orphaned sessions after restart",
    )

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
        "populate_by_name": True,
    }


class Settings(BaseSettings):
    """
    Application configuration loaded from environment variables.

    Priority (highest to lowest):
    1. CLI arguments (handled separately)
    2. Environment variables
    3. .env file
    4. Defaults defined here
    """

    # LLM Provider
    llm_provider: str = Field(
        default="deepseek",
        alias="NARRATE_PROVIDER",
        description="LLM provider to use: deepseek, openai, anthropic, mock",
    )

    # API Keys
    openai_api_key: str | None = Field(
        default=None, alias="OPENAI_API_KEY", description="OpenAI API key"
    )

    anthropic_api_key: str | None = Field(
        default=None, alias="ANTHROPIC_API_KEY", description="Anthropic API key"
    )

    deepseek_api_key: str | None = Field(
        default=None, alias="DEEPSEEK_API_KEY", description="DeepSeek API key"
    )

    # Output
    output_dir: str = Field(
        default="./output",
        alias="NARRATE_OUTPUT_DIR",
        description="Directory for execution outputs",
    )

    # Optional
    verbose: bool = Field(
        default=False, alias="NARRATE_VERBOSE", description="Enable verbose output"
    )

    timeout: int = Field(
        default=120, alias="NARRATE_TIMEOUT", description="Request timeout in seconds"
    )

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
        "populate_by_name": True,
    }

    def get_api_key(self, provider: str | None = None) -> str | None:
        """Get the API key for the specified or configured provider."""
        provider = provider or self.llm_provider

        if provider == "openai":
            return self.openai_api_key
        elif provider == "anthropic":
            return self.anthropic_api_key
        elif provider == "deepseek":
            return self.deepseek_api_key
        elif provider == "mock":
            return "mock-key"

        return None

    def validate_provider_config(self, provider: str | None = None) -> None:
        """
        Validate that the provider has required configuration.

        Raises:
            ConfigError: If required configuration is missing
        """
        from src.lib.exceptions import ConfigError

        provider = provider or self.llm_provider

        if provider == "mock":
            return  # Mock doesn't need API key

        api_key = self.get_api_key(provider)

        if not api_key:
            env_var = f"{provider.upper()}_API_KEY"
            raise ConfigError(
                f"Missing API key for provider '{provider}'. "
                f"Set the {env_var} environment variable."
            )


# Global settings instance (lazy loaded)
_settings: Settings | None = None


def get_settings() -> Settings:
    """Get the global settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reset_settings() -> None:
    """Reset settings (useful for testing)."""
    global _settings
    _settings = None


# Telegram/Whisper/Session config instances (lazy loaded)
_telegram_config: TelegramConfig | None = None
_whisper_config: WhisperConfig | None = None
_session_config: SessionConfig | None = None


def get_telegram_config() -> TelegramConfig:
    """Get the Telegram configuration instance."""
    global _telegram_config
    if _telegram_config is None:
        _telegram_config = TelegramConfig()
    return _telegram_config


def get_whisper_config() -> WhisperConfig:
    """Get the Whisper configuration instance."""
    global _whisper_config
    if _whisper_config is None:
        _whisper_config = WhisperConfig()
    return _whisper_config


def get_session_config() -> SessionConfig:
    """Get the session configuration instance."""
    global _session_config
    if _session_config is None:
        _session_config = SessionConfig()
    return _session_config


# Search config instance (lazy loaded)
_search_config: SearchConfig | None = None


def get_search_config() -> SearchConfig:
    """Get the search configuration instance."""
    global _search_config
    if _search_config is None:
        _search_config = SearchConfig()
    return _search_config


class OracleConfig(BaseSettings):
    """Configuration for contextual oracle feedback.
    
    Per plan.md for 007-contextual-oracle-feedback.
    
    Oracle LLM configuration is INDEPENDENT from NARRATE_PROVIDER.
    This allows using fast models (deepseek-chat, gpt-4o) for oracle feedback
    while NARRATE_PROVIDER uses reasoning models (deepseek-reasoner).
    
    Attributes:
        oracles_dir: Directory containing oracle personality markdown files
        oracle_placeholder: Placeholder string for context injection
        oracle_cache_ttl: Cache TTL in seconds for oracle file scanning
        llm_timeout_seconds: Timeout for LLM API requests
        oracle_provider: LLM provider for oracles (independent from NARRATE_PROVIDER)
        oracle_model: Model to use for oracle responses
    """

    oracles_dir: str = Field(
        default="prompts/oracles",
        alias="ORACLES_DIR",
        description="Directory containing oracle personality markdown files",
    )

    oracle_placeholder: str = Field(
        default="{{CONTEXT}}",
        alias="ORACLE_PLACEHOLDER",
        description="Placeholder string for context injection in oracle prompts",
    )

    oracle_cache_ttl: int = Field(
        default=10,
        alias="ORACLE_CACHE_TTL",
        description="Cache TTL in seconds for oracle file scanning",
    )

    llm_timeout_seconds: int = Field(
        default=30,
        alias="LLM_TIMEOUT_SECONDS",
        description="Timeout for LLM API requests in seconds",
    )

    # Independent Oracle LLM Configuration (FR-014)
    oracle_provider: str = Field(
        default="deepseek",
        alias="ORACLE_PROVIDER",
        description="LLM provider for oracles: deepseek, openai, anthropic, mock",
    )

    oracle_model: str = Field(
        default="deepseek-chat",
        alias="ORACLE_MODEL",
        description="Model to use for oracle responses (should be fast, not reasoning)",
    )

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
        "populate_by_name": True,
    }

    @property
    def oracles_path(self) -> Path:
        """Get oracles directory as Path."""
        return Path(self.oracles_dir)


# Oracle config instance (lazy loaded)
_oracle_config: OracleConfig | None = None


def get_oracle_config() -> OracleConfig:
    """Get the oracle configuration instance."""
    global _oracle_config
    if _oracle_config is None:
        _oracle_config = OracleConfig()
    return _oracle_config


def reset_all_configs() -> None:
    """Reset all configuration instances (useful for testing)."""
    global _settings, _telegram_config, _whisper_config, _session_config, _ui_config, _search_config, _oracle_config
    _settings = None
    _telegram_config = None
    _whisper_config = None
    _session_config = None
    _ui_config = None
    _search_config = None
    _oracle_config = None


class UIConfig(BaseSettings):
    """Configuration for UI presentation layer.
    
    Per Constitution Principle V (Externalized Configuration):
    All Telegram limits, timeouts, and UI parameters must reside
    in configuration files, not hardcoded.
    
    Per plan.md for 005-telegram-ux-overhaul.
    """

    message_limit: int = Field(
        default=4096,
        alias="TELEGRAM_MESSAGE_LIMIT",
        description="Telegram message character limit for pagination",
    )

    progress_interval_seconds: float = Field(
        default=5.0,
        alias="UI_PROGRESS_INTERVAL_SECONDS",
        description="Minimum interval between progress UI updates",
    )

    operation_timeout_seconds: int = Field(
        default=300,
        alias="OPERATION_TIMEOUT_SECONDS",
        description="Timeout for long operations before warning user",
    )

    audio_queue_max_size: int = Field(
        default=10,
        alias="UI_AUDIO_QUEUE_MAX_SIZE",
        description="Maximum audio queue size before rate limit warning",
    )

    confirmation_timeout_seconds: int = Field(
        default=60,
        alias="UI_CONFIRMATION_TIMEOUT_SECONDS",
        description="Timeout for confirmation dialogs before auto-dismiss",
    )

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
        "populate_by_name": True,
    }


# UI config instance (lazy loaded)
_ui_config: UIConfig | None = None


def get_ui_config() -> UIConfig:
    """Get the UI configuration instance."""
    global _ui_config
    if _ui_config is None:
        _ui_config = UIConfig()
    return _ui_config
