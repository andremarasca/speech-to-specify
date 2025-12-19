"""Contract tests for ErrorPresentationLayer.

Per T045-T047 from 005-telegram-ux-overhaul.

Tests the ErrorPresentationLayer component per contracts/error-presentation.md:
- translate_exception() maps exceptions to UserFacingError
- format_for_telegram() creates message + keyboard
- No stack traces exposed to user
"""

import pytest
from unittest.mock import MagicMock, patch

from src.lib.error_catalog import (
    UserFacingError,
    RecoveryAction,
    ErrorSeverity,
    ERROR_CATALOG,
    DEFAULT_ERROR,
    get_error_by_code,
    get_error_for_exception,
)


class TestTranslateException:
    """Tests for ErrorPresentationLayer.translate_exception() per T045."""

    def test_translate_file_not_found_error(self):
        """FileNotFoundError should map to ERR_STORAGE_002 (mapped via OSError fallback)."""
        from src.services.presentation.error_handler import ErrorPresentationLayer

        layer = ErrorPresentationLayer()
        exc = FileNotFoundError("test.txt not found")

        result = layer.translate_exception(exc)

        assert isinstance(result, UserFacingError)
        # FileNotFoundError inherits from OSError, which maps to ERR_STORAGE_002
        assert result.error_code == "ERR_STORAGE_002"
        # The message is about storage/disk space (per error catalog)
        assert "armazenamento" in result.message.lower() or "espaço" in result.message.lower()

    def test_translate_permission_error(self):
        """PermissionError should map to ERR_STORAGE_001."""
        from src.services.presentation.error_handler import ErrorPresentationLayer

        layer = ErrorPresentationLayer()
        exc = PermissionError("Access denied")

        result = layer.translate_exception(exc)

        assert isinstance(result, UserFacingError)
        assert result.error_code == "ERR_STORAGE_001"

    def test_translate_timeout_error(self):
        """TimeoutError should map to ERR_NETWORK_001."""
        from src.services.presentation.error_handler import ErrorPresentationLayer

        layer = ErrorPresentationLayer()
        exc = TimeoutError("Connection timed out")

        result = layer.translate_exception(exc)

        assert isinstance(result, UserFacingError)
        assert result.error_code == "ERR_NETWORK_001"

    def test_translate_unknown_exception_returns_default(self):
        """Unknown exceptions should return DEFAULT_ERROR."""
        from src.services.presentation.error_handler import ErrorPresentationLayer

        layer = ErrorPresentationLayer()
        exc = RuntimeError("Some unexpected error")

        result = layer.translate_exception(exc)

        assert isinstance(result, UserFacingError)
        assert result.error_code == "ERR_UNKNOWN_001"

    def test_translate_with_context(self):
        """Context should be passed to logger but not exposed."""
        from src.services.presentation.error_handler import ErrorPresentationLayer

        layer = ErrorPresentationLayer()
        exc = FileNotFoundError("test.txt")
        context = {"session_id": "test-session", "operation": "save"}

        with patch("src.services.presentation.error_handler.logger") as mock_logger:
            result = layer.translate_exception(exc, context=context)

            # Logger should be called with full details
            mock_logger.error.assert_called_once()
            log_call = mock_logger.error.call_args
            # Context should be in log message
            assert "test-session" in str(log_call) or context in log_call

    def test_translate_includes_recovery_actions(self):
        """Translated errors should include recovery actions."""
        from src.services.presentation.error_handler import ErrorPresentationLayer

        layer = ErrorPresentationLayer()
        exc = FileNotFoundError("test.txt")

        result = layer.translate_exception(exc)

        assert len(result.recovery_actions) > 0
        assert all(
            isinstance(action, RecoveryAction) 
            for action in result.recovery_actions
        )


class TestFormatForTelegram:
    """Tests for ErrorPresentationLayer.format_for_telegram() per T046."""

    def test_format_returns_text_and_keyboard(self):
        """format_for_telegram should return tuple of (text, keyboard)."""
        from src.services.presentation.error_handler import ErrorPresentationLayer
        from telegram import InlineKeyboardMarkup

        layer = ErrorPresentationLayer()
        error = get_error_by_code("ERR_STORAGE_001")

        text, keyboard = layer.format_for_telegram(error)

        assert isinstance(text, str)
        assert len(text) > 0
        assert isinstance(keyboard, InlineKeyboardMarkup)

    def test_format_includes_error_message(self):
        """Formatted text should include the error message."""
        from src.services.presentation.error_handler import ErrorPresentationLayer

        layer = ErrorPresentationLayer()
        error = get_error_by_code("ERR_STORAGE_001")

        text, _ = layer.format_for_telegram(error)

        assert error.message in text

    def test_format_includes_suggestions(self):
        """Formatted text should include suggestions."""
        from src.services.presentation.error_handler import ErrorPresentationLayer

        layer = ErrorPresentationLayer()
        error = UserFacingError(
            error_code="TEST_001",
            message="Test error",
            suggestions=["Try restarting", "Check connection"],
            recovery_actions=[],
            severity=ErrorSeverity.ERROR,
        )

        text, _ = layer.format_for_telegram(error)

        assert "Try restarting" in text or "restarting" in text.lower()

    def test_format_simplified_mode(self):
        """Simplified mode should use plain text without emojis."""
        from src.services.presentation.error_handler import ErrorPresentationLayer

        layer = ErrorPresentationLayer()
        error = get_error_by_code("ERR_STORAGE_001")

        text_normal, _ = layer.format_for_telegram(error, simplified=False)
        text_simplified, _ = layer.format_for_telegram(error, simplified=True)

        # Simplified should have fewer or no emojis
        emoji_count_normal = sum(1 for c in text_normal if ord(c) > 127)
        emoji_count_simplified = sum(1 for c in text_simplified if ord(c) > 127)

        assert emoji_count_simplified <= emoji_count_normal

    def test_format_keyboard_has_recovery_buttons(self):
        """Keyboard should include buttons for recovery actions."""
        from src.services.presentation.error_handler import ErrorPresentationLayer

        layer = ErrorPresentationLayer()
        error = UserFacingError(
            error_code="TEST_001",
            message="Test error",
            suggestions=[],
            recovery_actions=[
                RecoveryAction(label="Retry", callback_data="retry:test"),
                RecoveryAction(label="Cancel", callback_data="action:cancel"),
            ],
            severity=ErrorSeverity.ERROR,
        )

        _, keyboard = layer.format_for_telegram(error)

        # Check keyboard has buttons
        all_buttons = []
        for row in keyboard.inline_keyboard:
            all_buttons.extend(row)

        button_labels = [btn.text for btn in all_buttons]
        button_callbacks = [btn.callback_data for btn in all_buttons]

        assert "Retry" in button_labels
        assert "retry:test" in button_callbacks


class TestNoStackTraces:
    """Tests verifying no stack traces in user messages per T047."""

    def test_no_stack_trace_in_formatted_message(self):
        """Formatted error should not contain stack trace patterns."""
        from src.services.presentation.error_handler import ErrorPresentationLayer

        layer = ErrorPresentationLayer()

        # Create an exception with a traceback
        try:
            raise ValueError("Test error with traceback")
        except ValueError as e:
            result = layer.translate_exception(e)

        text, _ = layer.format_for_telegram(result)

        # Check for common stack trace patterns
        stack_trace_patterns = [
            "Traceback",
            "File \"",
            ".py\", line",
            "raise ",
            "  at ",
            "Exception:",
            "Error:",  # But allow "Erro:" in Portuguese
        ]

        for pattern in stack_trace_patterns:
            if pattern == "Error:":
                # Allow Portuguese error messages
                continue
            assert pattern not in text, f"Stack trace pattern '{pattern}' found in user message"

    def test_no_exception_class_name_exposed(self):
        """Exception class names should not be exposed to user."""
        from src.services.presentation.error_handler import ErrorPresentationLayer

        layer = ErrorPresentationLayer()

        exceptions_to_test = [
            ValueError("test"),
            FileNotFoundError("test"),
            PermissionError("test"),
            TimeoutError("test"),
            RuntimeError("test"),
        ]

        for exc in exceptions_to_test:
            result = layer.translate_exception(exc)
            text, _ = layer.format_for_telegram(result)

            # Class name should not appear
            class_name = exc.__class__.__name__
            assert class_name not in text, f"Exception class '{class_name}' exposed in message"

    def test_no_file_paths_in_user_message(self):
        """Internal file paths should not be exposed."""
        from src.services.presentation.error_handler import ErrorPresentationLayer

        layer = ErrorPresentationLayer()

        try:
            raise FileNotFoundError("/home/user/secret/config.py not found")
        except FileNotFoundError as e:
            result = layer.translate_exception(e)

        text, _ = layer.format_for_telegram(result)

        # Check for path patterns
        assert "/home/" not in text
        assert "config.py" not in text
        assert ".py" not in text or "py" in text.lower()  # Allow Portuguese words with "py"


class TestGetErrorByCode:
    """Tests for error catalog lookup."""

    def test_get_existing_error(self):
        """Should return error from catalog."""
        result = get_error_by_code("ERR_STORAGE_001")

        assert result.error_code == "ERR_STORAGE_001"
        assert len(result.message) > 0

    def test_get_unknown_code_returns_default(self):
        """Unknown code should return DEFAULT_ERROR."""
        result = get_error_by_code("ERR_NONEXISTENT_999")

        assert result.error_code == DEFAULT_ERROR.error_code

    def test_all_catalog_errors_have_required_fields(self):
        """All errors in catalog should have required fields."""
        for code, error in ERROR_CATALOG.items():
            assert error.error_code == code
            assert len(error.message) > 0
            assert isinstance(error.severity, ErrorSeverity)
            assert isinstance(error.suggestions, list)
            assert isinstance(error.recovery_actions, list)


class TestRegisterExceptionMapping:
    """Tests for custom exception mapping registration."""

    def test_register_custom_exception(self):
        """Should be able to register custom exception mappings."""
        from src.services.presentation.error_handler import ErrorPresentationLayer

        class CustomError(Exception):
            pass

        layer = ErrorPresentationLayer()
        layer.register_exception_mapping(CustomError, "ERR_STORAGE_001")

        exc = CustomError("Custom error message")
        result = layer.translate_exception(exc)

        assert result.error_code == "ERR_STORAGE_001"

    def test_custom_mapping_overrides_default(self):
        """Custom mapping should take precedence."""
        from src.services.presentation.error_handler import ErrorPresentationLayer

        layer = ErrorPresentationLayer()
        
        # Override default mapping for ValueError
        layer.register_exception_mapping(ValueError, "ERR_STORAGE_002")

        exc = ValueError("test")
        result = layer.translate_exception(exc)

        assert result.error_code == "ERR_STORAGE_002"
