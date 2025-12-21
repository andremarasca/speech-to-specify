"""Unit tests for PromptInjector.

Per tasks.md T023 for 007-contextual-oracle-feedback.

Tests context injection into oracle prompts.
"""

import pytest
from pathlib import Path

from src.models.oracle import Oracle
from src.services.llm.prompt_injector import PromptInjector


def _make_oracle(name: str, prompt: str, placeholder: str = "{{CONTEXT}}") -> Oracle:
    """Helper to create Oracle objects for testing."""
    return Oracle(
        id="test1234",
        name=name,
        file_path=Path("/test/oracle.md"),
        prompt_content=prompt,
        placeholder=placeholder
    )


class TestPromptInjectorWithPlaceholder:
    """Tests for injection when placeholder exists."""
    
    def test_inject_replaces_placeholder(self):
        """Placeholder is replaced with context."""
        injector = PromptInjector()
        oracle = _make_oracle("Test", """# Oracle

Instructions before.

{{CONTEXT}}

Instructions after.""")
        context = "Transcript content here."
        
        result = injector.inject(oracle, context)
        
        assert "{{CONTEXT}}" not in result
        assert "Transcript content here." in result
        assert "Instructions before." in result
        assert "Instructions after." in result
    
    def test_inject_preserves_structure(self):
        """Injection preserves document structure."""
        injector = PromptInjector()
        oracle = _make_oracle("Test", """# Oracle Title

## Section 1
Some intro.

{{CONTEXT}}

## Section 2
More content.""")
        context = "Injected context."
        
        result = injector.inject(oracle, context)
        
        # Structure preserved
        assert "# Oracle Title" in result
        assert "## Section 1" in result
        assert "## Section 2" in result
        # Content in right place
        lines = result.split("\n")
        section1_idx = next(i for i, l in enumerate(lines) if "Section 1" in l)
        context_idx = next(i for i, l in enumerate(lines) if "Injected context" in l)
        section2_idx = next(i for i, l in enumerate(lines) if "Section 2" in l)
        assert section1_idx < context_idx < section2_idx
    
    def test_inject_all_occurrences(self):
        """All placeholders are replaced when multiple exist."""
        injector = PromptInjector()
        oracle = _make_oracle("Test", """{{CONTEXT}}

More content.

{{CONTEXT}}""")
        context = "My context."
        
        result = injector.inject(oracle, context)
        
        # Both placeholders are replaced (Python str.replace replaces all occurrences)
        count = result.count("My context.")
        assert count == 2
    
    def test_inject_multiline_context(self):
        """Multi-line context is injected properly."""
        injector = PromptInjector()
        oracle = _make_oracle("Test", "Before\n{{CONTEXT}}\nAfter")
        context = """Line 1
Line 2
Line 3"""
        
        result = injector.inject(oracle, context)
        
        assert "Line 1" in result
        assert "Line 2" in result
        assert "Line 3" in result
        # Order preserved
        lines = result.split("\n")
        before_idx = lines.index("Before")
        after_idx = next(i for i, l in enumerate(lines) if l == "After")
        assert before_idx < after_idx


class TestPromptInjectorWithoutPlaceholder:
    """Tests for injection when no placeholder exists."""
    
    def test_inject_appends_when_no_placeholder(self):
        """Context is appended when no placeholder found."""
        injector = PromptInjector()
        oracle = _make_oracle("Test", """# Oracle

Instructions here.

No placeholder in this template.""", placeholder="MISSING_PLACEHOLDER")
        context = "My context content."
        
        result = injector.inject(oracle, context)
        
        # Original content preserved
        assert "# Oracle" in result
        assert "Instructions here." in result
        # Context appended at the end
        assert "My context content." in result
    
    def test_inject_adds_separator_when_appending(self):
        """Double newline separator added when appending."""
        injector = PromptInjector()
        oracle = _make_oracle("Test", "Template content.", placeholder="NOT_PRESENT")
        context = "Appended context."
        
        result = injector.inject(oracle, context)
        
        # Separator between original and appended
        assert "\n\n" in result
        assert "Template content." in result
        assert "Appended context." in result


class TestPromptInjectorCustomPlaceholder:
    """Tests for custom placeholder patterns."""
    
    def test_custom_placeholder(self):
        """Custom placeholder pattern works."""
        injector = PromptInjector()
        oracle = _make_oracle("Test", "Before <<INSERT>> After", placeholder="<<INSERT>>")
        context = "Custom content"
        
        result = injector.inject(oracle, context)
        
        assert result == "Before Custom content After"
    
    def test_default_placeholder_pattern(self):
        """Default placeholder is {{CONTEXT}}."""
        injector = PromptInjector()
        oracle = _make_oracle("Test", "Test {{CONTEXT}} template")
        context = "injected"
        
        result = injector.inject(oracle, context)
        
        assert result == "Test injected template"


class TestPromptInjectorEdgeCases:
    """Edge case tests."""
    
    def test_empty_context(self):
        """Empty context replaces placeholder with nothing."""
        injector = PromptInjector()
        oracle = _make_oracle("Test", "Before {{CONTEXT}} After")
        context = ""
        
        result = injector.inject(oracle, context)
        
        assert result == "Before  After"
    
    def test_minimal_template_appends_context(self):
        """Minimal template appends context."""
        injector = PromptInjector()
        oracle = _make_oracle("Test", "X", placeholder="NOT_PRESENT")  # Minimal content
        context = "Just context"
        
        result = injector.inject(oracle, context)
        
        assert "Just context" in result
        assert "X" in result
    
    def test_context_containing_placeholder_text(self):
        """Context containing placeholder text doesn't cause issues."""
        injector = PromptInjector()
        oracle = _make_oracle("Test", "Template {{CONTEXT}} end")
        context = "Content with {{CONTEXT}} in it"
        
        result = injector.inject(oracle, context)
        
        # The placeholder in template is replaced
        # The {{CONTEXT}} in context should remain (it's literal text now)
        assert result == "Template Content with {{CONTEXT}} in it end"
    
    def test_preview_injection_point_with_placeholder(self):
        """Preview shows placeholder replacement mode."""
        injector = PromptInjector()
        oracle = _make_oracle("Test", "Content {{CONTEXT}} here")
        
        preview = injector.preview_injection_point(oracle)
        
        assert "Placeholder replacement" in preview
    
    def test_preview_injection_point_without_placeholder(self):
        """Preview shows append mode."""
        injector = PromptInjector()
        oracle = _make_oracle("Test", "No placeholder", placeholder="MISSING")
        
        preview = injector.preview_injection_point(oracle)
        
        assert "Appended at end" in preview
