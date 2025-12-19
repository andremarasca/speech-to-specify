# Contract: Search Service

**Feature**: 004-resilient-voice-capture  
**Service**: `SearchService`  
**Location**: `src/services/search/engine.py`

## Purpose

Provides unified search across all sessions with semantic understanding and graceful fallback. Ensures search always returns useful results per Constitution Pillar V (Busca como Memória Efetiva).

## Interface

```python
from abc import ABC, abstractmethod
from typing import Optional
from enum import Enum

class SearchService(ABC):
    """Service for searching across sessions."""
    
    @abstractmethod
    def search(
        self,
        query: str,
        chat_id: Optional[int] = None,
        limit: int = 10,
        min_score: float = 0.3
    ) -> SearchResponse:
        """
        Search sessions by semantic similarity or text match.
        
        Strategy:
        1. Try semantic search if embeddings available
        2. Fallback to text search if semantic unavailable/insufficient
        3. Always include search method used in response
        
        Args:
            query: User's search query (natural language)
            chat_id: Filter by user (None = all users)
            limit: Maximum results
            min_score: Minimum relevance score (0.0-1.0)
            
        Returns:
            SearchResponse with results and metadata
            
        Never raises: Always returns response (may be empty with guidance)
        """
        pass
    
    @abstractmethod
    def search_by_date_range(
        self,
        start_date: datetime,
        end_date: datetime,
        chat_id: Optional[int] = None
    ) -> SearchResponse:
        """
        Search sessions within date range.
        
        Args:
            start_date: Range start (inclusive)
            end_date: Range end (inclusive)
            chat_id: Filter by user
            
        Returns:
            Sessions in date range, chronologically ordered
        """
        pass
    
    @abstractmethod
    def list_chronological(
        self,
        chat_id: Optional[int] = None,
        limit: int = 20,
        offset: int = 0
    ) -> SearchResponse:
        """
        List sessions in chronological order (newest first).
        
        Used when no search query or as fallback navigation.
        
        Args:
            chat_id: Filter by user
            limit: Page size
            offset: Pagination offset
            
        Returns:
            Chronologically ordered sessions
        """
        pass
    
    @abstractmethod
    def get_index_status(self) -> IndexStatus:
        """
        Get status of search indexes.
        
        Returns:
            IndexStatus with embedding coverage and health
        """
        pass
    
    @abstractmethod
    def rebuild_index(self, session_id: Optional[str] = None) -> RebuildResult:
        """
        Rebuild search index.
        
        Args:
            session_id: Specific session (None = all sessions)
            
        Returns:
            RebuildResult with stats
        """
        pass
```

## Data Types

```python
@dataclass
class SearchResponse:
    """Response from search operation."""
    query: str
    results: list[SearchResult]
    total_found: int
    search_method: SearchMethod
    fallback_used: bool
    fallback_reason: Optional[str]
    suggestions: list[str]  # If no results, suggest alternatives
    duration_ms: float

class SearchMethod(str, Enum):
    SEMANTIC = "SEMANTIC"           # Embedding similarity
    TEXT = "TEXT"                   # Full-text search
    CHRONOLOGICAL = "CHRONOLOGICAL" # Date-based listing
    HYBRID = "HYBRID"               # Combined semantic + text

@dataclass
class SearchResult:
    """Individual search result."""
    session_id: str
    session_name: str
    relevance_score: float  # 0.0 - 1.0
    match_type: MatchType
    preview_fragments: list[PreviewFragment]
    session_created_at: datetime
    total_audio_duration_seconds: float
    audio_count: int
    
@dataclass
class PreviewFragment:
    """Text fragment showing why result matched."""
    text: str
    highlight_ranges: list[tuple[int, int]]  # Start, end positions
    source: str  # "transcript" | "name"

@dataclass
class IndexStatus:
    """Status of search indexes."""
    total_sessions: int
    sessions_with_embeddings: int
    sessions_with_transcripts: int
    embedding_coverage_percent: float
    last_index_update: Optional[datetime]
    index_health: IndexHealth

class IndexHealth(str, Enum):
    HEALTHY = "HEALTHY"       # All indexed
    BUILDING = "BUILDING"     # Index in progress
    PARTIAL = "PARTIAL"       # Some sessions missing
    STALE = "STALE"           # Index outdated
    EMPTY = "EMPTY"           # No index

@dataclass
class RebuildResult:
    """Result of index rebuild."""
    sessions_processed: int
    embeddings_generated: int
    errors: list[str]
    duration_seconds: float
```

## Search Strategy

### Algorithm

```
search(query):
    1. Normalize query (lowercase, trim)
    
    2. If query is empty:
       return list_chronological()
    
    3. Try semantic search:
       a. Generate query embedding
       b. Load session embeddings
       c. Compute cosine similarities
       d. Filter by min_score
       e. If results >= 1:
          return results with method=SEMANTIC
    
    4. Fallback to text search:
       a. Search transcripts for query terms
       b. Score by term frequency + position
       c. If results >= 1:
          return results with method=TEXT, fallback_used=True
    
    5. No results:
       return empty with suggestions:
         - "Try broader terms"
         - "Browse chronologically with /sessions"
         - "Check recent sessions"
```

### Relevance Scoring

**Semantic search**:
```
score = cosine_similarity(query_embedding, session_embedding)
```

**Text search**:
```
score = (term_frequency * 0.4) + (title_match * 0.3) + (recency * 0.3)
```

### Fragment Extraction

For each match, extract context:
```python
def extract_fragment(text: str, match_pos: int, window: int = 100) -> PreviewFragment:
    start = max(0, match_pos - window)
    end = min(len(text), match_pos + window)
    fragment = text[start:end]
    # Highlight the matched portion
    highlight_start = match_pos - start
    highlight_end = highlight_start + len(match_term)
    return PreviewFragment(
        text=fragment,
        highlight_ranges=[(highlight_start, highlight_end)],
        source="transcript"
    )
```

## Test Cases (Contract Tests)

```python
def test_semantic_search_finds_conceptual_matches():
    """Semantic search finds relevant results without exact keywords."""
    # Query: "project planning" should find "roadmap discussion"
    
def test_text_fallback_on_no_embeddings():
    """Falls back to text when embeddings unavailable."""
    
def test_empty_query_returns_chronological():
    """Empty query returns chronological listing."""
    
def test_no_results_provides_suggestions():
    """Zero results include helpful suggestions."""
    
def test_search_never_raises():
    """Search always returns response, never raises."""
    
def test_relevance_score_normalized():
    """All scores are in [0.0, 1.0] range."""
    
def test_preview_fragments_have_context():
    """Preview fragments include surrounding text."""
```

## Fallback Guarantees (Constitution: Pillar V)

| Scenario | Behavior |
|----------|----------|
| No embeddings | Text search on transcripts |
| No transcripts | Search session names only |
| No matches | Suggestions + chronological option |
| Index building | Partial results + "building" indicator |
| Query error | Graceful message, offer alternatives |

**Never return empty without explanation**.

## Configuration

```python
@dataclass
class SearchConfig:
    min_semantic_score: float = 0.3
    min_text_score: float = 0.2
    max_results: int = 50
    fragment_context_chars: int = 100
    enable_hybrid_search: bool = True
```

## Dependencies

- `EmbeddingService`: Query embedding generation
- `SessionStorage`: Load session metadata and transcripts
- `EmbeddingIndexer`: Index management
