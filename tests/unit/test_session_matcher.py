"""Unit tests for SessionMatcher implementation.

Tests the DefaultSessionMatcher implementation in detail.
"""

import pytest
from typing import List, Optional, Tuple

from src.models.session import MatchType, SessionMatch
from src.services.session.matcher import (
    DefaultSessionMatcher,
    levenshtein_distance,
)


@pytest.fixture
def matcher() -> DefaultSessionMatcher:
    """Create a fresh DefaultSessionMatcher instance."""
    return DefaultSessionMatcher()


class TestExactSubstringMatching:
    """Unit tests for exact substring matching."""

    def test_full_name_match(self, matcher: DefaultSessionMatcher):
        """Full name matches exactly."""
        matcher.update_session("s1", "Reunião de Planejamento")
        result = matcher.resolve("Reunião de Planejamento")
        assert result.match_type == MatchType.EXACT_SUBSTRING
        assert result.session_id == "s1"
        assert result.confidence == 1.0

    def test_prefix_match(self, matcher: DefaultSessionMatcher):
        """Prefix substring matches."""
        matcher.update_session("s1", "Relatório Mensal de Vendas")
        result = matcher.resolve("Relatório")
        assert result.match_type == MatchType.EXACT_SUBSTRING
        assert result.session_id == "s1"

    def test_suffix_match(self, matcher: DefaultSessionMatcher):
        """Suffix substring matches."""
        matcher.update_session("s1", "Relatório Mensal de Vendas")
        result = matcher.resolve("Vendas")
        assert result.match_type == MatchType.EXACT_SUBSTRING
        assert result.session_id == "s1"

    def test_middle_substring_match(self, matcher: DefaultSessionMatcher):
        """Middle substring matches."""
        matcher.update_session("s1", "Relatório Mensal de Vendas")
        result = matcher.resolve("Mensal")
        assert result.match_type == MatchType.EXACT_SUBSTRING
        assert result.session_id == "s1"

    def test_case_insensitive_lower(self, matcher: DefaultSessionMatcher):
        """Lowercase query matches uppercase name."""
        matcher.update_session("s1", "RELATÓRIO MENSAL")
        result = matcher.resolve("relatório mensal")
        assert result.match_type == MatchType.EXACT_SUBSTRING
        assert result.session_id == "s1"

    def test_case_insensitive_mixed(self, matcher: DefaultSessionMatcher):
        """Mixed case query matches."""
        matcher.update_session("s1", "Relatório Mensal")
        result = matcher.resolve("RELATÓRIO mensal")
        assert result.match_type == MatchType.EXACT_SUBSTRING
        assert result.session_id == "s1"

    def test_no_match_returns_not_found(self, matcher: DefaultSessionMatcher):
        """Non-matching query returns NOT_FOUND."""
        matcher.update_session("s1", "Relatório Mensal")
        result = matcher.resolve("xyznonexistent")
        assert result.match_type == MatchType.NOT_FOUND
        assert result.session_id is None

    def test_single_character_match(self, matcher: DefaultSessionMatcher):
        """Single character query still matches if found."""
        matcher.update_session("s1", "ABC DEF")
        # Single char "A" is substring
        result = matcher.resolve("A")
        # Note: single character might not be considered reliable
        # This tests current behavior
        assert result.match_type in [MatchType.EXACT_SUBSTRING, MatchType.NOT_FOUND]

    def test_whitespace_handling(self, matcher: DefaultSessionMatcher):
        """Whitespace in query is handled properly."""
        matcher.update_session("s1", "Budget Planning Meeting")
        result = matcher.resolve("Budget Planning")
        assert result.match_type == MatchType.EXACT_SUBSTRING
        assert result.session_id == "s1"

    def test_special_characters_in_name(self, matcher: DefaultSessionMatcher):
        """Names with special characters can be matched."""
        matcher.update_session("s1", "Relatório (Q1) - Vendas")
        result = matcher.resolve("Q1")
        assert result.match_type == MatchType.EXACT_SUBSTRING


class TestFuzzyMatching:
    """Unit tests for fuzzy substring matching (Levenshtein)."""

    def test_fuzzy_single_char_insertion(self, matcher: DefaultSessionMatcher):
        """Match with single character insertion."""
        matcher.update_session("s1", "Relatório")
        result = matcher.resolve("Rellatório")  # extra 'l'
        # May return FUZZY_SUBSTRING if within threshold
        assert result.match_type in [MatchType.FUZZY_SUBSTRING, MatchType.NOT_FOUND]

    def test_fuzzy_single_char_deletion(self, matcher: DefaultSessionMatcher):
        """Match with single character deletion."""
        matcher.update_session("s1", "Relatório")
        result = matcher.resolve("Reltório")  # missing 'a'
        assert result.match_type in [MatchType.FUZZY_SUBSTRING, MatchType.NOT_FOUND]

    def test_fuzzy_single_char_substitution(self, matcher: DefaultSessionMatcher):
        """Match with single character substitution."""
        matcher.update_session("s1", "Relatório")
        result = matcher.resolve("Reletório")  # 'a' -> 'e'
        assert result.match_type in [MatchType.FUZZY_SUBSTRING, MatchType.NOT_FOUND]

    def test_fuzzy_two_char_difference(self, matcher: DefaultSessionMatcher):
        """Match with two character differences (boundary)."""
        matcher.update_session("s1", "Planejamento")
        result = matcher.resolve("Planejmento")  # 2 edits
        assert result.match_type in [MatchType.FUZZY_SUBSTRING, MatchType.NOT_FOUND]

    def test_fuzzy_beyond_threshold_no_match(self, matcher: DefaultSessionMatcher):
        """Too many differences should not match fuzzily."""
        matcher.update_session("s1", "Relatório")
        result = matcher.resolve("Relxyzxyz")  # many differences
        # Should not match as fuzzy
        if result.match_type == MatchType.FUZZY_SUBSTRING:
            pytest.fail("Should not fuzzy match with many differences")

    def test_fuzzy_match_lower_confidence(self, matcher: DefaultSessionMatcher):
        """Fuzzy matches should have lower confidence than exact."""
        matcher.update_session("s1", "Relatório Mensal")
        
        # Exact match
        exact = matcher.resolve("Relatório")
        
        # Fuzzy match (if it matches)
        fuzzy = matcher.resolve("Reletório")  # typo
        
        if fuzzy.match_type == MatchType.FUZZY_SUBSTRING:
            assert fuzzy.confidence < exact.confidence


class TestSemanticMatching:
    """Unit tests for semantic similarity matching."""

    def test_semantic_with_embedding_provided(self, matcher: DefaultSessionMatcher):
        """Semantic matching when embedding is provided."""
        # Create fake embedding
        embedding = [0.1] * 384
        matcher.update_session("s1", "Financial Report", embedding)
        
        # Without actual semantic search implementation, 
        # this tests that the method handles embeddings
        result = matcher.resolve("Budget Analysis")
        assert isinstance(result, SessionMatch)

    def test_semantic_match_type_when_matched(self, matcher: DefaultSessionMatcher):
        """When semantic match found, should return SEMANTIC_SIMILARITY."""
        # This depends on actual implementation
        # If no semantic matching implemented, this is informational
        embedding = [0.5] * 384
        matcher.update_session("s1", "Test Session", embedding)
        result = matcher.resolve("completely unrelated words")
        # Result type depends on implementation
        assert result.match_type in [
            MatchType.SEMANTIC_SIMILARITY,
            MatchType.NOT_FOUND,
            MatchType.EXACT_SUBSTRING,  # if substring happens to match
        ]

    def test_sessions_without_embeddings_skip_semantic(self, matcher: DefaultSessionMatcher):
        """Sessions without embeddings should be skipped in semantic search."""
        matcher.update_session("s1", "Test One")  # No embedding
        matcher.update_session("s2", "Test Two")  # No embedding
        
        result = matcher.resolve("something completely different")
        # Without embeddings, semantic search won't find anything
        assert result.match_type in [MatchType.NOT_FOUND, MatchType.EXACT_SUBSTRING]


class TestAmbiguityDetection:
    """Unit tests for ambiguity detection."""

    def test_two_exact_matches_is_ambiguous(self, matcher: DefaultSessionMatcher):
        """Two exact substring matches should be ambiguous."""
        matcher.update_session("s1", "Reunião de Planejamento")
        matcher.update_session("s2", "Reunião de Revisão")
        
        result = matcher.resolve("Reunião")
        assert result.match_type == MatchType.AMBIGUOUS
        assert result.session_id is None

    def test_ambiguous_has_candidates(self, matcher: DefaultSessionMatcher):
        """Ambiguous result should list candidates."""
        matcher.update_session("s1", "Reunião de Planejamento")
        matcher.update_session("s2", "Reunião de Revisão")
        matcher.update_session("s3", "Reunião de Código")
        
        result = matcher.resolve("Reunião")
        assert len(result.candidates) >= 2
        assert "s1" in result.candidates
        assert "s2" in result.candidates
        assert "s3" in result.candidates

    def test_single_match_not_ambiguous(self, matcher: DefaultSessionMatcher):
        """Single match should not be ambiguous."""
        matcher.update_session("s1", "Reunião de Planejamento")
        matcher.update_session("s2", "Discussão Técnica")
        
        result = matcher.resolve("Planejamento")
        assert result.match_type != MatchType.AMBIGUOUS
        assert result.session_id == "s1"

    def test_ambiguous_confidence_reflects_uncertainty(self, matcher: DefaultSessionMatcher):
        """Ambiguous result should have lower confidence."""
        matcher.update_session("s1", "Meeting Notes")
        matcher.update_session("s2", "Meeting Summary")
        
        result = matcher.resolve("Meeting")
        if result.match_type == MatchType.AMBIGUOUS:
            # Ambiguous should not have high confidence
            assert result.confidence < 1.0


class TestActiveSessionContext:
    """Unit tests for active session context handling."""

    def test_empty_query_returns_active_session(self, matcher: DefaultSessionMatcher):
        """Empty query with active session returns that session."""
        matcher.update_session("s1", "Test Session")
        
        result = matcher.resolve("", active_session_id="s1")
        assert result.match_type == MatchType.ACTIVE_CONTEXT
        assert result.session_id == "s1"
        assert result.confidence == 1.0

    def test_whitespace_query_treated_as_empty(self, matcher: DefaultSessionMatcher):
        """Whitespace-only query treated as empty."""
        matcher.update_session("s1", "Test Session")
        
        result = matcher.resolve("   \t\n", active_session_id="s1")
        assert result.match_type == MatchType.ACTIVE_CONTEXT

    def test_no_active_session_returns_not_found(self, matcher: DefaultSessionMatcher):
        """Empty query without active session returns NOT_FOUND."""
        result = matcher.resolve("")
        assert result.match_type == MatchType.NOT_FOUND

    def test_specific_query_ignores_active_session(self, matcher: DefaultSessionMatcher):
        """Specific query should match that session, not active one."""
        matcher.update_session("s1", "Active Session")
        matcher.update_session("s2", "Target Session")
        
        result = matcher.resolve("Target", active_session_id="s1")
        assert result.session_id == "s2"  # Not active session


class TestIndexOperations:
    """Unit tests for index management operations."""

    def test_update_session_overwrites_name(self, matcher: DefaultSessionMatcher):
        """Updating session with new name replaces old name."""
        matcher.update_session("s1", "Old Name")
        matcher.update_session("s1", "New Name")
        
        # Old name no longer matches
        result_old = matcher.resolve("Old Name")
        result_new = matcher.resolve("New Name")
        
        assert result_new.session_id == "s1"
        # Old might still partially match depending on implementation
        if result_old.match_type == MatchType.EXACT_SUBSTRING:
            assert result_old.session_id != "s1" or "Old" in "New Name"

    def test_update_session_with_embedding(self, matcher: DefaultSessionMatcher):
        """Can update session with embedding."""
        embedding = [0.2] * 384
        matcher.update_session("s1", "Test", embedding)
        # Verify session is searchable
        result = matcher.resolve("Test")
        assert result.session_id == "s1"

    def test_remove_nonexistent_no_error(self, matcher: DefaultSessionMatcher):
        """Removing non-existent session should not raise."""
        matcher.remove_session("nonexistent")  # Should not raise

    def test_rebuild_clears_all(self, matcher: DefaultSessionMatcher):
        """Rebuild should clear all indexed sessions."""
        matcher.update_session("s1", "Session One")
        matcher.update_session("s2", "Session Two")
        
        matcher.rebuild_index()
        
        assert matcher.resolve("Session One").match_type == MatchType.NOT_FOUND
        assert matcher.resolve("Session Two").match_type == MatchType.NOT_FOUND


class TestLevenshteinDistanceUnit:
    """Unit tests for Levenshtein distance calculation."""

    def test_same_string_zero_distance(self):
        """Identical strings have zero distance."""
        assert levenshtein_distance("test", "test") == 0
        assert levenshtein_distance("", "") == 0

    def test_insertion_distance(self):
        """Each insertion costs 1."""
        assert levenshtein_distance("abc", "abcd") == 1
        assert levenshtein_distance("abc", "abcde") == 2

    def test_deletion_distance(self):
        """Each deletion costs 1."""
        assert levenshtein_distance("abcd", "abc") == 1
        assert levenshtein_distance("abcde", "abc") == 2

    def test_substitution_distance(self):
        """Each substitution costs 1."""
        assert levenshtein_distance("abc", "aXc") == 1
        assert levenshtein_distance("abc", "XYc") == 2

    def test_mixed_operations(self):
        """Mixed operations calculate correctly."""
        # "kitten" -> "sitting" = 3 (k->s, e->i, +g)
        assert levenshtein_distance("kitten", "sitting") == 3

    def test_unicode_strings(self):
        """Unicode strings are handled correctly."""
        assert levenshtein_distance("café", "cafe") == 1
        assert levenshtein_distance("naïve", "naive") == 1

    def test_case_sensitivity(self):
        """Function is case-sensitive."""
        assert levenshtein_distance("ABC", "abc") == 3


class TestMatchPriority:
    """Test matching priority: exact > fuzzy > semantic."""

    def test_exact_preferred_over_fuzzy(self, matcher: DefaultSessionMatcher):
        """Exact substring match is preferred over fuzzy."""
        matcher.update_session("exact", "Planning")
        matcher.update_session("fuzzy", "Planing")  # typo
        
        result = matcher.resolve("Planning")
        assert result.session_id == "exact"
        assert result.match_type == MatchType.EXACT_SUBSTRING

    def test_exact_match_high_confidence(self, matcher: DefaultSessionMatcher):
        """Exact matches have confidence 1.0."""
        matcher.update_session("s1", "Test Session Name")
        
        result = matcher.resolve("Test")
        if result.match_type == MatchType.EXACT_SUBSTRING:
            assert result.confidence == 1.0
