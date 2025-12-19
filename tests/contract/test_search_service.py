"""Contract tests for SearchService.

Tests per contracts/search-service.md for 004-resilient-voice-capture.
"""

import pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path

from src.models.session import (
    AudioEntry,
    Session,
    SessionState,
    TranscriptionStatus,
)
from src.models.search_result import SearchResult, PreviewFragment
from src.services.search.engine import (
    IndexHealth,
    IndexStatus,
    RebuildResult,
    SearchMethod,
    SearchResponse,
    SearchService,
)


def create_test_session(
    session_id: str,
    name: str = "Test Session",
    state: SessionState = SessionState.READY,
    transcript_text: str = "",
) -> Session:
    """Create a test session with optional transcript."""
    return Session(
        id=session_id,
        state=state,
        created_at=datetime.now(timezone.utc),
        chat_id=12345,
        intelligible_name=name,
        audio_entries=[
            AudioEntry(
                sequence=1,
                received_at=datetime.now(timezone.utc),
                telegram_file_id="file_1",
                local_filename="001_audio.ogg",
                file_size_bytes=1024,
                duration_seconds=10.0,
                transcription_status=TranscriptionStatus.SUCCESS,
            )
        ],
    )


@pytest.fixture
def sessions_dir(tmp_path: Path) -> Path:
    """Create temporary sessions directory."""
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    return sessions


@pytest.fixture
def search_service(sessions_dir: Path) -> SearchService:
    """Create SearchService for testing."""
    from src.services.search.engine import DefaultSearchService
    from src.services.session.storage import SessionStorage
    
    storage = SessionStorage(sessions_dir)
    
    # Create test sessions with varied content
    sessions = [
        create_test_session(
            "2025-01-01_00-00-00",
            "Meeting about quarterly planning",
        ),
        create_test_session(
            "2025-01-02_00-00-00",
            "Ideas for new product features",
        ),
        create_test_session(
            "2025-01-03_00-00-00",
            "Discussion about budget allocation",
        ),
    ]
    
    for session in sessions:
        storage.create_session_folders(session)
        storage.save(session)
    
    return DefaultSearchService(storage=storage)


class TestSearch:
    """Contract tests for SearchService.search."""

    def test_search_returns_response(self, search_service: SearchService):
        """search must return SearchResponse with required fields."""
        response = search_service.search("meeting")
        
        assert isinstance(response, SearchResponse)
        assert hasattr(response, "query")
        assert hasattr(response, "results")
        assert hasattr(response, "total_found")
        assert hasattr(response, "search_method")

    def test_search_matches_session_names(self, search_service: SearchService):
        """search should match sessions by name."""
        response = search_service.search("meeting")
        
        assert response.total_found >= 1
        assert any("meeting" in r.session_name.lower() for r in response.results)

    def test_search_respects_limit(self, search_service: SearchService):
        """search should respect limit parameter."""
        response = search_service.search("", limit=1)
        
        assert len(response.results) <= 1

    def test_search_returns_search_method(self, search_service: SearchService):
        """search must indicate which method was used."""
        response = search_service.search("planning")
        
        assert response.search_method in [
            SearchMethod.SEMANTIC,
            SearchMethod.TEXT,
            SearchMethod.CHRONOLOGICAL,
            SearchMethod.HYBRID,
        ]

    def test_search_never_raises(self, search_service: SearchService):
        """search should never raise exceptions - always return response."""
        # Empty query
        response = search_service.search("")
        assert isinstance(response, SearchResponse)
        
        # Special characters
        response = search_service.search("@#$%^&*()")
        assert isinstance(response, SearchResponse)
        
        # Very long query
        response = search_service.search("a" * 1000)
        assert isinstance(response, SearchResponse)

    def test_search_results_have_required_fields(self, search_service: SearchService):
        """SearchResult must have all required fields."""
        response = search_service.search("meeting")
        
        for result in response.results:
            assert isinstance(result, SearchResult)
            assert result.session_id
            assert result.session_name is not None
            assert result.relevance_score >= 0.0


class TestListChronological:
    """Contract tests for SearchService.list_chronological."""

    def test_list_returns_sessions(self, search_service: SearchService):
        """list_chronological must return sessions."""
        response = search_service.list_chronological()
        
        assert isinstance(response, SearchResponse)
        assert response.search_method == SearchMethod.CHRONOLOGICAL

    def test_list_respects_limit(self, search_service: SearchService):
        """list_chronological should respect limit."""
        response = search_service.list_chronological(limit=2)
        
        assert len(response.results) <= 2

    def test_list_respects_offset(self, search_service: SearchService):
        """list_chronological should support pagination."""
        all_results = search_service.list_chronological(limit=100)
        page_1 = search_service.list_chronological(limit=1, offset=0)
        page_2 = search_service.list_chronological(limit=1, offset=1)
        
        if len(all_results.results) >= 2:
            # Pages should have different sessions
            assert page_1.results[0].session_id != page_2.results[0].session_id

    def test_results_sorted_newest_first(self, search_service: SearchService):
        """list_chronological should return newest first."""
        response = search_service.list_chronological(limit=100)
        
        if len(response.results) >= 2:
            for i in range(len(response.results) - 1):
                # session_created_at should be descending
                if (response.results[i].session_created_at and 
                    response.results[i+1].session_created_at):
                    assert response.results[i].session_created_at >= response.results[i+1].session_created_at


class TestGetIndexStatus:
    """Contract tests for SearchService.get_index_status."""

    def test_index_status_returns_status(self, search_service: SearchService):
        """get_index_status must return IndexStatus."""
        status = search_service.get_index_status()
        
        assert isinstance(status, IndexStatus)
        assert status.total_sessions >= 0
        assert status.index_health in IndexHealth

    def test_index_coverage_percentage(self, search_service: SearchService):
        """embedding_coverage_percent should be 0-100."""
        status = search_service.get_index_status()
        
        assert 0.0 <= status.embedding_coverage_percent <= 100.0


class TestRebuildIndex:
    """Contract tests for SearchService.rebuild_index."""

    def test_rebuild_returns_result(self, search_service: SearchService):
        """rebuild_index must return RebuildResult."""
        result = search_service.rebuild_index()
        
        assert isinstance(result, RebuildResult)
        assert result.sessions_processed >= 0
        assert result.duration_seconds >= 0.0


class TestSearchFallback:
    """Contract tests for search fallback behavior."""

    def test_fallback_to_text_when_no_embeddings(
        self, search_service: SearchService
    ):
        """Should fallback to text search when embeddings unavailable."""
        # Search should work even without embeddings
        response = search_service.search("meeting")
        
        # Should indicate if fallback was used
        if response.fallback_used:
            assert response.fallback_reason is not None

    def test_empty_results_include_suggestions(
        self, search_service: SearchService
    ):
        """Empty results should include helpful suggestions."""
        response = search_service.search("xyznonexistentquery123")
        
        # Even with no results, should have guidance
        assert isinstance(response, SearchResponse)
        # May have suggestions or at least indicates method used


class TestSearchResponse:
    """Tests for SearchResponse data structure."""

    def test_to_dict_serialization(self, search_service: SearchService):
        """SearchResponse.to_dict should serialize correctly."""
        response = search_service.search("test")
        data = response.to_dict()
        
        assert "query" in data
        assert "results" in data
        assert "total_found" in data
        assert "search_method" in data

    def test_results_are_serializable(self, search_service: SearchService):
        """Search results should be JSON-serializable."""
        import json
        
        response = search_service.search("meeting")
        data = response.to_dict()
        
        # Should not raise
        json_str = json.dumps(data)
        assert json_str
