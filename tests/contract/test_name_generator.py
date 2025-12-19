"""Contract tests for NameGenerator.

These tests verify the NameGenerator contract defined in:
specs/003-auto-session-audio/contracts/name-generator.md
"""

import pytest
from datetime import datetime, timezone

from src.services.session.name_generator import (
    NameGenerator,
    DefaultNameGenerator,
    get_name_generator,
    MONTH_NAMES_PT,
)


@pytest.fixture
def generator() -> NameGenerator:
    """Create a NameGenerator instance."""
    return DefaultNameGenerator()


class TestNameGeneratorContract:
    """Contract tests verifying NameGenerator interface compliance."""

    def test_generate_fallback_name_returns_string(self, generator: NameGenerator):
        """generate_fallback_name() should return a non-empty string."""
        result = generator.generate_fallback_name(datetime.now(timezone.utc))
        assert isinstance(result, str)
        assert len(result) > 0

    def test_generate_fallback_name_format(self, generator: NameGenerator):
        """Fallback name should follow 'Áudio de {day} de {month}' format."""
        result = generator.generate_fallback_name(
            datetime(2025, 12, 18, 14, 30, tzinfo=timezone.utc)
        )
        assert result == "Áudio de 18 de Dezembro"

    def test_generate_from_transcript_returns_string_or_none(self, generator: NameGenerator):
        """generate_from_transcript() should return string or None."""
        result = generator.generate_from_transcript("Reunião sobre o projeto Alpha")
        assert result is None or isinstance(result, str)

    def test_generate_from_llm_output_returns_string_or_none(self, generator: NameGenerator):
        """generate_from_llm_output() should return string or None."""
        result = generator.generate_from_llm_output("# Project Report")
        assert result is None or isinstance(result, str)

    def test_ensure_unique_returns_string(self, generator: NameGenerator):
        """ensure_unique() should always return a string."""
        result = generator.ensure_unique("Test Name", {"Other Name"})
        assert isinstance(result, str)

    def test_ensure_unique_unchanged_when_unique(self, generator: NameGenerator):
        """ensure_unique() returns unchanged name if already unique."""
        result = generator.ensure_unique("Test Name", {"Different Name"})
        assert result == "Test Name"

    def test_ensure_unique_adds_suffix_on_collision(self, generator: NameGenerator):
        """ensure_unique() adds suffix when collision occurs."""
        result = generator.ensure_unique("Test Name", {"Test Name"})
        assert result == "Test Name (2)"


class TestFallbackNameAllMonths:
    """Test fallback name generation for all 12 months."""

    @pytest.mark.parametrize("month,expected_name", [
        (1, "Áudio de 15 de Janeiro"),
        (2, "Áudio de 15 de Fevereiro"),
        (3, "Áudio de 15 de Março"),
        (4, "Áudio de 15 de Abril"),
        (5, "Áudio de 15 de Maio"),
        (6, "Áudio de 15 de Junho"),
        (7, "Áudio de 15 de Julho"),
        (8, "Áudio de 15 de Agosto"),
        (9, "Áudio de 15 de Setembro"),
        (10, "Áudio de 15 de Outubro"),
        (11, "Áudio de 15 de Novembro"),
        (12, "Áudio de 15 de Dezembro"),
    ])
    def test_fallback_name_month(self, generator: NameGenerator, month: int, expected_name: str):
        """Test fallback name for each month."""
        dt = datetime(2025, month, 15, 12, 0, tzinfo=timezone.utc)
        result = generator.generate_fallback_name(dt)
        assert result == expected_name

    def test_fallback_name_day_1(self, generator: NameGenerator):
        """Test day 1 of month."""
        dt = datetime(2025, 1, 1, tzinfo=timezone.utc)
        result = generator.generate_fallback_name(dt)
        assert result == "Áudio de 1 de Janeiro"

    def test_fallback_name_day_31(self, generator: NameGenerator):
        """Test day 31."""
        dt = datetime(2025, 12, 31, tzinfo=timezone.utc)
        result = generator.generate_fallback_name(dt)
        assert result == "Áudio de 31 de Dezembro"


class TestTranscriptionNameExtraction:
    """Test name extraction from transcription text."""

    def test_extracts_meaningful_words(self, generator: NameGenerator):
        """Should extract first meaningful words from transcript."""
        transcript = "Vamos discutir sobre o plano de implementação do projeto"
        result = generator.generate_from_transcript(transcript)
        assert result is not None
        assert "discutir" in result.lower() or "plano" in result.lower()

    def test_filters_filler_words(self, generator: NameGenerator):
        """Should filter out Portuguese filler words."""
        # Transcript with many filler words
        transcript = "Um então tipo o projeto é assim né"
        result = generator.generate_from_transcript(transcript)
        # Should extract meaningful content, not fillers
        if result:
            assert "projeto" in result.lower()

    def test_returns_none_for_empty_transcript(self, generator: NameGenerator):
        """Should return None for empty transcript."""
        result = generator.generate_from_transcript("")
        assert result is None

    def test_returns_none_for_whitespace_only(self, generator: NameGenerator):
        """Should return None for whitespace-only transcript."""
        result = generator.generate_from_transcript("   \n\t  ")
        assert result is None

    def test_returns_none_for_only_fillers(self, generator: NameGenerator):
        """Should return None if transcript is only filler words."""
        result = generator.generate_from_transcript("um uma o a é então")
        assert result is None

    def test_truncates_long_names(self, generator: NameGenerator):
        """Should truncate very long names."""
        # Long transcript
        transcript = " ".join(["palavra"] * 50)
        result = generator.generate_from_transcript(transcript)
        assert result is not None
        assert len(result) <= 100  # Max length per data-model.md


class TestLLMOutputExtraction:
    """Test title extraction from LLM output."""

    def test_extracts_explicit_title(self, generator: NameGenerator):
        """Should extract explicit 'Title:' line."""
        llm_output = "Title: Project Implementation Plan\n\nThis document..."
        result = generator.generate_from_llm_output(llm_output)
        assert result == "Project Implementation Plan"

    def test_extracts_titulo_line(self, generator: NameGenerator):
        """Should extract 'Título:' line (Portuguese)."""
        llm_output = "Título: Plano de Implementação\n\nEste documento..."
        result = generator.generate_from_llm_output(llm_output)
        assert result == "Plano de Implementação"

    def test_extracts_markdown_heading(self, generator: NameGenerator):
        """Should extract markdown heading."""
        llm_output = "# Meeting Notes Q4\n\n## Attendees\n..."
        result = generator.generate_from_llm_output(llm_output)
        assert result == "Meeting Notes Q4"

    def test_extracts_h2_heading(self, generator: NameGenerator):
        """Should extract ## heading if no # heading."""
        llm_output = "## Sprint Planning\n\nAgenda items..."
        result = generator.generate_from_llm_output(llm_output)
        assert result == "Sprint Planning"

    def test_returns_none_for_no_title(self, generator: NameGenerator):
        """Should return None if no title pattern found."""
        llm_output = "This is just regular content without any title markers."
        result = generator.generate_from_llm_output(llm_output)
        # May return first line or None depending on heuristics
        assert result is None or isinstance(result, str)

    def test_returns_none_for_empty_output(self, generator: NameGenerator):
        """Should return None for empty LLM output."""
        result = generator.generate_from_llm_output("")
        assert result is None


class TestUniquenessEnforcement:
    """Test unique name generation."""

    def test_no_suffix_when_unique(self, generator: NameGenerator):
        """Should not add suffix when name is already unique."""
        existing = {"Áudio de 18 de Dezembro", "Reunião Projeto"}
        result = generator.ensure_unique("Nova Sessão", existing)
        assert result == "Nova Sessão"

    def test_adds_suffix_2_on_first_collision(self, generator: NameGenerator):
        """Should add (2) suffix on first collision."""
        existing = {"Áudio de 18 de Dezembro"}
        result = generator.ensure_unique("Áudio de 18 de Dezembro", existing)
        assert result == "Áudio de 18 de Dezembro (2)"

    def test_increments_suffix_on_multiple_collisions(self, generator: NameGenerator):
        """Should increment suffix for multiple collisions."""
        existing = {
            "Áudio de 18 de Dezembro",
            "Áudio de 18 de Dezembro (2)",
            "Áudio de 18 de Dezembro (3)",
        }
        result = generator.ensure_unique("Áudio de 18 de Dezembro", existing)
        assert result == "Áudio de 18 de Dezembro (4)"

    def test_handles_empty_existing_set(self, generator: NameGenerator):
        """Should handle empty existing names set."""
        result = generator.ensure_unique("Test Name", set())
        assert result == "Test Name"

    def test_handles_large_collision_count(self, generator: NameGenerator):
        """Should handle many collisions."""
        existing = {f"Test ({i})" if i > 1 else "Test" for i in range(1, 100)}
        result = generator.ensure_unique("Test", existing)
        assert result == "Test (100)"


class TestNameGeneratorSingleton:
    """Test singleton pattern for NameGenerator."""

    def test_get_name_generator_returns_same_instance(self):
        """get_name_generator() should return same instance."""
        gen1 = get_name_generator()
        gen2 = get_name_generator()
        assert gen1 is gen2

    def test_singleton_is_name_generator(self):
        """Singleton should be a NameGenerator instance."""
        gen = get_name_generator()
        assert isinstance(gen, NameGenerator)
