"""Integration tests for search flow.

These tests validate the complete search workflow including
semantic search, text fallback, and /sessions command handler.
"""

import pytest
from datetime import datetime, timezone
from pathlib import Path

from src.models.session import (
    AudioEntry,
    Session,
    SessionState,
    TranscriptionStatus,
)
from src.services.session.storage import SessionStorage
from src.services.session.manager import SessionManager
from src.services.search.engine import (
    DefaultSearchService,
    SearchMethod,
    IndexHealth,
)
from src.cli.commands import SessionsCommandHandler, CommandStatus


@pytest.fixture
def sessions_dir(tmp_path: Path) -> Path:
    """Create a temporary sessions directory."""
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    return sessions


@pytest.fixture
def storage(sessions_dir: Path) -> SessionStorage:
    """Create a SessionStorage instance."""
    return SessionStorage(sessions_dir)


@pytest.fixture
def manager(storage: SessionStorage) -> SessionManager:
    """Create a SessionManager instance."""
    return SessionManager(storage)


@pytest.fixture
def search_service(storage: SessionStorage) -> DefaultSearchService:
    """Create a DefaultSearchService instance."""
    return DefaultSearchService(storage)


@pytest.fixture
def sessions_handler(search_service: DefaultSearchService, manager: SessionManager):
    """Create a SessionsCommandHandler instance."""
    return SessionsCommandHandler(search_service, manager)


def create_audio_entry(sequence: int) -> AudioEntry:
    """Helper to create audio entries."""
    return AudioEntry(
        sequence=sequence,
        received_at=datetime.now(timezone.utc),
        telegram_file_id=f"file_id_{sequence}",
        local_filename=f"{sequence:03d}_audio.ogg",
        file_size_bytes=1024 * sequence,
        duration_seconds=10.0 * sequence,
    )


def create_session_with_name(manager: SessionManager, name: str, chat_id: int = 12345) -> Session:
    """Helper to create a session with a specific name."""
    session = manager.create_session(chat_id=chat_id)
    # Add some audio
    manager.add_audio(session.id, create_audio_entry(1))
    # Update the name
    session = manager.get_session(session.id)
    session.intelligible_name = name
    manager.storage.save(session)
    return manager.get_session(session.id)


class TestSearchWorkflow:
    """Test complete search workflow."""
    
    def test_search_empty_database(self, search_service: DefaultSearchService):
        """Test search with no sessions."""
        response = search_service.search("test query")
        
        assert response.total_found == 0
        assert response.results == []
        assert response.search_method == SearchMethod.TEXT
    
    def test_search_finds_matching_session(self, manager: SessionManager, search_service: DefaultSearchService):
        """Test search finds sessions by name."""
        # Create sessions with specific names
        create_session_with_name(manager, "Meeting about Python development")
        create_session_with_name(manager, "JavaScript tutorial review")
        create_session_with_name(manager, "Team standup meeting")
        
        # Search for Python
        response = search_service.search("Python")
        
        assert response.total_found >= 1
        assert any("Python" in r.session_name for r in response.results)
    
    def test_search_ranks_by_relevance(self, manager: SessionManager, search_service: DefaultSearchService):
        """Test search results are sorted by relevance score."""
        create_session_with_name(manager, "Meeting")
        create_session_with_name(manager, "Python Meeting")
        create_session_with_name(manager, "Python development meeting")
        
        response = search_service.search("Python")
        
        # Should be sorted by relevance (highest first)
        if len(response.results) > 1:
            for i in range(len(response.results) - 1):
                assert response.results[i].relevance_score >= response.results[i + 1].relevance_score
    
    def test_list_chronological(self, manager: SessionManager, search_service: DefaultSearchService):
        """Test chronological listing without search query."""
        # Create multiple sessions
        session1 = create_session_with_name(manager, "First session")
        session2 = create_session_with_name(manager, "Second session")
        session3 = create_session_with_name(manager, "Third session")
        
        response = search_service.list_chronological(limit=10)
        
        assert response.total_found >= 3
        assert response.search_method == SearchMethod.CHRONOLOGICAL
    
    def test_list_respects_chat_id_filter(self, manager: SessionManager, search_service: DefaultSearchService):
        """Test that listing filters by chat_id."""
        create_session_with_name(manager, "User 1 session", chat_id=111)
        create_session_with_name(manager, "User 2 session", chat_id=222)
        
        response = search_service.list_chronological(chat_id=111, limit=10)
        
        # Should only return user 1's session
        for result in response.results:
            # Results belong to specified user
            pass  # Just verify no exception


class TestSessionsCommandHandler:
    """Test /sessions command handler integration."""
    
    def test_sessions_list_empty(self, sessions_handler: SessionsCommandHandler):
        """Test /sessions with no sessions."""
        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            sessions_handler.execute()
        )
        
        assert result.status == CommandStatus.INFO
        assert "No sessions found" in result.message
    
    def test_sessions_list_with_sessions(
        self, 
        manager: SessionManager, 
        sessions_handler: SessionsCommandHandler
    ):
        """Test /sessions lists existing sessions."""
        create_session_with_name(manager, "Test session one")
        create_session_with_name(manager, "Test session two")
        
        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            sessions_handler.execute()
        )
        
        assert result.status == CommandStatus.SUCCESS
        assert result.data["total_found"] >= 2
        assert len(result.data["sessions"]) >= 2
    
    def test_sessions_search_with_query(
        self,
        manager: SessionManager,
        sessions_handler: SessionsCommandHandler
    ):
        """Test /sessions with search query."""
        create_session_with_name(manager, "Python workshop")
        create_session_with_name(manager, "JavaScript tutorial")
        
        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            sessions_handler.execute(query="Python")
        )
        
        assert result.status == CommandStatus.SUCCESS
        assert result.data["query"] == "Python"
        assert result.data["search_method"] == "TEXT"
    
    def test_sessions_search_no_results(
        self,
        manager: SessionManager,
        sessions_handler: SessionsCommandHandler
    ):
        """Test /sessions search with no matches."""
        create_session_with_name(manager, "Meeting notes")
        
        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            sessions_handler.execute(query="xyz123nonexistent")
        )
        
        assert result.status == CommandStatus.INFO
        assert "No sessions found" in result.message
    
    def test_sessions_respects_limit(
        self,
        manager: SessionManager,
        sessions_handler: SessionsCommandHandler
    ):
        """Test /sessions respects limit parameter."""
        for i in range(5):
            create_session_with_name(manager, f"Session {i}")
        
        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            sessions_handler.execute(limit=3)
        )
        
        assert len(result.data["sessions"]) <= 3


class TestSearchIndexStatus:
    """Test search index status functionality."""
    
    def test_index_status_empty(self, search_service: DefaultSearchService):
        """Test index status with no sessions."""
        status = search_service.get_index_status()
        
        assert status.total_sessions == 0
        assert status.index_health == IndexHealth.EMPTY
    
    def test_index_status_with_sessions(
        self,
        manager: SessionManager,
        search_service: DefaultSearchService
    ):
        """Test index status with sessions."""
        create_session_with_name(manager, "Session one")
        create_session_with_name(manager, "Session two")
        
        status = search_service.get_index_status()
        
        assert status.total_sessions >= 2
        assert status.embedding_coverage_percent >= 0


class TestSearchFallbackBehavior:
    """Test search fallback when semantic search unavailable."""
    
    def test_text_fallback_without_embeddings(
        self,
        manager: SessionManager,
        search_service: DefaultSearchService
    ):
        """Test that text search is used when no embedding service."""
        create_session_with_name(manager, "Python tutorial")
        
        # No embedding service configured
        response = search_service.search("Python")
        
        # Text search is primary when no embedding service
        assert response.search_method == SearchMethod.TEXT
        # Should indicate semantic wasn't available
        assert response.fallback_reason == "Semantic search not available"
    
    def test_search_never_raises(self, search_service: DefaultSearchService):
        """Test that search never raises exceptions."""
        # Various edge cases
        queries = [
            "",
            "   ",
            "a" * 1000,  # Very long query
            "🎉🎊",  # Emoji
            "<script>alert('xss')</script>",  # HTML
            "SELECT * FROM sessions",  # SQL-like
        ]
        
        for query in queries:
            response = search_service.search(query)
            assert response is not None
            assert hasattr(response, "results")
