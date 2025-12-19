"""Contract tests for error catalog.

Per contracts/error-catalog.md for 005-telegram-ux-overhaul.

These tests verify:
1. All required error codes are present
2. Every error has at least one recovery action
3. Messages contain no technical jargon
4. DEFAULT_ERROR is properly defined
"""

import pytest

from src.lib.error_catalog import (
    ERROR_CATALOG,
    DEFAULT_ERROR,
    ErrorSeverity,
    RecoveryAction,
    UserFacingError,
    get_error_by_code,
    get_error_for_exception,
)


class TestRequiredErrorCodes:
    """Verify all minimum required error codes exist per contract."""

    REQUIRED_CODES = [
        # Storage errors
        "ERR_STORAGE_001",
        "ERR_STORAGE_002",
        # Network errors
        "ERR_NETWORK_001",
        "ERR_NETWORK_002",
        # Transcription errors
        "ERR_TRANSCRIPTION_001",
        "ERR_TRANSCRIPTION_002",
        # Session errors
        "ERR_SESSION_001",
        "ERR_SESSION_002",
        "ERR_SESSION_003",
        # Telegram errors
        "ERR_TELEGRAM_001",
        "ERR_TELEGRAM_002",
    ]

    def test_all_required_codes_present(self):
        """Verify all minimum required error codes exist."""
        for code in self.REQUIRED_CODES:
            assert code in ERROR_CATALOG, f"Missing required error: {code}"

    @pytest.mark.parametrize("code", REQUIRED_CODES)
    def test_required_code_is_user_facing_error(self, code: str):
        """Each required code must be a properly structured UserFacingError."""
        error = ERROR_CATALOG[code]
        assert isinstance(error, UserFacingError)
        assert error.error_code == code
        assert len(error.message) > 0


class TestErrorRecoveryActions:
    """Verify all errors have recovery actions."""

    def test_all_errors_have_recovery_actions(self):
        """Every error must have at least one recovery action."""
        for code, error in ERROR_CATALOG.items():
            assert len(error.recovery_actions) >= 1, f"{code} has no recovery actions"

    def test_recovery_actions_have_required_fields(self):
        """Each recovery action must have label and callback_data."""
        for code, error in ERROR_CATALOG.items():
            for i, action in enumerate(error.recovery_actions):
                assert isinstance(action, RecoveryAction), f"{code} action {i} is not RecoveryAction"
                assert len(action.label) > 0, f"{code} action {i} has empty label"
                assert len(action.callback_data) > 0, f"{code} action {i} has empty callback_data"

    def test_callback_data_follows_pattern(self):
        """Callback data should follow action:* or retry:* pattern."""
        for code, error in ERROR_CATALOG.items():
            for action in error.recovery_actions:
                assert ":" in action.callback_data, (
                    f"{code} callback_data '{action.callback_data}' doesn't follow pattern"
                )


class TestNoTechnicalJargon:
    """Verify messages don't contain technical terms."""

    FORBIDDEN_TERMS = [
        "exception",
        "stack",
        "trace",
        "traceback",
        "null",
        "none",
        "error code",
        "runtime",
        "internal",
        "debug",
        "log",
        "crash",
        "bug",
        "api",
        "http",
        "socket",
        "memory",
        # "process" removed - 'processados' is valid Portuguese
        "thread",
    ]

    def test_no_technical_jargon_in_messages(self):
        """Messages must not contain technical terms."""
        for code, error in ERROR_CATALOG.items():
            msg_lower = error.message.lower()
            for term in self.FORBIDDEN_TERMS:
                assert term not in msg_lower, f"{code} contains forbidden term: '{term}'"

    def test_no_technical_jargon_in_suggestions(self):
        """Suggestions must not contain technical terms."""
        for code, error in ERROR_CATALOG.items():
            for suggestion in error.suggestions:
                suggestion_lower = suggestion.lower()
                for term in self.FORBIDDEN_TERMS:
                    assert term not in suggestion_lower, (
                        f"{code} suggestion contains forbidden term: '{term}'"
                    )


class TestDefaultError:
    """Verify DEFAULT_ERROR is properly defined."""

    def test_default_error_exists(self):
        """DEFAULT_ERROR must be defined for unmapped exceptions."""
        assert DEFAULT_ERROR is not None

    def test_default_error_code_format(self):
        """DEFAULT_ERROR must use ERR_UNKNOWN prefix."""
        assert DEFAULT_ERROR.error_code.startswith("ERR_UNKNOWN")

    def test_default_error_has_recovery_actions(self):
        """DEFAULT_ERROR must have recovery actions."""
        assert len(DEFAULT_ERROR.recovery_actions) >= 1

    def test_default_error_is_user_facing(self):
        """DEFAULT_ERROR must be a UserFacingError."""
        assert isinstance(DEFAULT_ERROR, UserFacingError)


class TestErrorSeverity:
    """Verify error severities are properly assigned."""

    def test_all_errors_have_valid_severity(self):
        """All errors must have a valid ErrorSeverity."""
        for code, error in ERROR_CATALOG.items():
            assert isinstance(error.severity, ErrorSeverity), f"{code} has invalid severity"

    def test_critical_errors_are_marked_critical(self):
        """Disk full and config errors should be CRITICAL."""
        critical_codes = ["ERR_STORAGE_002", "ERR_CONFIG_001"]
        for code in critical_codes:
            if code in ERROR_CATALOG:
                assert ERROR_CATALOG[code].severity == ErrorSeverity.CRITICAL, (
                    f"{code} should be CRITICAL"
                )


class TestErrorLookupFunctions:
    """Test the helper functions for error lookup."""

    def test_get_error_by_code_existing(self):
        """get_error_by_code returns error for existing code."""
        error = get_error_by_code("ERR_STORAGE_001")
        assert error.error_code == "ERR_STORAGE_001"

    def test_get_error_by_code_missing(self):
        """get_error_by_code returns DEFAULT_ERROR for missing code."""
        error = get_error_by_code("ERR_NONEXISTENT_999")
        assert error == DEFAULT_ERROR

    def test_get_error_for_exception_permission(self):
        """get_error_for_exception maps PermissionError correctly."""
        error = get_error_for_exception(PermissionError("denied"))
        assert error.error_code == "ERR_STORAGE_001"

    def test_get_error_for_exception_timeout(self):
        """get_error_for_exception maps TimeoutError correctly."""
        error = get_error_for_exception(TimeoutError())
        assert error.error_code == "ERR_NETWORK_001"

    def test_get_error_for_exception_unmapped(self):
        """get_error_for_exception returns DEFAULT_ERROR for unmapped exceptions."""
        error = get_error_for_exception(KeyError("unmapped"))
        assert error == DEFAULT_ERROR


class TestErrorCodeFormat:
    """Verify error codes follow the correct format."""

    def test_error_code_format(self):
        """All error codes must follow ERR_{DOMAIN}_{NUMBER} pattern."""
        import re
        pattern = r"^ERR_[A-Z]+_\d{3}$"
        for code in ERROR_CATALOG.keys():
            assert re.match(pattern, code), f"Invalid error code format: {code}"

    def test_error_code_matches_key(self):
        """Error code in UserFacingError must match dict key."""
        for code, error in ERROR_CATALOG.items():
            assert error.error_code == code, f"Mismatch: key={code}, error.code={error.error_code}"
