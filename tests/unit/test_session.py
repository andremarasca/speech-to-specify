"""Unit tests for session models and manager.

These tests validate the session-related functionality including:
- Session ID generation (timestamp format)
- Session creation with folder structure
- Auto-finalize behavior
- NameSource and MatchType enums (003-auto-session-audio)
"""

import pytest
from datetime import datetime, timezone
from pathlib import Path
import re

from src.lib.timestamps import generate_id
from src.models.session import (
    AudioEntry,
    MatchType,
    NameSource,
    Session,
    SessionMatch,
    SessionState,
    TranscriptionStatus,
)
from src.services.session.storage import SessionStorage
from src.services.session.manager import SessionManager


@pytest.fixture
def sessions_dir(tmp_path: Path) -> Path:
    """Create a temporary sessions directory."""
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    return sessions


@pytest.fixture
def manager(sessions_dir: Path) -> SessionManager:
    """Create a SessionManager instance."""
    storage = SessionStorage(sessions_dir)
    return SessionManager(storage)


class TestSessionIdGeneration:
    """Test session ID generation follows timestamp format."""

    def test_generate_id_format(self):
        """Generated ID should match YYYY-MM-DD_HH-MM-SS format."""
        session_id = generate_id()

        # Pattern: 2025-12-18_14-30-00
        pattern = r"^\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}$"
        assert re.match(pattern, session_id), f"ID '{session_id}' doesn't match expected format"

    def test_generate_id_is_parseable(self):
        """Generated ID should be parseable back to datetime."""
        session_id = generate_id()

        # Should be parseable
        dt = datetime.strptime(session_id, "%Y-%m-%d_%H-%M-%S")
        assert dt is not None

    def test_generate_id_uses_utc(self):
        """Generated ID should use UTC time."""
        before = datetime.now(timezone.utc).replace(microsecond=0)
        session_id = generate_id()
        after = datetime.now(timezone.utc).replace(microsecond=0) + __import__('datetime').timedelta(seconds=1)

        dt = datetime.strptime(session_id, "%Y-%m-%d_%H-%M-%S")
        dt = dt.replace(tzinfo=timezone.utc)

        # Should be between before and after (with 1 second tolerance)
        assert before <= dt <= after


class TestCreateSessionWithFolder:
    """Test session creation creates proper folder structure."""

    def test_create_session_folder_exists(
        self, manager: SessionManager, sessions_dir: Path
    ):
        """Created session should have a folder."""
        session = manager.create_session(chat_id=123)

        session_path = sessions_dir / session.id
        assert session_path.exists()
        assert session_path.is_dir()

    def test_create_session_has_audio_folder(
        self, manager: SessionManager, sessions_dir: Path
    ):
        """Created session should have audio/ subdirectory."""
        session = manager.create_session(chat_id=123)

        audio_path = sessions_dir / session.id / "audio"
        assert audio_path.exists()

    def test_create_session_has_transcripts_folder(
        self, manager: SessionManager, sessions_dir: Path
    ):
        """Created session should have transcripts/ subdirectory."""
        session = manager.create_session(chat_id=123)

        transcripts_path = sessions_dir / session.id / "transcripts"
        assert transcripts_path.exists()

    def test_create_session_has_process_folder(
        self, manager: SessionManager, sessions_dir: Path
    ):
        """Created session should have process/ subdirectory."""
        session = manager.create_session(chat_id=123)

        process_path = sessions_dir / session.id / "process"
        assert process_path.exists()

    def test_create_session_has_metadata_json(
        self, manager: SessionManager, sessions_dir: Path
    ):
        """Created session should have metadata.json."""
        session = manager.create_session(chat_id=123)

        metadata_path = sessions_dir / session.id / "metadata.json"
        assert metadata_path.exists()


class TestAutoFinalizePolicy:
    """Test auto-finalize when creating new session with existing active."""

    def test_auto_finalize_transitions_to_transcribing(self, manager: SessionManager):
        """Auto-finalize should transition existing session to TRANSCRIBING."""
        # Create first session with audio
        session1 = manager.create_session(chat_id=123)
        audio = AudioEntry(
            sequence=1,
            received_at=datetime.now(timezone.utc),
            telegram_file_id="file_abc",
            local_filename="001_audio.ogg",
            file_size_bytes=1024,
        )
        manager.add_audio(session1.id, audio)

        # Create second session
        manager.create_session(chat_id=123)

        # Check first session state
        reloaded = manager.get_session(session1.id)
        assert reloaded.state == SessionState.TRANSCRIBING
        assert reloaded.finalized_at is not None

    def test_auto_finalize_sets_finalized_at(self, manager: SessionManager):
        """Auto-finalize should set finalized_at timestamp."""
        session1 = manager.create_session(chat_id=123)
        audio = AudioEntry(
            sequence=1,
            received_at=datetime.now(timezone.utc),
            telegram_file_id="file_abc",
            local_filename="001_audio.ogg",
            file_size_bytes=1024,
        )
        manager.add_audio(session1.id, audio)

        before = datetime.now(timezone.utc)
        manager.create_session(chat_id=123)
        after = datetime.now(timezone.utc)

        reloaded = manager.get_session(session1.id)
        assert reloaded.finalized_at is not None
        # Finalized timestamp should be recent
        assert reloaded.finalized_at >= before.replace(microsecond=0)

    def test_auto_finalize_empty_becomes_error(self, manager: SessionManager):
        """Auto-finalize of empty session should mark as ERROR."""
        session1 = manager.create_session(chat_id=123)
        # No audio added

        manager.create_session(chat_id=123)

        reloaded = manager.get_session(session1.id)
        assert reloaded.state == SessionState.ERROR

    def test_auto_finalize_empty_adds_error_entry(self, manager: SessionManager):
        """Auto-finalize of empty session should add error entry."""
        session1 = manager.create_session(chat_id=123)

        manager.create_session(chat_id=123)

        reloaded = manager.get_session(session1.id)
        assert len(reloaded.errors) > 0
        assert "auto-finalize" in reloaded.errors[0].operation

    def test_new_session_is_collecting(self, manager: SessionManager):
        """New session created after auto-finalize should be COLLECTING."""
        session1 = manager.create_session(chat_id=123)
        audio = AudioEntry(
            sequence=1,
            received_at=datetime.now(timezone.utc),
            telegram_file_id="file_abc",
            local_filename="001_audio.ogg",
            file_size_bytes=1024,
        )
        manager.add_audio(session1.id, audio)

        session2 = manager.create_session(chat_id=123)

        assert session2.state == SessionState.COLLECTING


class TestSessionProperties:
    """Test Session model properties."""

    def test_audio_count_empty(self):
        """Empty session should have audio_count 0."""
        session = Session(
            id="2025-12-18_14-30-00",
            state=SessionState.COLLECTING,
            created_at=datetime.now(timezone.utc),
            chat_id=123,
        )
        assert session.audio_count == 0

    def test_audio_count_with_entries(self):
        """Session should report correct audio count."""
        session = Session(
            id="2025-12-18_14-30-00",
            state=SessionState.COLLECTING,
            created_at=datetime.now(timezone.utc),
            chat_id=123,
        )
        session.audio_entries = [
            AudioEntry(
                sequence=1,
                received_at=datetime.now(timezone.utc),
                telegram_file_id="f1",
                local_filename="001.ogg",
                file_size_bytes=100,
            ),
            AudioEntry(
                sequence=2,
                received_at=datetime.now(timezone.utc),
                telegram_file_id="f2",
                local_filename="002.ogg",
                file_size_bytes=200,
            ),
        ]
        assert session.audio_count == 2

    def test_next_sequence_empty(self):
        """Empty session should have next_sequence 1."""
        session = Session(
            id="2025-12-18_14-30-00",
            state=SessionState.COLLECTING,
            created_at=datetime.now(timezone.utc),
            chat_id=123,
        )
        assert session.next_sequence == 1

    def test_next_sequence_increments(self):
        """next_sequence should be max + 1."""
        session = Session(
            id="2025-12-18_14-30-00",
            state=SessionState.COLLECTING,
            created_at=datetime.now(timezone.utc),
            chat_id=123,
        )
        session.audio_entries = [
            AudioEntry(
                sequence=1,
                received_at=datetime.now(timezone.utc),
                telegram_file_id="f1",
                local_filename="001.ogg",
                file_size_bytes=100,
            ),
        ]
        assert session.next_sequence == 2

    def test_is_finalized_collecting(self):
        """COLLECTING session should not be finalized."""
        session = Session(
            id="2025-12-18_14-30-00",
            state=SessionState.COLLECTING,
            created_at=datetime.now(timezone.utc),
            chat_id=123,
        )
        assert not session.is_finalized

    def test_is_finalized_transcribing(self):
        """TRANSCRIBING session should be finalized."""
        session = Session(
            id="2025-12-18_14-30-00",
            state=SessionState.TRANSCRIBING,
            created_at=datetime.now(timezone.utc),
            chat_id=123,
            finalized_at=datetime.now(timezone.utc),
        )
        assert session.is_finalized

    def test_can_add_audio_collecting(self):
        """COLLECTING session can add audio."""
        session = Session(
            id="2025-12-18_14-30-00",
            state=SessionState.COLLECTING,
            created_at=datetime.now(timezone.utc),
            chat_id=123,
        )
        assert session.can_add_audio

    def test_can_add_audio_finalized(self):
        """Finalized session cannot add audio."""
        session = Session(
            id="2025-12-18_14-30-00",
            state=SessionState.TRANSCRIBING,
            created_at=datetime.now(timezone.utc),
            chat_id=123,
        )
        assert not session.can_add_audio

    def test_can_finalize_with_audio(self):
        """Session with audio can be finalized."""
        session = Session(
            id="2025-12-18_14-30-00",
            state=SessionState.COLLECTING,
            created_at=datetime.now(timezone.utc),
            chat_id=123,
        )
        session.audio_entries = [
            AudioEntry(
                sequence=1,
                received_at=datetime.now(timezone.utc),
                telegram_file_id="f1",
                local_filename="001.ogg",
                file_size_bytes=100,
            ),
        ]
        assert session.can_finalize

    def test_can_finalize_empty(self):
        """Empty session cannot be finalized."""
        session = Session(
            id="2025-12-18_14-30-00",
            state=SessionState.COLLECTING,
            created_at=datetime.now(timezone.utc),
            chat_id=123,
        )
        assert not session.can_finalize

    def test_can_process_transcribed(self):
        """TRANSCRIBED session can process."""
        session = Session(
            id="2025-12-18_14-30-00",
            state=SessionState.TRANSCRIBED,
            created_at=datetime.now(timezone.utc),
            chat_id=123,
        )
        assert session.can_process

    def test_can_process_collecting(self):
        """COLLECTING session cannot process."""
        session = Session(
            id="2025-12-18_14-30-00",
            state=SessionState.COLLECTING,
            created_at=datetime.now(timezone.utc),
            chat_id=123,
        )
        assert not session.can_process


class TestNameSourceEnum:
    """Test NameSource enum for session name origins."""

    def test_name_source_values(self):
        """NameSource should have all expected values."""
        assert NameSource.FALLBACK_TIMESTAMP == "FALLBACK_TIMESTAMP"
        assert NameSource.TRANSCRIPTION == "TRANSCRIPTION"
        assert NameSource.LLM_TITLE == "LLM_TITLE"
        assert NameSource.USER_ASSIGNED == "USER_ASSIGNED"

    def test_name_source_is_string_enum(self):
        """NameSource values should be strings for JSON serialization."""
        for source in NameSource:
            assert isinstance(source.value, str)

    def test_name_source_from_string(self):
        """NameSource should be creatable from string."""
        assert NameSource("FALLBACK_TIMESTAMP") == NameSource.FALLBACK_TIMESTAMP
        assert NameSource("TRANSCRIPTION") == NameSource.TRANSCRIPTION

    def test_name_source_priority_order(self):
        """Document expected priority: FALLBACK < TRANSCRIPTION < LLM_TITLE < USER_ASSIGNED."""
        # Priority list from lowest to highest
        priority = [
            NameSource.FALLBACK_TIMESTAMP,
            NameSource.TRANSCRIPTION,
            NameSource.LLM_TITLE,
            NameSource.USER_ASSIGNED,
        ]
        # Verify all values are covered
        assert set(priority) == set(NameSource)


class TestMatchTypeEnum:
    """Test MatchType enum for session reference matching."""

    def test_match_type_values(self):
        """MatchType should have all expected values."""
        assert MatchType.EXACT_SUBSTRING == "EXACT_SUBSTRING"
        assert MatchType.FUZZY_SUBSTRING == "FUZZY_SUBSTRING"
        assert MatchType.SEMANTIC_SIMILARITY == "SEMANTIC_SIMILARITY"
        assert MatchType.ACTIVE_CONTEXT == "ACTIVE_CONTEXT"
        assert MatchType.AMBIGUOUS == "AMBIGUOUS"
        assert MatchType.NOT_FOUND == "NOT_FOUND"

    def test_match_type_is_string_enum(self):
        """MatchType values should be strings for JSON serialization."""
        for match_type in MatchType:
            assert isinstance(match_type.value, str)

    def test_match_type_from_string(self):
        """MatchType should be creatable from string."""
        assert MatchType("EXACT_SUBSTRING") == MatchType.EXACT_SUBSTRING
        assert MatchType("NOT_FOUND") == MatchType.NOT_FOUND


class TestSessionMatch:
    """Test SessionMatch dataclass for reference resolution results."""

    def test_session_match_creation(self):
        """SessionMatch should be creatable with required fields."""
        match = SessionMatch(
            session_id="2025-12-18_14-30-00",
            confidence=1.0,
            match_type=MatchType.EXACT_SUBSTRING,
        )
        assert match.session_id == "2025-12-18_14-30-00"
        assert match.confidence == 1.0
        assert match.match_type == MatchType.EXACT_SUBSTRING
        assert match.candidates == []  # Default empty list

    def test_session_match_with_candidates(self):
        """SessionMatch should support candidate list for ambiguous matches."""
        match = SessionMatch(
            session_id=None,
            confidence=0.9,
            match_type=MatchType.AMBIGUOUS,
            candidates=["session-1", "session-2"],
        )
        assert match.session_id is None
        assert match.match_type == MatchType.AMBIGUOUS
        assert len(match.candidates) == 2

    def test_session_match_not_found(self):
        """SessionMatch for NOT_FOUND should have zero confidence."""
        match = SessionMatch(
            session_id=None,
            confidence=0.0,
            match_type=MatchType.NOT_FOUND,
        )
        assert match.session_id is None
        assert match.confidence == 0.0
        assert match.match_type == MatchType.NOT_FOUND


class TestSessionNewFields:
    """Test new Session fields for auto-session feature."""

    def test_session_default_name_source(self):
        """New session should have FALLBACK_TIMESTAMP as default."""
        session = Session(
            id="2025-12-18_14-30-00",
            state=SessionState.COLLECTING,
            created_at=datetime.now(timezone.utc),
            chat_id=123,
        )
        assert session.name_source == NameSource.FALLBACK_TIMESTAMP

    def test_session_default_intelligible_name(self):
        """New session should have empty intelligible_name by default."""
        session = Session(
            id="2025-12-18_14-30-00",
            state=SessionState.COLLECTING,
            created_at=datetime.now(timezone.utc),
            chat_id=123,
        )
        assert session.intelligible_name == ""

    def test_session_default_embedding(self):
        """New session should have None embedding by default."""
        session = Session(
            id="2025-12-18_14-30-00",
            state=SessionState.COLLECTING,
            created_at=datetime.now(timezone.utc),
            chat_id=123,
        )
        assert session.embedding is None

    def test_session_with_all_new_fields(self):
        """Session should support all new fields."""
        embedding = [0.1] * 384  # 384-dim vector
        session = Session(
            id="2025-12-18_14-30-00",
            state=SessionState.COLLECTING,
            created_at=datetime.now(timezone.utc),
            chat_id=123,
            intelligible_name="Áudio de 18 de Dezembro",
            name_source=NameSource.FALLBACK_TIMESTAMP,
            embedding=embedding,
        )
        assert session.intelligible_name == "Áudio de 18 de Dezembro"
        assert session.name_source == NameSource.FALLBACK_TIMESTAMP
        assert len(session.embedding) == 384

    def test_session_to_dict_includes_new_fields(self):
        """Session.to_dict() should include new fields."""
        session = Session(
            id="2025-12-18_14-30-00",
            state=SessionState.COLLECTING,
            created_at=datetime.now(timezone.utc),
            chat_id=123,
            intelligible_name="Test Session",
            name_source=NameSource.TRANSCRIPTION,
        )
        data = session.to_dict()

        assert "intelligible_name" in data
        assert data["intelligible_name"] == "Test Session"
        assert "name_source" in data
        assert data["name_source"] == "TRANSCRIPTION"
        assert "embedding" in data

    def test_session_from_dict_handles_new_fields(self):
        """Session.from_dict() should handle new fields."""
        data = {
            "id": "2025-12-18_14-30-00",
            "state": "COLLECTING",
            "created_at": "2025-12-18T14:30:00",
            "chat_id": 123,
            "intelligible_name": "Test Session",
            "name_source": "TRANSCRIPTION",
            "embedding": [0.5] * 384,
        }
        session = Session.from_dict(data)

        assert session.intelligible_name == "Test Session"
        assert session.name_source == NameSource.TRANSCRIPTION
        assert len(session.embedding) == 384

    def test_session_from_dict_handles_missing_new_fields(self):
        """Session.from_dict() should handle legacy data without new fields."""
        # Simulating old session data without new fields
        data = {
            "id": "2025-12-18_14-30-00",
            "state": "COLLECTING",
            "created_at": "2025-12-18T14:30:00",
            "chat_id": 123,
        }
        session = Session.from_dict(data)

        # Should use defaults
        assert session.intelligible_name == ""
        assert session.name_source == NameSource.FALLBACK_TIMESTAMP
        assert session.embedding is None
