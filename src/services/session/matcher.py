"""Session matcher for natural language session references.

This module implements the SessionMatcher contract for resolving
user references like "monthly report" to actual session IDs.

Following research.md decision: Hybrid substring + semantic matching
with exact → fuzzy → semantic cascade.
"""

import logging
from abc import ABC, abstractmethod
from typing import Optional

from src.lib.embedding import cosine_similarity, get_embedding_service
from src.models.session import MatchType, SessionMatch

logger = logging.getLogger(__name__)


class SessionMatcher(ABC):
    """
    Contract for resolving natural language session references.

    Implementations should follow the resolution algorithm in data-model.md:
    1. Empty reference → use active session
    2. Exact substring match
    3. Fuzzy substring match (Levenshtein ≤ 2)
    4. Semantic similarity match (cosine > 0.7)
    """

    @abstractmethod
    def resolve(
        self,
        reference: str,
        active_session_id: Optional[str] = None
    ) -> SessionMatch:
        """
        Resolve a natural language reference to a session.

        Args:
            reference: User's natural language reference
            active_session_id: Currently active session (for empty refs)

        Returns:
            SessionMatch with resolved session or ambiguity info
        """
        pass

    @abstractmethod
    def rebuild_index(self) -> None:
        """
        Rebuild the session index from storage.

        Called on startup and when sessions are modified.
        """
        pass

    @abstractmethod
    def update_session(
        self,
        session_id: str,
        intelligible_name: str,
        embedding: Optional[list[float]] = None
    ) -> None:
        """
        Update index entry for a session.

        Args:
            session_id: Session to update
            intelligible_name: Current session name
            embedding: Precomputed embedding (optional)
        """
        pass

    @abstractmethod
    def remove_session(self, session_id: str) -> None:
        """
        Remove session from index.

        Args:
            session_id: Session to remove
        """
        pass


def levenshtein_distance(s1: str, s2: str) -> int:
    """
    Compute Levenshtein (edit) distance between two strings.

    Args:
        s1: First string
        s2: Second string

    Returns:
        Minimum number of single-character edits
    """
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)

    if len(s2) == 0:
        return len(s1)

    previous_row = range(len(s2) + 1)

    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            # Insertions, deletions, substitutions
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    return previous_row[-1]


class DefaultSessionMatcher(SessionMatcher):
    """
    Default implementation of SessionMatcher.

    Maintains an in-memory index of session names and embeddings
    for fast lookup. Index is rebuilt from storage on startup.
    """

    FUZZY_MAX_DISTANCE = 2
    SEMANTIC_THRESHOLD = 0.7

    def __init__(self):
        """Initialize matcher with empty index."""
        # Index: session_id -> (intelligible_name, embedding)
        self._index: dict[str, tuple[str, Optional[list[float]]]] = {}

    def resolve(
        self,
        reference: str,
        active_session_id: Optional[str] = None
    ) -> SessionMatch:
        """Resolve reference using cascading match strategy."""
        reference = reference.strip()

        # Step 1: Empty reference → use active session
        if not reference:
            if active_session_id and active_session_id in self._index:
                return SessionMatch(
                    session_id=active_session_id,
                    confidence=1.0,
                    match_type=MatchType.ACTIVE_CONTEXT,
                    candidates=[]
                )
            return SessionMatch(
                session_id=None,
                confidence=0.0,
                match_type=MatchType.NOT_FOUND,
                candidates=[]
            )

        reference_lower = reference.lower()

        # Step 2a: Exact ID match (highest priority)
        if reference in self._index:
            return SessionMatch(
                session_id=reference,
                confidence=1.0,
                match_type=MatchType.EXACT_SUBSTRING,
                candidates=[]
            )
        
        # Step 2b: ID substring match
        id_matches = []
        for session_id in self._index.keys():
            if reference_lower in session_id.lower():
                id_matches.append(session_id)
        
        if len(id_matches) == 1:
            return SessionMatch(
                session_id=id_matches[0],
                confidence=1.0,
                match_type=MatchType.EXACT_SUBSTRING,
                candidates=[]
            )
        
        if len(id_matches) > 1:
            return SessionMatch(
                session_id=None,
                confidence=0.9,
                match_type=MatchType.AMBIGUOUS,
                candidates=id_matches
            )

        # Step 3: Exact name substring match
        exact_matches = []
        for session_id, (name, _) in self._index.items():
            if reference_lower in name.lower():
                exact_matches.append(session_id)

        if len(exact_matches) == 1:
            return SessionMatch(
                session_id=exact_matches[0],
                confidence=1.0,
                match_type=MatchType.EXACT_SUBSTRING,
                candidates=[]
            )

        if len(exact_matches) > 1:
            return SessionMatch(
                session_id=None,
                confidence=0.9,
                match_type=MatchType.AMBIGUOUS,
                candidates=exact_matches
            )

        # Step 3: Fuzzy substring match (Levenshtein ≤ 2)
        fuzzy_matches = []
        for session_id, (name, _) in self._index.items():
            # Check if any word in the name is within edit distance
            name_words = name.lower().split()
            ref_words = reference_lower.split()

            for ref_word in ref_words:
                for name_word in name_words:
                    if levenshtein_distance(ref_word, name_word) <= self.FUZZY_MAX_DISTANCE:
                        fuzzy_matches.append(session_id)
                        break
                else:
                    continue
                break

        if len(fuzzy_matches) == 1:
            return SessionMatch(
                session_id=fuzzy_matches[0],
                confidence=0.9,
                match_type=MatchType.FUZZY_SUBSTRING,
                candidates=[]
            )

        if len(fuzzy_matches) > 1:
            return SessionMatch(
                session_id=None,
                confidence=0.8,
                match_type=MatchType.AMBIGUOUS,
                candidates=list(set(fuzzy_matches))
            )

        # Step 4: Semantic similarity match
        semantic_matches = self._find_semantic_matches(reference)

        if len(semantic_matches) >= 1:
            # Sort by similarity (descending)
            semantic_matches.sort(key=lambda x: x[1], reverse=True)
            best_id, best_score = semantic_matches[0]

            # If multiple matches are close in score, it's ambiguous
            if len(semantic_matches) > 1:
                second_score = semantic_matches[1][1]
                if second_score > best_score - 0.1:  # Within 10% similarity
                    return SessionMatch(
                        session_id=None,
                        confidence=best_score,
                        match_type=MatchType.AMBIGUOUS,
                        candidates=[m[0] for m in semantic_matches[:3]]
                    )

            return SessionMatch(
                session_id=best_id,
                confidence=best_score,
                match_type=MatchType.SEMANTIC_SIMILARITY,
                candidates=[]
            )

        # Step 5: No match found
        return SessionMatch(
            session_id=None,
            confidence=0.0,
            match_type=MatchType.NOT_FOUND,
            candidates=[]
        )

    def _find_semantic_matches(
        self,
        reference: str
    ) -> list[tuple[str, float]]:
        """Find sessions matching by semantic similarity."""
        matches = []

        try:
            embedding_service = get_embedding_service()
            ref_embedding = embedding_service.embed(reference)

            for session_id, (_, session_embedding) in self._index.items():
                if session_embedding is None:
                    continue

                similarity = cosine_similarity(ref_embedding, session_embedding)
                if similarity > self.SEMANTIC_THRESHOLD:
                    matches.append((session_id, similarity))

        except Exception as e:
            logger.warning(f"Semantic matching failed: {e}")
            # Fall through with empty matches

        return matches

    def rebuild_index(self) -> None:
        """Rebuild index - to be called with session data."""
        # Note: This is a stub - actual implementation will be called
        # by SessionManager with session data
        logger.info("Rebuilding session index")
        self._index.clear()

    def update_session(
        self,
        session_id: str,
        intelligible_name: str,
        embedding: Optional[list[float]] = None
    ) -> None:
        """Update index entry for a session."""
        self._index[session_id] = (intelligible_name, embedding)
        logger.debug(f"Updated index for session {session_id}: {intelligible_name}")

    def remove_session(self, session_id: str) -> None:
        """Remove session from index."""
        if session_id in self._index:
            del self._index[session_id]
            logger.debug(f"Removed session {session_id} from index")

    def get_all_names(self) -> set[str]:
        """Get all session names in the index (for uniqueness check)."""
        return {name for name, _ in self._index.values()}


# Singleton instance
_session_matcher: Optional[DefaultSessionMatcher] = None


def get_session_matcher() -> DefaultSessionMatcher:
    """
    Get the singleton SessionMatcher instance.

    Returns:
        The shared SessionMatcher instance
    """
    global _session_matcher

    if _session_matcher is None:
        _session_matcher = DefaultSessionMatcher()

    return _session_matcher
