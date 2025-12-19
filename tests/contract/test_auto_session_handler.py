"""Contract tests for auto-session handler.

These tests verify the SessionManager extension for automatic session
creation when audio is received without an active session.

Tests follow the contract defined in:
specs/003-auto-session-audio/contracts/auto-session-handler.md
"""

import pytest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.models.session import NameSource, Session, SessionState
from src.services.session.manager import SessionManager
from src.services.session.storage import SessionStorage


@pytest.fixture
def sessions_dir(tmp_path: Path) -> Path:
    """Create a temporary sessions directory."""
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    return sessions


@pytest.fixture
def temp_dir(tmp_path: Path) -> Path:
    """Create a temporary directory for audio files."""
    temp = tmp_path / "temp"
    temp.mkdir()
    return temp


@pytest.fixture
def storage(sessions_dir: Path) -> SessionStorage:
    """Create a SessionStorage instance."""
    return SessionStorage(sessions_dir)


@pytest.fixture
def manager(storage: SessionStorage) -> SessionManager:
    """Create a SessionManager instance."""
    return SessionManager(storage)


class TestHandleAudioReceipt:
    """Contract tests for handle_audio_receipt()."""

    def test_audio_receipt_creates_session_when_none(
        self, manager: SessionManager, sessions_dir: Path
    ):
        """Audio with no active session creates new session."""
        # Precondition: no active session
        assert manager.get_active_session() is None

        # Act: receive audio
        audio_data = b"fake audio data"
        session, audio_entry = manager.handle_audio_receipt(
            chat_id=123,
            audio_data=audio_data,
            telegram_file_id="file123",
            duration_seconds=5.0,
        )

        # Assert: session was created
        assert session is not None
        assert session.state == SessionState.COLLECTING
        assert session.chat_id == 123
        assert len(session.audio_entries) == 1
        assert audio_entry.sequence == 1

    def test_audio_receipt_uses_active_session(
        self, manager: SessionManager
    ):
        """Audio with active session adds to that session."""
        # Setup: create an active session first
        existing_session = manager.create_session(chat_id=123)
        existing_id = existing_session.id

        # Act: receive audio
        audio_data = b"fake audio data"
        session, audio_entry = manager.handle_audio_receipt(
            chat_id=123,
            audio_data=audio_data,
            telegram_file_id="file123",
        )

        # Assert: same session used
        assert session.id == existing_id
        assert len(session.audio_entries) == 1

    def test_audio_persisted_to_session_folder(
        self, manager: SessionManager, sessions_dir: Path
    ):
        """Audio is saved to session's audio folder."""
        audio_data = b"test audio content"

        session, audio_entry = manager.handle_audio_receipt(
            chat_id=123,
            audio_data=audio_data,
            telegram_file_id="file123",
        )

        # Check audio file exists
        audio_path = sessions_dir / session.id / "audio" / audio_entry.local_filename
        assert audio_path.exists()
        assert audio_path.read_bytes() == audio_data

    def test_session_created_with_fallback_name(
        self, manager: SessionManager
    ):
        """New session has fallback timestamp name."""
        session, _ = manager.handle_audio_receipt(
            chat_id=123,
            audio_data=b"test",
            telegram_file_id="file123",
        )

        # Should have Portuguese fallback name
        assert session.intelligible_name != ""
        assert "Áudio de" in session.intelligible_name
        assert session.name_source == NameSource.FALLBACK_TIMESTAMP

    def test_audio_entry_has_correct_metadata(
        self, manager: SessionManager
    ):
        """AudioEntry captures all required metadata."""
        audio_data = b"x" * 1000  # 1000 bytes

        session, audio_entry = manager.handle_audio_receipt(
            chat_id=123,
            audio_data=audio_data,
            telegram_file_id="telegram_file_abc",
            duration_seconds=3.5,
        )

        assert audio_entry.telegram_file_id == "telegram_file_abc"
        assert audio_entry.file_size_bytes == 1000
        assert audio_entry.duration_seconds == 3.5
        assert audio_entry.local_filename.endswith(".ogg")


class TestGetOrCreateSession:
    """Contract tests for get_or_create_session()."""

    def test_returns_existing_active_session(
        self, manager: SessionManager
    ):
        """Returns existing active session if available."""
        # Setup: create active session
        existing = manager.create_session(chat_id=123)

        # Act
        session, was_created = manager.get_or_create_session(chat_id=123)

        # Assert
        assert session.id == existing.id
        assert was_created is False

    def test_creates_session_when_none_active(
        self, manager: SessionManager
    ):
        """Creates new session if no active session exists."""
        # Precondition
        assert manager.get_active_session() is None

        # Act
        session, was_created = manager.get_or_create_session(chat_id=123)

        # Assert
        assert session is not None
        assert was_created is True
        assert session.state == SessionState.COLLECTING

    def test_created_session_has_intelligible_name(
        self, manager: SessionManager
    ):
        """Newly created session has intelligible name set."""
        session, was_created = manager.get_or_create_session(chat_id=123)

        assert was_created is True
        assert session.intelligible_name != ""
        assert session.name_source == NameSource.FALLBACK_TIMESTAMP


class TestUpdateSessionName:
    """Contract tests for update_session_name()."""

    def test_update_from_fallback_to_transcription(
        self, manager: SessionManager
    ):
        """FALLBACK_TIMESTAMP can be upgraded to TRANSCRIPTION."""
        # Setup: create session with fallback name
        session, _ = manager.get_or_create_session(chat_id=123)
        original_name = session.intelligible_name

        # Act: update with transcription-derived name
        updated = manager.update_session_name(
            session_id=session.id,
            new_name="Reunião sobre projeto",
            source=NameSource.TRANSCRIPTION,
        )

        # Assert
        assert updated.intelligible_name == "Reunião sobre projeto"
        assert updated.name_source == NameSource.TRANSCRIPTION
        assert updated.intelligible_name != original_name

    def test_update_from_transcription_to_llm_title(
        self, manager: SessionManager
    ):
        """TRANSCRIPTION can be upgraded to LLM_TITLE."""
        # Setup
        session, _ = manager.get_or_create_session(chat_id=123)
        manager.update_session_name(
            session_id=session.id,
            new_name="Reunião projeto",
            source=NameSource.TRANSCRIPTION,
        )

        # Act
        updated = manager.update_session_name(
            session_id=session.id,
            new_name="Plano de Implementação Q1",
            source=NameSource.LLM_TITLE,
        )

        # Assert
        assert updated.intelligible_name == "Plano de Implementação Q1"
        assert updated.name_source == NameSource.LLM_TITLE

    def test_lower_priority_does_not_overwrite(
        self, manager: SessionManager
    ):
        """Lower priority source cannot overwrite higher."""
        # Setup: session with LLM_TITLE
        session, _ = manager.get_or_create_session(chat_id=123)
        manager.update_session_name(
            session_id=session.id,
            new_name="LLM Generated Title",
            source=NameSource.LLM_TITLE,
        )

        # Act: try to update with TRANSCRIPTION (lower priority)
        updated = manager.update_session_name(
            session_id=session.id,
            new_name="Should Not Change",
            source=NameSource.TRANSCRIPTION,
        )

        # Assert: name unchanged
        assert updated.intelligible_name == "LLM Generated Title"
        assert updated.name_source == NameSource.LLM_TITLE

    def test_user_assigned_always_wins(
        self, manager: SessionManager
    ):
        """USER_ASSIGNED can overwrite any source."""
        # Setup: session with LLM_TITLE
        session, _ = manager.get_or_create_session(chat_id=123)
        manager.update_session_name(
            session_id=session.id,
            new_name="LLM Title",
            source=NameSource.LLM_TITLE,
        )

        # Act: update with USER_ASSIGNED
        updated = manager.update_session_name(
            session_id=session.id,
            new_name="My Custom Name",
            source=NameSource.USER_ASSIGNED,
        )

        # Assert
        assert updated.intelligible_name == "My Custom Name"
        assert updated.name_source == NameSource.USER_ASSIGNED

    def test_user_assigned_cannot_be_overwritten(
        self, manager: SessionManager
    ):
        """USER_ASSIGNED name is final - cannot be overwritten."""
        # Setup
        session, _ = manager.get_or_create_session(chat_id=123)
        manager.update_session_name(
            session_id=session.id,
            new_name="User's Choice",
            source=NameSource.USER_ASSIGNED,
        )

        # Act: try to update with any source
        for source in [NameSource.TRANSCRIPTION, NameSource.LLM_TITLE]:
            updated = manager.update_session_name(
                session_id=session.id,
                new_name="Attempt Override",
                source=source,
            )
            assert updated.intelligible_name == "User's Choice"
            assert updated.name_source == NameSource.USER_ASSIGNED
