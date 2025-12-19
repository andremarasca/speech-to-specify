"""Unit tests for keyboard builders.

Per tasks.md for 005-telegram-ux-overhaul.

These tests verify:
1. All keyboard types can be built
2. Simplified mode works correctly
3. All keyboards include help button (FR-008)
4. Button labels are externalized (Constitution Principle V)
"""

import pytest

from src.models.ui_state import (
    KeyboardType,
    ConfirmationContext,
    ConfirmationType,
    ConfirmationOption,
)
from src.services.telegram.keyboards import (
    build_keyboard,
    build_recovery_keyboard,
    keyboard_has_help_button,
)


class TestBuildKeyboard:
    """Tests for build_keyboard function."""

    @pytest.mark.parametrize("keyboard_type", list(KeyboardType))
    def test_all_keyboard_types_buildable(self, keyboard_type: KeyboardType):
        """All KeyboardType values should be buildable."""
        # CONFIRMATION type needs a context
        if keyboard_type == KeyboardType.CONFIRMATION:
            context = ConfirmationContext(
                confirmation_type=ConfirmationType.SESSION_CONFLICT,
                options=[
                    ConfirmationOption(label="OK", callback_data="action:ok"),
                ],
            )
            keyboard = build_keyboard(keyboard_type, confirmation_context=context)
        else:
            keyboard = build_keyboard(keyboard_type)
        
        assert keyboard is not None
        assert len(keyboard.inline_keyboard) > 0

    @pytest.mark.parametrize("keyboard_type", list(KeyboardType))
    def test_simplified_mode_works(self, keyboard_type: KeyboardType):
        """All keyboard types should support simplified mode."""
        if keyboard_type == KeyboardType.CONFIRMATION:
            context = ConfirmationContext(
                confirmation_type=ConfirmationType.SESSION_CONFLICT,
                options=[
                    ConfirmationOption(label="OK", callback_data="action:ok"),
                ],
            )
            keyboard = build_keyboard(keyboard_type, simplified=True, confirmation_context=context)
        else:
            keyboard = build_keyboard(keyboard_type, simplified=True)
        
        assert keyboard is not None

    def test_invalid_keyboard_type_raises(self):
        """Invalid keyboard type should raise ValueError."""
        with pytest.raises(ValueError):
            build_keyboard("INVALID_TYPE")  # type: ignore


class TestKeyboardHasHelpButton:
    """Tests for help button presence per FR-008."""

    # Keyboard types that should have help buttons
    HELP_REQUIRED_TYPES = [
        KeyboardType.SESSION_ACTIVE,
        KeyboardType.SESSION_EMPTY,
        KeyboardType.RESULTS,
        KeyboardType.SESSION_CONFLICT,
        KeyboardType.ERROR_RECOVERY,
        KeyboardType.TIMEOUT,
    ]
    
    # Keyboard types that may not have help (contextual)
    HELP_OPTIONAL_TYPES = [
        KeyboardType.PROCESSING,  # Only has cancel
        KeyboardType.PAGINATION,  # Navigation focused
        KeyboardType.HELP_CONTEXT,  # Already showing help
        KeyboardType.CONFIRMATION,  # Dynamic, depends on options
    ]

    @pytest.mark.parametrize("keyboard_type", HELP_REQUIRED_TYPES)
    def test_required_keyboards_have_help(self, keyboard_type: KeyboardType):
        """Keyboards that require help button should have it."""
        keyboard = build_keyboard(keyboard_type)
        assert keyboard_has_help_button(keyboard), f"{keyboard_type} should have help button"


class TestSessionActiveKeyboard:
    """Tests for SESSION_ACTIVE keyboard."""

    def test_has_finalize_button(self):
        """SESSION_ACTIVE should have Finalize button."""
        keyboard = build_keyboard(KeyboardType.SESSION_ACTIVE)
        callback_datas = [
            btn.callback_data 
            for row in keyboard.inline_keyboard 
            for btn in row
        ]
        assert "action:finalize" in callback_datas

    def test_has_status_button(self):
        """SESSION_ACTIVE should have Status button."""
        keyboard = build_keyboard(KeyboardType.SESSION_ACTIVE)
        callback_datas = [
            btn.callback_data 
            for row in keyboard.inline_keyboard 
            for btn in row
        ]
        assert "action:status" in callback_datas

    def test_simplified_removes_emojis(self):
        """Simplified mode should remove emojis from labels."""
        normal = build_keyboard(KeyboardType.SESSION_ACTIVE, simplified=False)
        simplified = build_keyboard(KeyboardType.SESSION_ACTIVE, simplified=True)
        
        normal_labels = [
            btn.text for row in normal.inline_keyboard for btn in row
        ]
        simplified_labels = [
            btn.text for row in simplified.inline_keyboard for btn in row
        ]
        
        # Simplified labels should not have emojis (✅, 📊, ❓)
        assert any("✅" in label or "📊" in label or "❓" in label for label in normal_labels)
        assert not any("✅" in label or "📊" in label or "❓" in label for label in simplified_labels)


class TestPaginationKeyboard:
    """Tests for PAGINATION keyboard."""

    def test_first_page_no_previous(self):
        """First page should not have Previous button."""
        keyboard = build_keyboard(
            KeyboardType.PAGINATION,
            current_page=1,
            total_pages=3,
        )
        callback_datas = [
            btn.callback_data 
            for row in keyboard.inline_keyboard 
            for btn in row
        ]
        assert "page:0" not in callback_datas

    def test_last_page_no_next(self):
        """Last page should not have Next button."""
        keyboard = build_keyboard(
            KeyboardType.PAGINATION,
            current_page=3,
            total_pages=3,
        )
        callback_datas = [
            btn.callback_data 
            for row in keyboard.inline_keyboard 
            for btn in row
        ]
        assert "page:4" not in callback_datas

    def test_middle_page_has_both(self):
        """Middle pages should have both Previous and Next."""
        keyboard = build_keyboard(
            KeyboardType.PAGINATION,
            current_page=2,
            total_pages=3,
        )
        callback_datas = [
            btn.callback_data 
            for row in keyboard.inline_keyboard 
            for btn in row
        ]
        assert "page:1" in callback_datas  # Previous
        assert "page:3" in callback_datas  # Next

    def test_page_indicator_shows_current(self):
        """Page indicator should show current/total."""
        keyboard = build_keyboard(
            KeyboardType.PAGINATION,
            current_page=2,
            total_pages=5,
        )
        labels = [
            btn.text for row in keyboard.inline_keyboard for btn in row
        ]
        assert "2/5" in labels


class TestConfirmationKeyboard:
    """Tests for CONFIRMATION keyboard."""

    def test_builds_from_context(self):
        """Should build buttons from confirmation context."""
        context = ConfirmationContext(
            confirmation_type=ConfirmationType.SESSION_CONFLICT,
            options=[
                ConfirmationOption(label="Yes", callback_data="confirm:yes"),
                ConfirmationOption(label="No", callback_data="confirm:no"),
            ],
        )
        keyboard = build_keyboard(KeyboardType.CONFIRMATION, confirmation_context=context)
        
        callback_datas = [
            btn.callback_data 
            for row in keyboard.inline_keyboard 
            for btn in row
        ]
        assert "confirm:yes" in callback_datas
        assert "confirm:no" in callback_datas

    def test_fallback_without_context(self):
        """Should have fallback if no context provided."""
        keyboard = build_keyboard(KeyboardType.CONFIRMATION)
        
        assert len(keyboard.inline_keyboard) > 0


class TestRecoveryKeyboard:
    """Tests for recovery keyboard."""

    def test_has_resume_button(self):
        """Recovery keyboard should have Resume button."""
        keyboard = build_recovery_keyboard()
        callback_datas = [
            btn.callback_data 
            for row in keyboard.inline_keyboard 
            for btn in row
        ]
        assert "action:resume_session" in callback_datas

    def test_has_finalize_button(self):
        """Recovery keyboard should have Finalize button."""
        keyboard = build_recovery_keyboard()
        callback_datas = [
            btn.callback_data 
            for row in keyboard.inline_keyboard 
            for btn in row
        ]
        assert "action:finalize_orphan" in callback_datas

    def test_has_discard_button(self):
        """Recovery keyboard should have Discard button."""
        keyboard = build_recovery_keyboard()
        callback_datas = [
            btn.callback_data 
            for row in keyboard.inline_keyboard 
            for btn in row
        ]
        assert "action:discard_orphan" in callback_datas

    def test_has_help_button(self):
        """Recovery keyboard should have Help button."""
        keyboard = build_recovery_keyboard()
        assert keyboard_has_help_button(keyboard)


class TestButtonLabelsExternalized:
    """Verify button labels come from messages.py (Constitution Principle V)."""

    def test_labels_not_hardcoded(self):
        """Labels should come from messages module, not be hardcoded."""
        from src.lib import messages
        
        keyboard = build_keyboard(KeyboardType.SESSION_ACTIVE)
        
        # Get all labels from keyboard
        labels = [btn.text for row in keyboard.inline_keyboard for btn in row]
        
        # Verify labels match messages module
        expected_labels = [
            messages.BUTTON_FINALIZE,
            messages.BUTTON_STATUS,
            messages.BUTTON_HELP,
        ]
        
        for label in labels:
            assert label in expected_labels, f"Label '{label}' not from messages module"
