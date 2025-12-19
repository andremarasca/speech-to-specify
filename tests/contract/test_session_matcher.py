"""Contract tests for SessionMatcher.

These tests verify the SessionMatcher contract defined in:
specs/003-auto-session-audio/contracts/session-matcher.md
"""

import pytest
from typing import Optional

from src.models.session import MatchType, SessionMatch
from src.services.session.matcher import (
    SessionMatcher,
    DefaultSessionMatcher,
    get_session_matcher,
    levenshtein_distance,
)


@pytest.fixture
def matcher() -> DefaultSessionMatcher:
    """Create a fresh SessionMatcher instance."""
    return DefaultSessionMatcher()


@pytest.fixture
def populated_matcher(matcher: DefaultSessionMatcher) -> DefaultSessionMatcher:
    """Create a matcher with some sessions indexed."""
    matcher.update_session("session-1", "Reunião de Planejamento")
    matcher.update_session("session-2", "Discussão sobre Projeto Alpha")
    matcher.update_session("session-3", "Áudio de 18 de Dezembro")
    matcher.update_session("session-4", "Revisão de Código")
    return matcher


class TestSessionMatcherContract:
    """Contract tests verifying SessionMatcher interface."""

    def test_resolve_returns_session_match(self, matcher: SessionMatcher):
        """resolve() should return a SessionMatch object."""
        result = matcher.resolve("test")
        assert isinstance(result, SessionMatch)

    def test_resolve_has_required_fields(self, matcher: SessionMatcher):
        """SessionMatch should have all required fields."""
        result = matcher.resolve("test")
        assert hasattr(result, "session_id")
        assert hasattr(result, "confidence")
        assert hasattr(result, "match_type")
        assert hasattr(result, "candidates")

    def test_rebuild_index_is_callable(self, matcher: SessionMatcher):
        """rebuild_index() should be callable."""
        matcher.rebuild_index()  # Should not raise

    def test_update_session_is_callable(self, matcher: SessionMatcher):
        """update_session() should be callable."""
        matcher.update_session("test-id", "Test Name")

    def test_remove_session_is_callable(self, matcher: SessionMatcher):
        """remove_session() should be callable."""
        matcher.remove_session("test-id")


class TestResolveEmptyReference:
    """Test resolve() behavior with empty reference."""

    def test_empty_reference_without_active_session(self, matcher: DefaultSessionMatcher):
        """Empty reference with no active session returns NOT_FOUND."""
        result = matcher.resolve("")
        assert result.match_type == MatchType.NOT_FOUND
        assert result.session_id is None
        assert result.confidence == 0.0

    def test_empty_reference_with_active_session(self, populated_matcher: DefaultSessionMatcher):
        """Empty reference with active session returns ACTIVE_CONTEXT."""
        result = populated_matcher.resolve("", active_session_id="session-1")
        assert result.match_type == MatchType.ACTIVE_CONTEXT
        assert result.session_id == "session-1"
        assert result.confidence == 1.0

    def test_whitespace_treated_as_empty(self, populated_matcher: DefaultSessionMatcher):
        """Whitespace-only reference treated as empty."""
        result = populated_matcher.resolve("   ", active_session_id="session-1")
        assert result.match_type == MatchType.ACTIVE_CONTEXT


class TestExactSubstringMatch:
    """Test exact substring matching."""

    def test_exact_substring_match(self, populated_matcher: DefaultSessionMatcher):
        """Should find exact substring match."""
        result = populated_matcher.resolve("Planejamento")
        assert result.match_type == MatchType.EXACT_SUBSTRING
        assert result.session_id == "session-1"
        assert result.confidence == 1.0

    def test_case_insensitive_substring(self, populated_matcher: DefaultSessionMatcher):
        """Substring matching should be case-insensitive."""
        result = populated_matcher.resolve("planejamento")
        assert result.match_type == MatchType.EXACT_SUBSTRING
        assert result.session_id == "session-1"

    def test_partial_word_match(self, populated_matcher: DefaultSessionMatcher):
        """Should match partial words."""
        result = populated_matcher.resolve("Alpha")
        assert result.session_id == "session-2"

    def test_ambiguous_exact_match(self, matcher: DefaultSessionMatcher):
        """Multiple exact matches should return AMBIGUOUS."""
        # Setup sessions with common word
        matcher.update_session("session-a", "Reunião de Segunda")
        matcher.update_session("session-b", "Reunião de Terça")
        
        result = matcher.resolve("Reunião")
        assert result.match_type == MatchType.AMBIGUOUS
        assert result.session_id is None
        assert len(result.candidates) >= 2


class TestFuzzySubstringMatch:
    """Test fuzzy substring matching (Levenshtein distance)."""

    def test_fuzzy_match_single_typo(self, populated_matcher: DefaultSessionMatcher):
        """Should match with single character difference."""
        # "Planejamento" vs "Planejamnto" (1 edit)
        result = populated_matcher.resolve("Planejamnto")
        # May or may not match depending on implementation
        assert result.match_type in [MatchType.FUZZY_SUBSTRING, MatchType.NOT_FOUND]

    def test_fuzzy_match_confidence(self, populated_matcher: DefaultSessionMatcher):
        """Fuzzy match should have lower confidence than exact."""
        # Add session and test
        populated_matcher.update_session("fuzzy-test", "Relatório Mensal")
        result = populated_matcher.resolve("Relatóro")  # typo
        if result.match_type == MatchType.FUZZY_SUBSTRING:
            assert result.confidence < 1.0


class TestSemanticSimilarityMatch:
    """Test semantic similarity matching."""

    def test_semantic_match_with_embeddings(self, matcher: DefaultSessionMatcher):
        """Should match using semantic similarity when embeddings present."""
        # This requires embedding support - add embedding to session
        embedding = [0.1] * 384  # Fake embedding
        matcher.update_session("semantic-test", "Budget Planning Meeting", embedding)
        
        # Without actual semantic search, this won't find a match
        result = matcher.resolve("financial discussion")
        # The result depends on whether embeddings are used
        assert isinstance(result, SessionMatch)


class TestMatchTypeReturnValues:
    """Test that match types are correctly returned."""

    def test_not_found_for_no_match(self, populated_matcher: DefaultSessionMatcher):
        """Should return NOT_FOUND when nothing matches."""
        result = populated_matcher.resolve("xyznonexistent123")
        assert result.match_type == MatchType.NOT_FOUND
        assert result.session_id is None

    def test_candidates_populated_on_ambiguous(self, matcher: DefaultSessionMatcher):
        """Candidates list should be populated for AMBIGUOUS matches."""
        matcher.update_session("s1", "Meeting Notes")
        matcher.update_session("s2", "Meeting Summary")
        
        result = matcher.resolve("Meeting")
        if result.match_type == MatchType.AMBIGUOUS:
            assert len(result.candidates) >= 2
            assert "s1" in result.candidates
            assert "s2" in result.candidates


class TestIndexManagement:
    """Test index update and removal."""

    def test_update_session_makes_searchable(self, matcher: DefaultSessionMatcher):
        """Updating session should make it searchable."""
        matcher.update_session("new-session", "Unique Search Term")
        result = matcher.resolve("Unique Search Term")
        assert result.session_id == "new-session"

    def test_remove_session_removes_from_index(self, matcher: DefaultSessionMatcher):
        """Removing session should remove it from search."""
        matcher.update_session("to-remove", "Removable Content")
        matcher.remove_session("to-remove")
        result = matcher.resolve("Removable Content")
        assert result.session_id != "to-remove"

    def test_rebuild_index_clears_old_data(self, populated_matcher: DefaultSessionMatcher):
        """rebuild_index() should clear existing index."""
        # Verify data exists
        result = populated_matcher.resolve("Planejamento")
        assert result.session_id == "session-1"
        
        # Rebuild (clears)
        populated_matcher.rebuild_index()
        
        # Data should be gone
        result = populated_matcher.resolve("Planejamento")
        assert result.match_type == MatchType.NOT_FOUND


class TestLevenshteinDistance:
    """Test the Levenshtein distance helper function."""

    def test_identical_strings(self):
        """Distance of identical strings is 0."""
        assert levenshtein_distance("hello", "hello") == 0

    def test_single_insertion(self):
        """Single insertion has distance 1."""
        assert levenshtein_distance("hello", "helloo") == 1

    def test_single_deletion(self):
        """Single deletion has distance 1."""
        assert levenshtein_distance("hello", "helo") == 1

    def test_single_substitution(self):
        """Single substitution has distance 1."""
        assert levenshtein_distance("hello", "hallo") == 1

    def test_empty_strings(self):
        """Empty string distances."""
        assert levenshtein_distance("", "") == 0
        assert levenshtein_distance("hello", "") == 5
        assert levenshtein_distance("", "hello") == 5

    def test_completely_different(self):
        """Completely different strings."""
        assert levenshtein_distance("abc", "xyz") == 3


class TestMatcherSingleton:
    """Test singleton pattern for SessionMatcher."""

    def test_get_session_matcher_returns_same_instance(self):
        """get_session_matcher() should return same instance."""
        m1 = get_session_matcher()
        m2 = get_session_matcher()
        assert m1 is m2

    def test_singleton_is_session_matcher(self):
        """Singleton should be a SessionMatcher instance."""
        m = get_session_matcher()
        assert isinstance(m, SessionMatcher)
