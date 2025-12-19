"""Unit tests for message templates.

Per tasks.md for 005-telegram-ux-overhaul.

These tests verify:
1. All required messages exist
2. Message templates are formattable
3. Simplified versions exist for key messages
4. Helper functions work correctly
"""

import pytest

from src.lib import messages
from src.lib.messages import (
    get_message,
    get_button_label,
    get_help_message,
    HELP_MESSAGES,
    HELP_MESSAGES_SIMPLIFIED,
    OPERATION_TYPE_NAMES,
)


class TestRequiredMessagesExist:
    """Verify all required message templates exist."""

    REQUIRED_SESSION_MESSAGES = [
        "SESSION_CREATED",
        "SESSION_CREATED_SIMPLIFIED",
        "AUDIO_RECEIVED",
        "AUDIO_RECEIVED_SIMPLIFIED",
        "SESSION_FINALIZED",
        "SESSION_FINALIZED_SIMPLIFIED",
        "SESSION_STATUS",
        "SESSION_STATUS_SIMPLIFIED",
        "NO_ACTIVE_SESSION",
        "NO_ACTIVE_SESSION_SIMPLIFIED",
    ]

    REQUIRED_PROGRESS_MESSAGES = [
        "PROGRESS_STARTED",
        "PROGRESS_STARTED_SIMPLIFIED",
        "PROGRESS_UPDATE",
        "PROGRESS_UPDATE_SIMPLIFIED",
        "PROGRESS_COMPLETE",
        "PROGRESS_COMPLETE_SIMPLIFIED",
    ]

    REQUIRED_BUTTON_LABELS = [
        "BUTTON_FINALIZE",
        "BUTTON_FINALIZE_SIMPLIFIED",
        "BUTTON_STATUS",
        "BUTTON_STATUS_SIMPLIFIED",
        "BUTTON_HELP",
        "BUTTON_HELP_SIMPLIFIED",
        "BUTTON_CANCEL",
        "BUTTON_CANCEL_SIMPLIFIED",
        "BUTTON_RETRY",
        "BUTTON_RETRY_SIMPLIFIED",
    ]

    @pytest.mark.parametrize("message_name", REQUIRED_SESSION_MESSAGES)
    def test_session_messages_exist(self, message_name: str):
        """Required session messages should exist."""
        assert hasattr(messages, message_name), f"Missing message: {message_name}"
        assert getattr(messages, message_name), f"Empty message: {message_name}"

    @pytest.mark.parametrize("message_name", REQUIRED_PROGRESS_MESSAGES)
    def test_progress_messages_exist(self, message_name: str):
        """Required progress messages should exist."""
        assert hasattr(messages, message_name), f"Missing message: {message_name}"
        assert getattr(messages, message_name), f"Empty message: {message_name}"

    @pytest.mark.parametrize("message_name", REQUIRED_BUTTON_LABELS)
    def test_button_labels_exist(self, message_name: str):
        """Required button labels should exist."""
        assert hasattr(messages, message_name), f"Missing label: {message_name}"
        assert getattr(messages, message_name), f"Empty label: {message_name}"


class TestMessageFormatting:
    """Test message template formatting."""

    def test_audio_received_formatting(self):
        """AUDIO_RECEIVED should format with sequence number and session name."""
        msg = messages.AUDIO_RECEIVED.format(sequence=5, session_name="test-session")
        assert "5" in msg
        assert "test-session" in msg

    def test_session_finalized_formatting(self):
        """SESSION_FINALIZED should format with audio count."""
        msg = messages.SESSION_FINALIZED.format(audio_count=3)
        assert "3" in msg

    def test_session_status_formatting(self):
        """SESSION_STATUS should format with all fields."""
        msg = messages.SESSION_STATUS.format(
            session_name="test-session",
            audio_count=5,
            created_at="2025-12-19 15:30",
            state="COLLECTING",
        )
        assert "test-session" in msg
        assert "5" in msg
        assert "2025-12-19 15:30" in msg
        assert "COLLECTING" in msg

    def test_progress_update_formatting(self):
        """PROGRESS_UPDATE should format with description and percentage."""
        msg = messages.PROGRESS_UPDATE.format(
            description="Transcrevendo áudio 2 de 5",
            progress_bar="▓▓▓▓░░░░░░",
            percentage=40,
        )
        assert "40%" in msg
        assert "▓▓▓▓" in msg


class TestGetMessageHelper:
    """Tests for get_message helper function."""

    def test_get_message_returns_message(self):
        """get_message should return the message for a key."""
        msg = get_message("SESSION_CREATED")
        assert msg == messages.SESSION_CREATED

    def test_get_message_simplified(self):
        """get_message should return simplified version when requested."""
        msg = get_message("SESSION_CREATED", simplified=True)
        assert msg == messages.SESSION_CREATED_SIMPLIFIED

    def test_get_message_with_formatting(self):
        """get_message should format the message with kwargs."""
        msg = get_message("AUDIO_RECEIVED", sequence=3, session_name="test-session")
        assert "3" in msg
        assert "test-session" in msg

    def test_get_message_fallback_to_normal(self):
        """get_message should fall back to normal if simplified doesn't exist."""
        # Test with a key that might not have simplified version
        msg = get_message("GENERIC_ERROR", simplified=True)
        assert msg is not None

    def test_get_message_unknown_key(self):
        """get_message should return generic error for unknown key."""
        msg = get_message("UNKNOWN_KEY_THAT_DOES_NOT_EXIST")
        assert msg == messages.GENERIC_ERROR


class TestGetButtonLabelHelper:
    """Tests for get_button_label helper function."""

    def test_get_button_label_normal(self):
        """get_button_label should return label with emoji."""
        label = get_button_label("FINALIZE")
        assert "✅" in label

    def test_get_button_label_simplified(self):
        """get_button_label simplified should not have emoji."""
        label = get_button_label("FINALIZE", simplified=True)
        assert "✅" not in label
        assert "Finalizar" in label


class TestGetHelpMessageHelper:
    """Tests for get_help_message helper function."""

    def test_get_help_message_session_active(self):
        """get_help_message should return contextual help."""
        msg = get_help_message("SESSION_ACTIVE")
        assert msg == HELP_MESSAGES["SESSION_ACTIVE"]

    def test_get_help_message_simplified(self):
        """get_help_message should return simplified version."""
        msg = get_help_message("SESSION_ACTIVE", simplified=True)
        assert msg == HELP_MESSAGES_SIMPLIFIED["SESSION_ACTIVE"]

    def test_get_help_message_default(self):
        """get_help_message should return default for unknown context."""
        msg = get_help_message("UNKNOWN_CONTEXT")
        assert msg == HELP_MESSAGES.get("DEFAULT", "")


class TestHelpMessages:
    """Tests for help message dictionaries."""

    REQUIRED_HELP_CONTEXTS = [
        "SESSION_ACTIVE",
        "SESSION_EMPTY",
        "PROCESSING",
        "RESULTS",
        "ERROR_RECOVERY",
        "DEFAULT",
    ]

    @pytest.mark.parametrize("context", REQUIRED_HELP_CONTEXTS)
    def test_help_message_exists(self, context: str):
        """All required help contexts should exist."""
        assert context in HELP_MESSAGES, f"Missing help context: {context}"
        assert HELP_MESSAGES[context], f"Empty help for: {context}"

    @pytest.mark.parametrize("context", REQUIRED_HELP_CONTEXTS)
    def test_simplified_help_exists(self, context: str):
        """All help contexts should have simplified versions."""
        assert context in HELP_MESSAGES_SIMPLIFIED, f"Missing simplified help: {context}"
        assert HELP_MESSAGES_SIMPLIFIED[context], f"Empty simplified help: {context}"


class TestOperationTypeNames:
    """Tests for operation type display names."""

    REQUIRED_TYPES = [
        "TRANSCRIPTION",
        "EMBEDDING",
        "PROCESSING",
        "SEARCH",
    ]

    @pytest.mark.parametrize("op_type", REQUIRED_TYPES)
    def test_operation_type_name_exists(self, op_type: str):
        """All operation types should have display names."""
        assert op_type in OPERATION_TYPE_NAMES, f"Missing operation type: {op_type}"
        assert OPERATION_TYPE_NAMES[op_type], f"Empty name for: {op_type}"


class TestSimplifiedMessagesNoEmojis:
    """Verify simplified messages don't contain emojis."""

    EMOJI_CHARS = ["✅", "❌", "📊", "❓", "🎙️", "✨", "⏳", "⚠️", "🔄", "📄", "🔍", "🚀"]

    def test_session_created_simplified_no_emoji(self):
        """SESSION_CREATED_SIMPLIFIED should not have emojis."""
        for emoji in self.EMOJI_CHARS:
            assert emoji not in messages.SESSION_CREATED_SIMPLIFIED

    def test_audio_received_simplified_no_emoji(self):
        """AUDIO_RECEIVED_SIMPLIFIED should not have emojis."""
        for emoji in self.EMOJI_CHARS:
            assert emoji not in messages.AUDIO_RECEIVED_SIMPLIFIED

    def test_button_finalize_simplified_no_emoji(self):
        """BUTTON_FINALIZE_SIMPLIFIED should not have emojis."""
        for emoji in self.EMOJI_CHARS:
            assert emoji not in messages.BUTTON_FINALIZE_SIMPLIFIED


class TestPortugueseMessages:
    """Verify messages are in Portuguese (pt-BR)."""

    # Common Portuguese words that should appear in messages
    PORTUGUESE_INDICATORS = [
        "sessão",
        "áudio",
        "finalizar",
        "ajuda",
        "cancelar",
        "tentar",
        "novamente",
    ]

    def test_messages_contain_portuguese(self):
        """Messages should contain Portuguese words."""
        all_messages = (
            messages.SESSION_CREATED
            + messages.AUDIO_RECEIVED
            + messages.SESSION_FINALIZED
            + messages.NO_ACTIVE_SESSION
        ).lower()
        
        found_portuguese = any(
            word in all_messages for word in self.PORTUGUESE_INDICATORS
        )
        assert found_portuguese, "Messages should be in Portuguese"
