# Contract: ErrorPresentationLayer

**Feature**: 005-telegram-ux-overhaul  
**Module**: `src/services/presentation/error_handler.py`  
**Date**: 2025-12-19

## Purpose

ErrorPresentationLayer captures exceptions from business logic and transforms them into user-friendly messages with actionable recovery options. It enforces Constitution Restriction #2 (no implementation exposure) while maintaining debuggability via structured logging.

## Interface

```python
from abc import ABC, abstractmethod
from typing import Type
from src.models.ui_state import UserFacingError, ErrorSeverity

class ErrorPresentationProtocol(ABC):
    """Protocol for humanized error presentation."""
    
    @abstractmethod
    def translate_exception(
        self, 
        exception: Exception,
        context: dict | None = None
    ) -> UserFacingError:
        """
        Transform exception into user-facing error.
        
        Args:
            exception: Caught exception from business logic
            context: Optional context (session_id, operation, etc.)
            
        Returns:
            UserFacingError with humanized message and recovery actions
            
        Side Effects:
            Logs full exception details at ERROR level with correlation ID
        """
        ...
    
    @abstractmethod
    def get_error_by_code(self, error_code: str) -> UserFacingError:
        """
        Retrieve error from catalog by code.
        
        Args:
            error_code: Error code (e.g., "ERR_STORAGE_001")
            
        Returns:
            Configured UserFacingError or DEFAULT_ERROR if not found
        """
        ...
    
    @abstractmethod
    def register_exception_mapping(
        self, 
        exception_type: Type[Exception],
        error_code: str
    ) -> None:
        """
        Register mapping from exception type to error code.
        
        Args:
            exception_type: Exception class to map
            error_code: Target error code
        """
        ...
    
    @abstractmethod
    def format_for_telegram(
        self, 
        error: UserFacingError,
        simplified: bool = False
    ) -> tuple[str, "InlineKeyboardMarkup"]:
        """
        Format error for Telegram message.
        
        Args:
            error: UserFacingError to format
            simplified: Whether to use simplified UI mode
            
        Returns:
            Tuple of (message_text, keyboard_markup)
        """
        ...
```

## Error Catalog Structure

Errors are defined in configuration (not hardcoded):

```python
# src/lib/error_catalog.py (loaded from config)

ERROR_CATALOG: dict[str, UserFacingError] = {
    # Storage errors
    "ERR_STORAGE_001": UserFacingError(
        error_code="ERR_STORAGE_001",
        message="Não foi possível salvar o áudio no momento.",
        suggestions=[
            "Verifique se há espaço livre no dispositivo.",
            "Tente novamente em alguns instantes."
        ],
        recovery_actions=[
            RecoveryAction("Tentar novamente", "retry:save_audio"),
            RecoveryAction("Cancelar", "action:cancel")
        ],
        severity=ErrorSeverity.ERROR
    ),
    
    "ERR_STORAGE_002": UserFacingError(
        error_code="ERR_STORAGE_002",
        message="Sessão não encontrada.",
        suggestions=["A sessão pode ter expirado ou sido removida."],
        recovery_actions=[
            RecoveryAction("Iniciar nova sessão", "action:start"),
            RecoveryAction("Ver sessões anteriores", "action:list")
        ],
        severity=ErrorSeverity.WARNING
    ),
    
    # Transcription errors
    "ERR_TRANSCRIPTION_001": UserFacingError(
        error_code="ERR_TRANSCRIPTION_001",
        message="Não foi possível transcrever o áudio.",
        suggestions=[
            "O áudio pode estar muito curto ou sem fala clara.",
            "Tente gravar novamente em um ambiente mais silencioso."
        ],
        recovery_actions=[
            RecoveryAction("Tentar novamente", "retry:transcription"),
            RecoveryAction("Pular este áudio", "action:skip_audio")
        ],
        severity=ErrorSeverity.ERROR
    ),
    
    # Session errors
    "ERR_SESSION_001": UserFacingError(
        error_code="ERR_SESSION_001",
        message="Operação não permitida no estado atual da sessão.",
        suggestions=["A sessão pode já estar finalizada."],
        recovery_actions=[
            RecoveryAction("Ver status", "action:status"),
            RecoveryAction("Iniciar nova", "action:start")
        ],
        severity=ErrorSeverity.WARNING
    ),
    
    # Network/Telegram errors
    "ERR_TELEGRAM_001": UserFacingError(
        error_code="ERR_TELEGRAM_001",
        message="Erro de comunicação com o Telegram.",
        suggestions=["Verifique sua conexão com a internet."],
        recovery_actions=[
            RecoveryAction("Tentar novamente", "retry:telegram")
        ],
        severity=ErrorSeverity.ERROR
    ),
    
    # Timeout errors
    "ERR_TIMEOUT_001": UserFacingError(
        error_code="ERR_TIMEOUT_001",
        message="A operação está demorando mais que o esperado.",
        suggestions=["Isso pode acontecer com áudios muito longos."],
        recovery_actions=[
            RecoveryAction("Continuar aguardando", "action:continue_wait"),
            RecoveryAction("Cancelar operação", "action:cancel_operation")
        ],
        severity=ErrorSeverity.WARNING
    ),
}

DEFAULT_ERROR = UserFacingError(
    error_code="ERR_UNKNOWN",
    message="Ocorreu um erro inesperado.",
    suggestions=["Tente novamente. Se o problema persistir, reinicie o bot."],
    recovery_actions=[
        RecoveryAction("Tentar novamente", "retry:unknown"),
        RecoveryAction("Ajuda", "action:help")
    ],
    severity=ErrorSeverity.ERROR
)
```

## Exception Mappings

```python
# Default mappings
EXCEPTION_MAPPINGS: dict[Type[Exception], str] = {
    FileNotFoundError: "ERR_STORAGE_002",
    PermissionError: "ERR_STORAGE_001",
    OSError: "ERR_STORAGE_001",
    TimeoutError: "ERR_TIMEOUT_001",
    InvalidStateError: "ERR_SESSION_001",
    # Add project-specific exceptions
}
```

## Logging Format

When translating exceptions, full details are logged:

```python
logger.error(
    "Error occurred",
    extra={
        "error_code": error.error_code,
        "correlation_id": generate_correlation_id(),
        "exception_type": type(exception).__name__,
        "exception_message": str(exception),
        "context": context,
        "traceback": traceback.format_exc()
    }
)
```

## Testing Contract

```python
# tests/contract/test_error_presentation.py

def test_translate_known_exception():
    """Known exceptions map to specific error codes."""
    
def test_translate_unknown_exception():
    """Unknown exceptions use DEFAULT_ERROR."""

def test_no_stack_trace_in_user_message():
    """User-facing message never contains stack trace."""

def test_error_logged_with_full_details():
    """Full exception details are logged at ERROR level."""

def test_recovery_actions_have_valid_callbacks():
    """All recovery actions have valid callback_data format."""

def test_simplified_format_removes_emojis():
    """Simplified mode produces plain text without decorative elements."""
```

## Constitution Compliance

- **Restriction #2**: Stack traces and implementation details NEVER appear in `UserFacingError.message` or `suggestions`
- **Principle IV**: Full exception logged server-side for debugging
- **Principle V**: Error catalog externalized, not hardcoded in handler logic
