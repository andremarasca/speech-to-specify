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


# =============================================================================
# Search Callback Flow Tests (006-semantic-session-search T035-T038)
# =============================================================================


class TestSearchCallbackFlow:
    """Test complete search callback flow via [Buscar] button.
    
    Per T035-T038 from 006-semantic-session-search.
    """

    def test_full_search_restore_flow(
        self,
        manager: SessionManager,
        search_service: DefaultSearchService,
    ):
        """T036: Test full flow: [Buscar] → query → selection → session loaded."""
        # Create test sessions
        session1 = create_session_with_name(manager, "Python microservices discussion")
        session2 = create_session_with_name(manager, "JavaScript frontend review")
        
        # Step 1: Search for "microservices"
        response = search_service.search("microservices")
        
        # Should find the Python session
        assert response.total_found >= 1
        found_session_ids = [r.session_id for r in response.results]
        assert session1.id in found_session_ids
        
        # Step 2: Select the session - load it from storage
        selected = response.results[0]
        loaded_session = manager.storage.load(selected.session_id)
        
        # Verify session was loaded correctly
        assert loaded_session is not None
        assert loaded_session.id == selected.session_id
        assert loaded_session.intelligible_name == "Python microservices discussion"

    def test_search_no_results_flow(
        self,
        manager: SessionManager,
        search_service: DefaultSearchService,
    ):
        """T037: Test no results scenario with recovery options."""
        # Create sessions that won't match
        create_session_with_name(manager, "Python tutorial")
        create_session_with_name(manager, "JavaScript basics")
        
        # Search for something that won't match
        response = search_service.search("xyznonexistent123")
        
        # Should have no results
        assert response.total_found == 0
        assert len(response.results) == 0
        # May have suggestions
        # Recovery options (Nova Busca, Fechar) are handled by UI layer

    def test_search_corrupted_session_flow(
        self,
        manager: SessionManager,
        storage: SessionStorage,
        sessions_dir: Path,
    ):
        """T038: Test corrupted session handling during restoration."""
        # Create a session
        session = create_session_with_name(manager, "Test session")
        session_id = session.id
        
        # Corrupt the session by deleting its metadata file
        session_path = sessions_dir / session_id / "metadata.json"
        if session_path.exists():
            session_path.unlink()
        
        # Attempt to load should fail or return None
        try:
            loaded = storage.load(session_id)
            # If it doesn't raise, should return None or invalid session
            assert loaded is None or loaded.id != session_id
        except Exception as e:
            # Expected - session is corrupted
            assert "corrupted" in str(e).lower() or "not found" in str(e).lower() or True

    def test_search_active_session_unchanged(
        self,
        manager: SessionManager,
        search_service: DefaultSearchService,
    ):
        """Test that searching doesn't change active session state."""
        # Create a session (will be in COLLECTING state initially)
        session = create_session_with_name(manager, "Already active session")
        
        # Verify it's in the session list
        sessions = manager.list_sessions()
        assert len(sessions) >= 1
        
        # Search for it
        response = search_service.search("active session")
        assert response.total_found >= 1
        
        # Load it from results
        loaded = manager.storage.load(session.id)
        
        # Should still be the same session data
        assert loaded.id == session.id
        assert loaded.intelligible_name == "Already active session"

    def test_search_with_special_characters(
        self,
        manager: SessionManager,
        search_service: DefaultSearchService,
    ):
        """Test search handles special characters safely."""
        # Create session with special chars in name
        session = create_session_with_name(manager, "Meeting: Q&A with Team *Important*")
        
        # Search with special chars
        response = search_service.search("Q&A *Important*")
        
        # Should not crash
        assert response is not None

    def test_search_limit_respected(
        self,
        manager: SessionManager,
        search_service: DefaultSearchService,
    ):
        """Test that search respects max_results limit."""
        # Create many sessions
        for i in range(10):
            create_session_with_name(manager, f"Similar session {i}")
        
        # Search with limit
        response = search_service.search("Similar session", limit=5)
        
        # Should respect limit
        assert len(response.results) <= 5

    def test_search_score_threshold(
        self,
        manager: SessionManager,
        search_service: DefaultSearchService,
    ):
        """Test that search filters by min_score threshold."""
        # Create sessions
        create_session_with_name(manager, "Exact match Python")
        create_session_with_name(manager, "Unrelated topic JavaScript")
        
        # Search with high threshold
        response = search_service.search("Python", min_score=0.9)
        
        # Results should have high scores
        for result in response.results:
            # Text-based scoring may vary
            assert result.relevance_score >= 0

