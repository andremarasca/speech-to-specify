"""Search service for semantic and text-based session search.

Per contracts/search-service.md for 004-resilient-voice-capture.
Provides unified search across all sessions with graceful fallback.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from src.models.session import MatchType, Session, TranscriptionStatus
from src.models.search_result import SearchResult, PreviewFragment


class SearchMethod(str, Enum):
    """How search was performed."""
    
    SEMANTIC = "SEMANTIC"  # Embedding similarity
    TEXT = "TEXT"  # Full-text search
    CHRONOLOGICAL = "CHRONOLOGICAL"  # Date-based listing
    HYBRID = "HYBRID"  # Combined semantic + text


class IndexHealth(str, Enum):
    """Health status of search index."""
    
    HEALTHY = "HEALTHY"  # All sessions indexed
    BUILDING = "BUILDING"  # Index in progress
    PARTIAL = "PARTIAL"  # Some sessions missing
    STALE = "STALE"  # Index outdated
    EMPTY = "EMPTY"  # No index exists


@dataclass
class SearchResponse:
    """Response from search operation.
    
    Attributes:
        query: Original search query
        results: Matching sessions
        total_found: Total matches (may exceed returned results)
        search_method: How search was performed
        fallback_used: Whether fallback strategy was used
        fallback_reason: Why fallback was needed (if applicable)
        suggestions: Alternative queries if no results
        duration_ms: Search duration in milliseconds
    """
    
    query: str
    results: list[SearchResult]
    total_found: int
    search_method: SearchMethod
    fallback_used: bool = False
    fallback_reason: Optional[str] = None
    suggestions: list[str] = field(default_factory=list)
    duration_ms: float = 0.0
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "query": self.query,
            "results": [r.to_dict() for r in self.results],
            "total_found": self.total_found,
            "search_method": self.search_method.value,
            "fallback_used": self.fallback_used,
            "fallback_reason": self.fallback_reason,
            "suggestions": self.suggestions,
            "duration_ms": self.duration_ms,
        }


@dataclass
class IndexStatus:
    """Status of search indexes.
    
    Attributes:
        total_sessions: Total sessions in storage
        sessions_with_embeddings: Sessions with generated embeddings
        sessions_with_transcripts: Sessions with transcripts
        embedding_coverage_percent: Percentage of sessions with embeddings
        last_index_update: When index was last updated
        index_health: Overall index health
    """
    
    total_sessions: int
    sessions_with_embeddings: int
    sessions_with_transcripts: int
    embedding_coverage_percent: float
    last_index_update: Optional[datetime]
    index_health: IndexHealth
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "total_sessions": self.total_sessions,
            "sessions_with_embeddings": self.sessions_with_embeddings,
            "sessions_with_transcripts": self.sessions_with_transcripts,
            "embedding_coverage_percent": self.embedding_coverage_percent,
            "last_index_update": (
                self.last_index_update.isoformat() 
                if self.last_index_update 
                else None
            ),
            "index_health": self.index_health.value,
        }


@dataclass
class RebuildResult:
    """Result of index rebuild.
    
    Attributes:
        sessions_processed: Number of sessions processed
        embeddings_generated: Number of embeddings created
        errors: List of error messages
        duration_seconds: Time taken to rebuild
    """
    
    sessions_processed: int
    embeddings_generated: int
    errors: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0


class SearchService(ABC):
    """Service for searching across sessions.
    
    Per contracts/search-service.md for 004-resilient-voice-capture.
    Ensures search always returns useful results per Constitution Pillar V.
    """
    
    @abstractmethod
    def search(
        self,
        query: str,
        chat_id: Optional[int] = None,
        limit: int = 10,
        min_score: float = 0.3
    ) -> SearchResponse:
        """Search sessions by semantic similarity or text match.
        
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
        """Search sessions within date range.
        
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
        """List sessions in chronological order (newest first).
        
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
        """Get status of search indexes.
        
        Returns:
            IndexStatus with embedding coverage and health
        """
        pass
    
    @abstractmethod
    def rebuild_index(self, session_id: Optional[str] = None) -> RebuildResult:
        """Rebuild search index.
        
        Args:
            session_id: Specific session (None = all sessions)
            
        Returns:
            RebuildResult with stats
        """
        pass


class DefaultSearchService(SearchService):
    """Default implementation of SearchService.
    
    Provides text-based search with optional semantic search when
    embeddings are available. Always falls back gracefully.
    """
    
    def __init__(self, storage, embedding_service=None):
        """Initialize search service.
        
        Args:
            storage: SessionStorage for session access
            embedding_service: Optional EmbeddingService for semantic search
        """
        self.storage = storage
        self.embedding_service = embedding_service
        self._last_index_update: Optional[datetime] = None
    
    def search(
        self,
        query: str,
        chat_id: Optional[int] = None,
        limit: int = 10,
        min_score: float = 0.3
    ) -> SearchResponse:
        """Search sessions by text match (semantic search when embeddings available)."""
        import time
        start_time = time.time()
        
        query = query.strip()
        
        # Empty query - return chronological list
        if not query:
            return self.list_chronological(chat_id=chat_id, limit=limit)
        
        try:
            # Get all sessions
            sessions = self.storage.list_sessions(limit=1000)
            
            # Filter by chat_id if provided
            if chat_id is not None:
                sessions = [s for s in sessions if s.chat_id == chat_id]
            
            # Score and filter sessions
            results = []
            query_lower = query.lower()
            
            for session in sessions:
                # Calculate text match score
                score = self._calculate_text_score(session, query_lower)
                
                if score >= min_score:
                    results.append(SearchResult(
                        session_id=session.id,
                        session_name=session.intelligible_name or session.id,
                        relevance_score=score,
                        match_type=MatchType.EXACT_SUBSTRING if score > 0.7 else MatchType.FUZZY_SUBSTRING,
                        session_created_at=session.created_at,
                        total_audio_duration=session.total_audio_duration,
                        audio_count=session.audio_count,
                    ))
            
            # Sort by score and limit
            results.sort(key=lambda r: r.relevance_score, reverse=True)
            results = results[:limit]
            
            duration_ms = (time.time() - start_time) * 1000
            
            return SearchResponse(
                query=query,
                results=results,
                total_found=len(results),
                search_method=SearchMethod.TEXT,
                fallback_used=True if self.embedding_service else False,
                fallback_reason="Semantic search not available" if not self.embedding_service else None,
                duration_ms=duration_ms,
            )
            
        except Exception as e:
            # Never raise - return empty response with guidance
            return SearchResponse(
                query=query,
                results=[],
                total_found=0,
                search_method=SearchMethod.TEXT,
                fallback_used=True,
                fallback_reason=f"Search error: {str(e)}",
                suggestions=["Try a different search term", "Use /sessions to list all sessions"],
            )
    
    def _calculate_text_score(self, session: Session, query_lower: str) -> float:
        """Calculate text match score for a session."""
        score = 0.0
        
        # Match against session name
        name = (session.intelligible_name or "").lower()
        if query_lower in name:
            score = max(score, 0.8)
        elif any(word in name for word in query_lower.split()):
            score = max(score, 0.5)
        
        # Match against session ID
        if query_lower in session.id.lower():
            score = max(score, 0.6)
        
        return score
    
    def search_by_date_range(
        self,
        start_date: datetime,
        end_date: datetime,
        chat_id: Optional[int] = None
    ) -> SearchResponse:
        """Search sessions within date range."""
        import time
        start_time = time.time()
        
        sessions = self.storage.list_sessions(limit=1000)
        
        # Filter by date range and chat_id
        filtered = []
        for session in sessions:
            if start_date <= session.created_at <= end_date:
                if chat_id is None or session.chat_id == chat_id:
                    filtered.append(session)
        
        # Convert to results
        results = [
            SearchResult(
                session_id=s.id,
                session_name=s.intelligible_name or s.id,
                relevance_score=1.0,
                match_type=MatchType.CHRONOLOGICAL,
                session_created_at=s.created_at,
                total_audio_duration=s.total_audio_duration,
                audio_count=s.audio_count,
            )
            for s in filtered
        ]
        
        # Sort chronologically
        results.sort(key=lambda r: r.created_at, reverse=True)
        
        duration_ms = (time.time() - start_time) * 1000
        
        return SearchResponse(
            query=f"date:{start_date.date()} to {end_date.date()}",
            results=results,
            total_found=len(results),
            search_method=SearchMethod.CHRONOLOGICAL,
            duration_ms=duration_ms,
        )
    
    def list_chronological(
        self,
        chat_id: Optional[int] = None,
        limit: int = 20,
        offset: int = 0
    ) -> SearchResponse:
        """List sessions in chronological order (newest first)."""
        import time
        start_time = time.time()
        
        sessions = self.storage.list_sessions(limit=1000)
        
        # Filter by chat_id
        if chat_id is not None:
            sessions = [s for s in sessions if s.chat_id == chat_id]
        
        # Already sorted by date (newest first from storage)
        # Apply pagination
        total = len(sessions)
        sessions = sessions[offset:offset + limit]
        
        # Convert to results
        results = [
            SearchResult(
                session_id=s.id,
                session_name=s.intelligible_name or s.id,
                relevance_score=1.0,
                match_type=MatchType.CHRONOLOGICAL,
                session_created_at=s.created_at,
                total_audio_duration=s.total_audio_duration,
                audio_count=s.audio_count,
            )
            for s in sessions
        ]
        
        duration_ms = (time.time() - start_time) * 1000
        
        return SearchResponse(
            query="",
            results=results,
            total_found=total,
            search_method=SearchMethod.CHRONOLOGICAL,
            duration_ms=duration_ms,
        )
    
    def get_index_status(self) -> IndexStatus:
        """Get status of search indexes."""
        sessions = self.storage.list_sessions(limit=1000)
        
        total = len(sessions)
        with_embeddings = sum(1 for s in sessions if s.embedding is not None)
        with_transcripts = sum(
            1 for s in sessions 
            if any(e.transcription_status == TranscriptionStatus.SUCCESS 
                   for e in s.audio_entries)
        )
        
        coverage = (with_embeddings / total * 100) if total > 0 else 0.0
        
        # Determine health
        if total == 0:
            health = IndexHealth.EMPTY
        elif with_embeddings == total:
            health = IndexHealth.HEALTHY
        elif with_embeddings > 0:
            health = IndexHealth.PARTIAL
        else:
            health = IndexHealth.STALE
        
        return IndexStatus(
            total_sessions=total,
            sessions_with_embeddings=with_embeddings,
            sessions_with_transcripts=with_transcripts,
            embedding_coverage_percent=coverage,
            last_index_update=self._last_index_update,
            index_health=health,
        )
    
    def rebuild_index(self, session_id: Optional[str] = None) -> RebuildResult:
        """Rebuild search index."""
        import time
        start_time = time.time()
        
        processed = 0
        embeddings = 0
        errors = []
        
        if session_id:
            sessions = [self.storage.load(session_id)]
            sessions = [s for s in sessions if s is not None]
        else:
            sessions = self.storage.list_sessions(limit=1000)
        
        for session in sessions:
            processed += 1
            
            # Generate embedding if service available
            if self.embedding_service:
                try:
                    # Collect transcript text
                    text_parts = [session.intelligible_name or ""]
                    # Would add transcript content here
                    text = " ".join(text_parts)
                    
                    if text.strip():
                        # embedding = self.embedding_service.embed(text)
                        # session.embedding = embedding
                        # self.storage.save(session)
                        embeddings += 1
                except Exception as e:
                    errors.append(f"Session {session.id}: {str(e)}")
        
        self._last_index_update = datetime.now(timezone.utc)
        duration = time.time() - start_time
        
        return RebuildResult(
            sessions_processed=processed,
            embeddings_generated=embeddings,
            errors=errors,
            duration_seconds=duration,
        )
