"""Unit tests for UIPreferences.

Per tasks.md T037 for 007-contextual-oracle-feedback.

Tests preference serialization and persistence.
"""

import pytest

from src.models.ui_state import UIPreferences


class TestUIPreferencesDefaults:
    """Tests for default values."""
    
    def test_default_simplified_ui(self):
        """Default simplified_ui is False."""
        prefs = UIPreferences()
        
        assert prefs.simplified_ui is False
    
    def test_default_include_llm_history(self):
        """Default include_llm_history is True."""
        prefs = UIPreferences()
        
        assert prefs.include_llm_history is True
    
    def test_custom_values(self):
        """Can set custom values."""
        prefs = UIPreferences(
            simplified_ui=True,
            include_llm_history=False,
        )
        
        assert prefs.simplified_ui is True
        assert prefs.include_llm_history is False


class TestUIPreferencesSerialization:
    """Tests for to_dict and from_dict."""
    
    def test_to_dict_default(self):
        """to_dict includes all fields with defaults."""
        prefs = UIPreferences()
        
        result = prefs.to_dict()
        
        assert result == {
            "simplified_ui": False,
            "include_llm_history": True,
        }
    
    def test_to_dict_custom(self):
        """to_dict includes custom values."""
        prefs = UIPreferences(
            simplified_ui=True,
            include_llm_history=False,
        )
        
        result = prefs.to_dict()
        
        assert result == {
            "simplified_ui": True,
            "include_llm_history": False,
        }
    
    def test_from_dict_full(self):
        """from_dict restores all fields."""
        data = {
            "simplified_ui": True,
            "include_llm_history": False,
        }
        
        prefs = UIPreferences.from_dict(data)
        
        assert prefs.simplified_ui is True
        assert prefs.include_llm_history is False
    
    def test_from_dict_partial(self):
        """from_dict uses defaults for missing fields."""
        data = {"simplified_ui": True}  # Missing include_llm_history
        
        prefs = UIPreferences.from_dict(data)
        
        assert prefs.simplified_ui is True
        assert prefs.include_llm_history is True  # Default
    
    def test_from_dict_empty(self):
        """from_dict with empty dict uses all defaults."""
        prefs = UIPreferences.from_dict({})
        
        assert prefs.simplified_ui is False
        assert prefs.include_llm_history is True
    
    def test_roundtrip(self):
        """to_dict and from_dict are inverses."""
        original = UIPreferences(
            simplified_ui=True,
            include_llm_history=False,
        )
        
        data = original.to_dict()
        restored = UIPreferences.from_dict(data)
        
        assert restored.simplified_ui == original.simplified_ui
        assert restored.include_llm_history == original.include_llm_history


class TestUIPreferencesBackwardCompatibility:
    """Tests for backward compatibility with older session data."""
    
    def test_missing_include_llm_history_defaults_true(self):
        """
        Sessions saved before 007 feature won't have include_llm_history.
        It should default to True.
        """
        old_session_data = {"simplified_ui": False}
        
        prefs = UIPreferences.from_dict(old_session_data)
        
        assert prefs.include_llm_history is True
    
    def test_extra_fields_ignored(self):
        """Unknown fields in dict are ignored."""
        data = {
            "simplified_ui": True,
            "include_llm_history": False,
            "unknown_field": "some_value",
            "another_unknown": 42,
        }
        
        prefs = UIPreferences.from_dict(data)
        
        assert prefs.simplified_ui is True
        assert prefs.include_llm_history is False
        # No error raised for unknown fields
