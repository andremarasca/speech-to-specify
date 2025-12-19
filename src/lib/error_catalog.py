"""Externalized error catalog for humanized user messages.

Per Constitution Principle V (Externalized Configuration):
All user-facing error messages are externalized here rather than
hardcoded in source code.

Per contracts/error-catalog.md for 005-telegram-ux-overhaul.
Current language: Portuguese (pt-BR).

Error Code Format: ERR_{DOMAIN}_{NUMBER}
- STORAGE: 001-099 (File system, disk space)
- NETWORK: 100-199 (Connectivity, timeout)
- TRANSCRIPTION: 200-299 (Whisper, audio processing)
- SESSION: 300-399 (Session lifecycle, conflicts)
- TELEGRAM: 400-499 (API limits, message delivery)
- CONFIG: 500-599 (Missing config, invalid values)
- UNKNOWN: 900-999 (Unmapped exceptions)
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

# Forward declarations for type checking - actual models in src/models/ui_state.py
# These are duplicated here temporarily until Phase 2 creates the full models


class ErrorSeverity(str, Enum):
    """Severity level for user-facing errors."""
    
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass
class RecoveryAction:
    """An actionable recovery option for an error.
    
    Attributes:
        label: Button text shown to user
        callback_data: Callback data for button handler
    """
    
    label: str
    callback_data: str


@dataclass
class UserFacingError:
    """Structured error for humanized presentation.
    
    Per data-model.md for 005-telegram-ux-overhaul.
    
    Attributes:
        error_code: Unique error identifier (e.g., "ERR_STORAGE_001")
        message: User-friendly description (no technical jargon)
        suggestions: List of actionable recovery hints
        recovery_actions: List of buttons with callback handlers
        severity: Error severity level
    """
    
    error_code: str
    message: str
    suggestions: list[str] = field(default_factory=list)
    recovery_actions: list[RecoveryAction] = field(default_factory=list)
    severity: ErrorSeverity = ErrorSeverity.ERROR


# =============================================================================
# Error Catalog
# =============================================================================

ERROR_CATALOG: dict[str, UserFacingError] = {
    # -------------------------------------------------------------------------
    # Storage Errors (ERR_STORAGE_xxx)
    # -------------------------------------------------------------------------
    "ERR_STORAGE_001": UserFacingError(
        error_code="ERR_STORAGE_001",
        message="Não foi possível salvar o áudio no momento.",
        suggestions=[
            "Verifique se há espaço livre no dispositivo.",
            "Tente novamente em alguns instantes.",
        ],
        recovery_actions=[
            RecoveryAction(label="🔄 Tentar novamente", callback_data="retry:save_audio"),
            RecoveryAction(label="❌ Cancelar", callback_data="action:cancel"),
        ],
        severity=ErrorSeverity.ERROR,
    ),
    "ERR_STORAGE_002": UserFacingError(
        error_code="ERR_STORAGE_002",
        message="O espaço de armazenamento está esgotado.",
        suggestions=[
            "Libere espaço no dispositivo.",
            "Finalize sessões antigas que não precisa mais.",
        ],
        recovery_actions=[
            RecoveryAction(label="🔄 Tentar novamente", callback_data="retry:save_audio"),
            RecoveryAction(label="❌ Cancelar", callback_data="action:cancel"),
        ],
        severity=ErrorSeverity.CRITICAL,
    ),
    
    # -------------------------------------------------------------------------
    # Network Errors (ERR_NETWORK_xxx)
    # -------------------------------------------------------------------------
    "ERR_NETWORK_001": UserFacingError(
        error_code="ERR_NETWORK_001",
        message="A operação demorou mais que o esperado.",
        suggestions=[
            "Verifique sua conexão com a internet.",
            "Tente novamente em alguns instantes.",
        ],
        recovery_actions=[
            RecoveryAction(label="🔄 Tentar novamente", callback_data="retry:last_action"),
            RecoveryAction(label="❌ Cancelar", callback_data="action:cancel"),
        ],
        severity=ErrorSeverity.WARNING,
    ),
    "ERR_NETWORK_002": UserFacingError(
        error_code="ERR_NETWORK_002",
        message="Não foi possível conectar ao serviço.",
        suggestions=[
            "Verifique sua conexão com a internet.",
            "Tente novamente em alguns instantes.",
        ],
        recovery_actions=[
            RecoveryAction(label="🔄 Tentar novamente", callback_data="retry:last_action"),
            RecoveryAction(label="❌ Cancelar", callback_data="action:cancel"),
        ],
        severity=ErrorSeverity.ERROR,
    ),
    
    # -------------------------------------------------------------------------
    # Transcription Errors (ERR_TRANSCRIPTION_xxx)
    # -------------------------------------------------------------------------
    "ERR_TRANSCRIPTION_001": UserFacingError(
        error_code="ERR_TRANSCRIPTION_001",
        message="Não foi possível transcrever o áudio.",
        suggestions=[
            "O áudio pode estar corrompido ou em formato não suportado.",
            "Tente enviar o áudio novamente.",
        ],
        recovery_actions=[
            RecoveryAction(label="🔄 Tentar novamente", callback_data="retry:transcribe"),
            RecoveryAction(label="⏭️ Pular áudio", callback_data="action:skip_audio"),
            RecoveryAction(label="❌ Cancelar", callback_data="action:cancel"),
        ],
        severity=ErrorSeverity.ERROR,
    ),
    "ERR_TRANSCRIPTION_002": UserFacingError(
        error_code="ERR_TRANSCRIPTION_002",
        message="O áudio parece estar vazio ou sem fala detectável.",
        suggestions=[
            "Verifique se o microfone está funcionando.",
            "Tente gravar novamente com mais volume.",
        ],
        recovery_actions=[
            RecoveryAction(label="▶️ Continuar mesmo assim", callback_data="action:continue"),
            RecoveryAction(label="🗑️ Descartar áudio", callback_data="action:discard_audio"),
            RecoveryAction(label="❓ Ajuda", callback_data="action:help"),
        ],
        severity=ErrorSeverity.WARNING,
    ),
    
    # -------------------------------------------------------------------------
    # Session Errors (ERR_SESSION_xxx)
    # -------------------------------------------------------------------------
    "ERR_SESSION_001": UserFacingError(
        error_code="ERR_SESSION_001",
        message="Nenhuma sessão ativa encontrada.",
        suggestions=[
            "Envie uma mensagem de voz para iniciar uma nova sessão.",
        ],
        recovery_actions=[
            RecoveryAction(label="🆕 Nova sessão", callback_data="action:new_session"),
            RecoveryAction(label="❓ Ajuda", callback_data="action:help"),
        ],
        severity=ErrorSeverity.INFO,
    ),
    "ERR_SESSION_002": UserFacingError(
        error_code="ERR_SESSION_002",
        message="Já existe uma sessão em andamento.",
        suggestions=[
            "Finalize a sessão atual antes de iniciar uma nova.",
            "Ou continue adicionando áudios à sessão existente.",
        ],
        recovery_actions=[
            RecoveryAction(label="✅ Finalizar atual", callback_data="action:finalize"),
            RecoveryAction(label="↩️ Voltar à atual", callback_data="action:return_current"),
            RecoveryAction(label="❓ Ajuda", callback_data="action:help"),
        ],
        severity=ErrorSeverity.WARNING,
    ),
    "ERR_SESSION_003": UserFacingError(
        error_code="ERR_SESSION_003",
        message="Sessão anterior não foi finalizada corretamente.",
        suggestions=[
            "Você pode retomar a sessão de onde parou.",
            "Ou finalizar e iniciar uma nova.",
        ],
        recovery_actions=[
            RecoveryAction(label="▶️ Retomar", callback_data="action:resume_session"),
            RecoveryAction(label="✅ Finalizar", callback_data="action:finalize_orphan"),
            RecoveryAction(label="🗑️ Descartar", callback_data="action:discard_orphan"),
        ],
        severity=ErrorSeverity.WARNING,
    ),
    
    # -------------------------------------------------------------------------
    # Telegram Errors (ERR_TELEGRAM_xxx)
    # -------------------------------------------------------------------------
    "ERR_TELEGRAM_001": UserFacingError(
        error_code="ERR_TELEGRAM_001",
        message="Não foi possível enviar a mensagem.",
        suggestions=[
            "Tente novamente em alguns instantes.",
            "Se o problema persistir, reinicie o bot.",
        ],
        recovery_actions=[
            RecoveryAction(label="🔄 Tentar novamente", callback_data="retry:send_message"),
            RecoveryAction(label="❌ Cancelar", callback_data="action:cancel"),
        ],
        severity=ErrorSeverity.ERROR,
    ),
    "ERR_TELEGRAM_002": UserFacingError(
        error_code="ERR_TELEGRAM_002",
        message="Muitas mensagens em sequência. Aguarde um momento.",
        suggestions=[
            "Seus áudios serão processados em ordem.",
            "Aguarde a confirmação antes de enviar mais.",
        ],
        recovery_actions=[
            RecoveryAction(label="⏳ Ok, aguardar", callback_data="action:dismiss"),
            RecoveryAction(label="❓ Ajuda", callback_data="action:help"),
        ],
        severity=ErrorSeverity.WARNING,
    ),
    
    # -------------------------------------------------------------------------
    # Config Errors (ERR_CONFIG_xxx)
    # -------------------------------------------------------------------------
    "ERR_CONFIG_001": UserFacingError(
        error_code="ERR_CONFIG_001",
        message="Configuração inválida detectada.",
        suggestions=[
            "Entre em contato com o administrador do sistema.",
        ],
        recovery_actions=[
            RecoveryAction(label="❓ Ajuda", callback_data="action:help"),
        ],
        severity=ErrorSeverity.CRITICAL,
    ),
}

# =============================================================================
# Default Error (for unmapped exceptions)
# =============================================================================

DEFAULT_ERROR: UserFacingError = UserFacingError(
    error_code="ERR_UNKNOWN_001",
    message="Algo inesperado aconteceu.",
    suggestions=[
        "Tente novamente em alguns instantes.",
        "Se o problema persistir, reinicie o bot.",
    ],
    recovery_actions=[
        RecoveryAction(label="🔄 Tentar novamente", callback_data="retry:last_action"),
        RecoveryAction(label="❌ Cancelar", callback_data="action:cancel"),
    ],
    severity=ErrorSeverity.ERROR,
)

# =============================================================================
# Exception to Error Code Mapping
# =============================================================================

EXCEPTION_MAPPING: dict[type, str] = {
    # Order matters! More specific exceptions must come first
    # TimeoutError is a subclass of OSError, so it must be checked first
    TimeoutError: "ERR_NETWORK_001",
    ConnectionError: "ERR_NETWORK_002",
    PermissionError: "ERR_STORAGE_001",
    OSError: "ERR_STORAGE_002",  # Covers disk full and other OS errors
    ValueError: "ERR_SESSION_001",  # Default for value errors in session context
}


def get_error_for_exception(exc: Exception) -> UserFacingError:
    """Get the appropriate UserFacingError for an exception.
    
    Args:
        exc: The exception to map
        
    Returns:
        UserFacingError from catalog, or DEFAULT_ERROR if unmapped
    """
    for exc_type, error_code in EXCEPTION_MAPPING.items():
        if isinstance(exc, exc_type):
            return ERROR_CATALOG.get(error_code, DEFAULT_ERROR)
    return DEFAULT_ERROR


def get_error_by_code(error_code: str) -> UserFacingError:
    """Get an error by its code.
    
    Args:
        error_code: The error code (e.g., "ERR_STORAGE_001")
        
    Returns:
        UserFacingError from catalog, or DEFAULT_ERROR if not found
    """
    return ERROR_CATALOG.get(error_code, DEFAULT_ERROR)
