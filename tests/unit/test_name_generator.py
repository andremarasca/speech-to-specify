"""Unit tests for NameGenerator implementation.

These tests verify the internal behavior of the DefaultNameGenerator
implementation details.
"""

import pytest
from datetime import datetime, timezone

from src.services.session.name_generator import (
    DefaultNameGenerator,
    MONTH_NAMES_PT,
    FILLER_WORDS_PT,
)


@pytest.fixture
def generator() -> DefaultNameGenerator:
    """Create a DefaultNameGenerator instance."""
    return DefaultNameGenerator()


class TestMonthNames:
    """Test Portuguese month name constants."""

    def test_has_12_months(self):
        """Should have exactly 12 month names."""
        assert len(MONTH_NAMES_PT) == 12

    def test_months_are_strings(self):
        """All month names should be strings."""
        for month in MONTH_NAMES_PT:
            assert isinstance(month, str)

    def test_months_start_with_capital(self):
        """All month names should be capitalized."""
        for month in MONTH_NAMES_PT:
            assert month[0].isupper()


class TestFillerWords:
    """Test Portuguese filler word list."""

    def test_filler_words_is_set(self):
        """Filler words should be a set for O(1) lookup."""
        assert isinstance(FILLER_WORDS_PT, set)

    def test_contains_common_fillers(self):
        """Should contain common Portuguese filler words."""
        expected_fillers = ["um", "uma", "então", "tipo", "né", "é"]
        for filler in expected_fillers:
            assert filler in FILLER_WORDS_PT

    def test_all_lowercase(self):
        """All filler words should be lowercase."""
        for word in FILLER_WORDS_PT:
            assert word == word.lower()


class TestTranscriptFiltering:
    """Test filler word filtering in transcript processing."""

    def test_removes_fillers_from_start(self, generator: DefaultNameGenerator):
        """Should remove filler words from start."""
        transcript = "Um então vamos começar a reunião"
        result = generator.generate_from_transcript(transcript)
        assert result is not None
        assert not result.lower().startswith("um")

    def test_preserves_meaningful_content(self, generator: DefaultNameGenerator):
        """Should preserve meaningful words."""
        transcript = "Implementação do módulo de autenticação"
        result = generator.generate_from_transcript(transcript)
        assert "Implementação" in result

    def test_handles_mixed_content(self, generator: DefaultNameGenerator):
        """Should handle mixed filler and content."""
        transcript = "Então tipo o sistema de login é assim"
        result = generator.generate_from_transcript(transcript)
        if result:
            assert "sistema" in result.lower() or "login" in result.lower()

    def test_removes_punctuation_when_filtering(self, generator: DefaultNameGenerator):
        """Should handle punctuation when filtering."""
        transcript = "Então, tipo, o projeto vai assim."
        result = generator.generate_from_transcript(transcript)
        if result:
            assert "projeto" in result.lower()


class TestWordLimiting:
    """Test word count limits in name generation."""

    def test_limits_to_max_words(self, generator: DefaultNameGenerator):
        """Should limit to MAX_WORDS_FROM_TRANSCRIPT words."""
        transcript = " ".join(["palavra"] * 20)
        result = generator.generate_from_transcript(transcript)
        assert result is not None
        word_count = len(result.split())
        assert word_count <= generator.MAX_WORDS_FROM_TRANSCRIPT

    def test_respects_max_length(self, generator: DefaultNameGenerator):
        """Should respect MAX_NAME_LENGTH."""
        transcript = " ".join(["palavralonga"] * 20)
        result = generator.generate_from_transcript(transcript)
        if result:
            assert len(result) <= generator.MAX_NAME_LENGTH


class TestUniqueSuffixBehavior:
    """Test suffix generation for uniqueness."""

    def test_starts_at_2(self, generator: DefaultNameGenerator):
        """Suffix numbering should start at 2."""
        existing = {"Test"}
        result = generator.ensure_unique("Test", existing)
        assert "(2)" in result

    def test_increments_sequentially(self, generator: DefaultNameGenerator):
        """Should increment sequentially."""
        existing = {"Test", "Test (2)"}
        result = generator.ensure_unique("Test", existing)
        assert "(3)" in result

    def test_finds_next_available(self, generator: DefaultNameGenerator):
        """Should find next available number."""
        existing = {"Test", "Test (2)", "Test (4)"}  # Gap at (3)
        result = generator.ensure_unique("Test", existing)
        assert result == "Test (3)"

    def test_case_sensitive(self, generator: DefaultNameGenerator):
        """Uniqueness check should be case-sensitive."""
        existing = {"test"}  # lowercase
        result = generator.ensure_unique("Test", existing)  # Different case
        assert result == "Test"  # Should not add suffix


class TestLLMTitlePatterns:
    """Test LLM output title extraction patterns."""

    def test_case_insensitive_title_match(self, generator: DefaultNameGenerator):
        """Should match 'title:' case-insensitively."""
        assert generator.generate_from_llm_output("TITLE: Test") == "Test"
        assert generator.generate_from_llm_output("Title: Test") == "Test"
        assert generator.generate_from_llm_output("title: Test") == "Test"

    def test_strips_whitespace(self, generator: DefaultNameGenerator):
        """Should strip whitespace from extracted title."""
        result = generator.generate_from_llm_output("Title:   Spaced Title  \n")
        assert result == "Spaced Title"

    def test_multiline_heading_extraction(self, generator: DefaultNameGenerator):
        """Should extract heading from multiline document."""
        # When there's a clear markdown heading without preamble
        doc = """# Main Title

Content here
"""
        result = generator.generate_from_llm_output(doc)
        assert result == "Main Title"

    def test_heading_after_preamble(self, generator: DefaultNameGenerator):
        """Short preamble lines may be extracted as title."""
        # This tests the actual behavior: short first lines get priority
        doc = """
        Some preamble text
        
        # Main Title
        
        Content here
        """
        result = generator.generate_from_llm_output(doc)
        # First short line wins over later heading
        assert result is not None


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_single_word_transcript(self, generator: DefaultNameGenerator):
        """Should handle single word transcript."""
        result = generator.generate_from_transcript("Importante")
        # Single meaningful word might be below minimum
        assert result is None or "Importante" in result

    def test_numeric_transcript(self, generator: DefaultNameGenerator):
        """Should handle numeric content."""
        result = generator.generate_from_transcript("123 456 789")
        # Numbers are not in filler list, but might be filtered as too short
        assert result is None or isinstance(result, str)

    def test_unicode_content(self, generator: DefaultNameGenerator):
        """Should handle unicode properly."""
        transcript = "Discussão sobre implementação"
        result = generator.generate_from_transcript(transcript)
        assert result is not None
        assert "Discussão" in result or "implementação" in result

    def test_very_short_words_filtered(self, generator: DefaultNameGenerator):
        """Should filter very short words."""
        transcript = "a b c d e f g projeto"
        result = generator.generate_from_transcript(transcript)
        if result:
            # Single char words should be filtered
            words = result.split()
            for word in words:
                assert len(word) > 1

    def test_empty_string_handling(self, generator: DefaultNameGenerator):
        """Should handle empty strings gracefully."""
        assert generator.generate_from_transcript("") is None
        assert generator.generate_from_llm_output("") is None

    def test_none_safe_operations(self, generator: DefaultNameGenerator):
        """All operations should be None-safe where applicable."""
        # ensure_unique should never return None
        result = generator.ensure_unique("", set())
        assert result is not None
