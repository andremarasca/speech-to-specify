# Contract: Session Matcher

**Module**: `src/services/session/matcher.py`  
**Feature**: 003-auto-session-audio

## Purpose

Resolve natural language session references to actual sessions. Supports exact substring, fuzzy matching, and semantic similarity search. Returns confidence scores and handles ambiguity by presenting candidates.

## Interface

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
from enum import Enum


class MatchType(str, Enum):
    """How a session reference was matched."""
    EXACT_SUBSTRING = "EXACT_SUBSTRING"
    FUZZY_SUBSTRING = "FUZZY_SUBSTRING"
    SEMANTIC_SIMILARITY = "SEMANTIC_SIMILARITY"
    ACTIVE_CONTEXT = "ACTIVE_CONTEXT"
    AMBIGUOUS = "AMBIGUOUS"
    NOT_FOUND = "NOT_FOUND"


@dataclass
class SessionMatch:
    """Result of session reference resolution."""
    session_id: Optional[str]
    confidence: float  # [0.0, 1.0]
    match_type: MatchType
    candidates: list[str]  # Empty unless AMBIGUOUS


class SessionMatcher(ABC):
    """Contract for resolving natural language session references."""

    @abstractmethod
    def resolve(
        self, 
        reference: str,
        active_session_id: Optional[str] = None
    ) -> SessionMatch:
        """
        Resolve a natural language reference to a session.
        
        Resolution order:
        1. Empty reference → use active session (ACTIVE_CONTEXT)
        2. Exact substring match in session names
        3. Fuzzy substring match (Levenshtein ≤ 2)
        4. Semantic similarity match (cosine > 0.7)
        
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
        Loads all session names and precomputes embeddings.
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
        
        Called when session name changes or embedding is computed.
        
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
        
        Called when session is deleted (if supported).
        """
        pass
```

## Behavior Specification

### Resolution Priority

| Scenario | Match Type | Confidence |
|----------|------------|------------|
| Empty reference, active session exists | `ACTIVE_CONTEXT` | 1.0 |
| Empty reference, no active session | `NOT_FOUND` | 0.0 |
| Exact substring, single match | `EXACT_SUBSTRING` | 1.0 |
| Exact substring, multiple matches | `AMBIGUOUS` | 0.9 |
| Fuzzy match (≤2 edits), single | `FUZZY_SUBSTRING` | 0.9 |
| Semantic match, high confidence | `SEMANTIC_SIMILARITY` | cosine score |
| Semantic match, multiple similar | `AMBIGUOUS` | best score |
| No matches found | `NOT_FOUND` | 0.0 |

### Example Resolutions

| Reference | Sessions | Result |
|-----------|----------|--------|
| `""` | active: `"abc"` | `("abc", 1.0, ACTIVE_CONTEXT, [])` |
| `"relatório"` | `["relatório mensal", "projeto"]` | `("...", 1.0, EXACT_SUBSTRING, [])` |
| `"relatorio"` | `["relatório mensal"]` | `("...", 0.9, FUZZY_SUBSTRING, [])` |
| `"monthly report"` | `["relatório mensal"]` | `("...", 0.85, SEMANTIC_SIMILARITY, [])` |
| `"relatório"` | `["relatório jan", "relatório fev"]` | `(None, 0.9, AMBIGUOUS, [id1, id2])` |
| `"xyz123"` | any | `(None, 0.0, NOT_FOUND, [])` |

### Semantic Matching Thresholds

| Threshold | Behavior |
|-----------|----------|
| `> 0.85` AND gap `> 0.15` to second | Single confident match |
| `> 0.7` | Include in candidates |
| `≤ 0.7` | Exclude from results |

## Dependencies

- `sentence-transformers`: For embedding computation
- `numpy`: For cosine similarity calculation

## Error Handling

- **Missing embeddings**: Fall back to substring matching only
- **Model load failure**: Log error, continue with substring matching
- **Empty session index**: Return `NOT_FOUND` for all queries

## Testing Requirements

### Contract Tests

```python
def test_empty_reference_uses_active():
    """Empty reference returns active session."""

def test_exact_substring_single_match():
    """Single exact match returns with confidence 1.0."""

def test_exact_substring_multiple_returns_ambiguous():
    """Multiple exact matches return AMBIGUOUS."""

def test_fuzzy_handles_typos():
    """Levenshtein distance ≤ 2 matches."""

def test_semantic_matches_paraphrase():
    """Semantically similar reference matches."""

def test_no_match_returns_not_found():
    """Unmatched reference returns NOT_FOUND."""

def test_rebuild_index_loads_all_sessions():
    """Rebuild populates index from storage."""
```

### Integration Tests

```python
def test_end_to_end_reference_resolution():
    """Full flow: create session, name it, resolve reference."""
```
