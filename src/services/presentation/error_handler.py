"""Error presentation layer for humanized user messages.

Per contracts/error-presentation.md for 005-telegram-ux-overhaul (T048-T055).

ErrorPresentationLayer captures exceptions from business logic and transforms
them into user-friendly messages with actionable recovery options. It enforces
Constitution Restriction #2 (no implementation exposure) while maintaining
debuggability via structured logging.
"""

import logging
import uuid
from typing import Type, Optional

from telegram import InlineKeyboardMarkup, InlineKeyboardButton

from src.lib.error_catalog import (
    UserFacingError,
    RecoveryAction,
    ErrorSeverity,
    ERROR_CATALOG,
    DEFAULT_ERROR,
    EXCEPTION_MAPPING,
    get_error_by_code,
)

logger = logging.getLogger(__name__)


class ErrorPresentationLayer:
    """Error presentation layer for humanized messages.
    
    Per contracts/error-presentation.md:
    - Translates exceptions to user-facing errors
    - Logs full details for debugging
    - Never exposes stack traces to users
    - Provides recovery actions via inline keyboards
    
    Example:
        layer = ErrorPresentationLayer()
        
        try:
            risky_operation()
        except Exception as e:
            error = layer.translate_exception(e, {"session_id": "123"})
            text, keyboard = layer.format_for_telegram(error)
            await bot.send_message(chat_id, text, reply_markup=keyboard)
    """
    
    def __init__(self):
        """Initialize the error presentation layer."""
        # Copy default mappings to allow custom registrations
        self._exception_mappings: dict[Type[Exception], str] = dict(EXCEPTION_MAPPING)
        
    def translate_exception(
        self,
        exception: Exception,
        context: Optional[dict] = None,
    ) -> UserFacingError:
        """Transform exception into user-facing error.
        
        Args:
            exception: Caught exception from business logic
            context: Optional context (session_id, operation, etc.)
            
        Returns:
            UserFacingError with humanized message and recovery actions
            
        Side Effects:
            Logs full exception details at ERROR level with correlation ID
        """
        # Generate correlation ID for log tracing
        correlation_id = str(uuid.uuid4())[:8]
        
        # Find matching error code
        error_code = self._find_error_code(exception)
        error = get_error_by_code(error_code)
        
        # Log full details for debugging (never exposed to user)
        log_context = {
            "correlation_id": correlation_id,
            "error_code": error_code,
            "exception_type": type(exception).__name__,
            "exception_message": str(exception),
            "context": context or {},
        }
        
        logger.error(
            f"Error [{correlation_id}] {error_code}: {type(exception).__name__}: {exception}",
            extra=log_context,
            exc_info=True,  # Include traceback in logs
        )
        
        return error
        
    def get_error_by_code(self, error_code: str) -> UserFacingError:
        """Retrieve error from catalog by code.
        
        Args:
            error_code: Error code (e.g., "ERR_STORAGE_001")
            
        Returns:
            Configured UserFacingError or DEFAULT_ERROR if not found
        """
        return get_error_by_code(error_code)
        
    def register_exception_mapping(
        self,
        exception_type: Type[Exception],
        error_code: str,
    ) -> None:
        """Register mapping from exception type to error code.
        
        Args:
            exception_type: Exception class to map
            error_code: Target error code
        """
        self._exception_mappings[exception_type] = error_code
        logger.debug(f"Registered exception mapping: {exception_type.__name__} -> {error_code}")
        
    def format_for_telegram(
        self,
        error: UserFacingError,
        simplified: bool = False,
    ) -> tuple[str, InlineKeyboardMarkup]:
        """Format error for Telegram message.
        
        Args:
            error: UserFacingError to format
            simplified: Whether to use simplified UI mode (no emojis)
            
        Returns:
            Tuple of (message_text, keyboard_markup)
        """
        # Build message text
        if simplified:
            text = self._format_simplified(error)
        else:
            text = self._format_standard(error)
            
        # Build keyboard with recovery actions
        keyboard = self._build_recovery_keyboard(error, simplified)
        
        return text, keyboard
        
    def _find_error_code(self, exception: Exception) -> str:
        """Find the error code for an exception.
        
        Checks registered mappings in order (more specific first).
        """
        # Check exact type first, then parent classes
        for exc_type, error_code in self._exception_mappings.items():
            if isinstance(exception, exc_type):
                return error_code
                
        return DEFAULT_ERROR.error_code
        
    def _format_standard(self, error: UserFacingError) -> str:
        """Format error with emojis and rich formatting."""
        # Severity emoji
        severity_emoji = {
            ErrorSeverity.INFO: "ℹ️",
            ErrorSeverity.WARNING: "⚠️",
            ErrorSeverity.ERROR: "❌",
            ErrorSeverity.CRITICAL: "🚨",
        }.get(error.severity, "❌")
        
        # Build message
        lines = [
            f"{severity_emoji} <b>Erro</b>",
            "",
            error.message,
        ]
        
        # Add suggestions if any
        if error.suggestions:
            lines.append("")
            lines.append("💡 <b>Sugestões:</b>")
            for suggestion in error.suggestions:
                lines.append(f"• {suggestion}")
                
        return "\n".join(lines)
        
    def _format_simplified(self, error: UserFacingError) -> str:
        """Format error in simplified mode (text only, no emojis)."""
        lines = [
            "Erro:",
            "",
            error.message,
        ]
        
        if error.suggestions:
            lines.append("")
            lines.append("Sugestões:")
            for suggestion in error.suggestions:
                lines.append(f"- {suggestion}")
                
        return "\n".join(lines)
        
    def _build_recovery_keyboard(
        self,
        error: UserFacingError,
        simplified: bool = False,
    ) -> InlineKeyboardMarkup:
        """Build inline keyboard with recovery action buttons."""
        buttons = []
        
        for action in error.recovery_actions:
            # In simplified mode, remove emojis from labels
            label = action.label
            if simplified:
                # Remove common emojis (simple approach)
                for emoji in ["🔄", "❌", "⏭️", "🆕", "❓", "▶️", "🗑️", "✅", "↩️", "⏳"]:
                    label = label.replace(emoji, "").strip()
                    
            buttons.append([
                InlineKeyboardButton(
                    text=label,
                    callback_data=action.callback_data,
                )
            ])
            
        # Always add help option if not already present
        has_help = any(
            "help" in action.callback_data.lower() 
            for action in error.recovery_actions
        )
        
        if not has_help:
            help_label = "Ajuda" if simplified else "❓ Ajuda"
            buttons.append([
                InlineKeyboardButton(
                    text=help_label,
                    callback_data="action:help",
                )
            ])
            
        return InlineKeyboardMarkup(buttons)


# Global instance for convenience
_error_layer: Optional[ErrorPresentationLayer] = None


def get_error_presentation_layer() -> ErrorPresentationLayer:
    """Get the global error presentation layer instance."""
    global _error_layer
    if _error_layer is None:
        _error_layer = ErrorPresentationLayer()
    return _error_layer


def reset_error_presentation_layer() -> None:
    """Reset the global error presentation layer (for testing)."""
    global _error_layer
    _error_layer = None
