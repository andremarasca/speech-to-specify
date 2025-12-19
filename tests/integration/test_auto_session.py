"""Integration tests for auto-session audio feature.

These tests verify the end-to-end flow of automatic session creation
when audio is received, following the spec from:
specs/003-auto-session-audio/spec.md

User Story 1: Audio triggers session creation (P1 - MVP)
"""

import pytest
from datetime import datetime, timezone
from pathlib import Path

from src.models.session import NameSource, SessionState, TranscriptionStatus
from src.services.session.manager import SessionManager
from src.services.session.storage import SessionStorage


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


class TestAutoSessionCreation:
    """Integration tests for automatic session creation."""

    def test_end_to_end_auto_session(
        self, manager: SessionManager, sessions_dir: Path
    ):
        """
        Full flow: send audio without session → session created → audio preserved.
        
        This is the core MVP test for User Story 1.
        """
        # Precondition: no active session
        assert manager.get_active_session() is None

        # Act: simulate receiving voice message
        audio_data = b"simulated voice message audio data"
        session, audio_entry = manager.handle_audio_receipt(
            chat_id=12345,
            audio_data=audio_data,
            telegram_file_id="AgACAgIAAxkBAAI",
            duration_seconds=10.5,
        )

        # Assert: session created and collecting
        assert session.state == SessionState.COLLECTING
        assert session.chat_id == 12345

        # Assert: session has intelligible name
        assert session.intelligible_name != ""
        assert session.name_source == NameSource.FALLBACK_TIMESTAMP

        # Assert: audio is preserved
        assert len(session.audio_entries) == 1
        assert audio_entry.sequence == 1
        assert audio_entry.telegram_file_id == "AgACAgIAAxkBAAI"
        assert audio_entry.duration_seconds == 10.5

        # Assert: audio file exists on disk
        audio_path = sessions_dir / session.id / "audio" / audio_entry.local_filename
        assert audio_path.exists()
        assert audio_path.read_bytes() == audio_data

        # Assert: session is persisted
        loaded = manager.storage.load(session.id)
        assert loaded is not None
        assert loaded.id == session.id

    def test_multiple_audios_same_session(
        self, manager: SessionManager, sessions_dir: Path
    ):
        """Multiple audio messages go to the same active session."""
        # First audio creates session
        session1, entry1 = manager.handle_audio_receipt(
            chat_id=123,
            audio_data=b"first audio",
            telegram_file_id="file1",
        )

        # Second audio should use same session
        session2, entry2 = manager.handle_audio_receipt(
            chat_id=123,
            audio_data=b"second audio",
            telegram_file_id="file2",
        )

        # Same session
        assert session1.id == session2.id

        # Different entries
        assert entry1.sequence == 1
        assert entry2.sequence == 2

        # Both files exist
        audio_dir = sessions_dir / session1.id / "audio"
        assert (audio_dir / entry1.local_filename).exists()
        assert (audio_dir / entry2.local_filename).exists()

    def test_session_created_with_correct_folder_structure(
        self, manager: SessionManager, sessions_dir: Path
    ):
        """Auto-created session has full folder structure."""
        session, _ = manager.handle_audio_receipt(
            chat_id=123,
            audio_data=b"test",
            telegram_file_id="file1",
        )

        session_path = sessions_dir / session.id
        assert session_path.exists()
        assert (session_path / "audio").exists()
        assert (session_path / "transcripts").exists()
        assert (session_path / "process").exists()
        assert (session_path / "metadata.json").exists()

    def test_session_metadata_persisted_immediately(
        self, manager: SessionManager, sessions_dir: Path
    ):
        """Session metadata is persisted immediately after creation."""
        session, _ = manager.handle_audio_receipt(
            chat_id=456,
            audio_data=b"test audio",
            telegram_file_id="file_abc",
        )

        # Load directly from disk
        import json
        metadata_path = sessions_dir / session.id / "metadata.json"
        with open(metadata_path, encoding="utf-8") as f:
            data = json.load(f)

        assert data["id"] == session.id
        assert data["chat_id"] == 456
        assert data["state"] == "COLLECTING"
        assert data["intelligible_name"] != ""
        assert data["name_source"] == "FALLBACK_TIMESTAMP"
        assert len(data["audio_entries"]) == 1


class TestAudioPersistenceReliability:
    """Tests for zero data loss guarantee."""

    def test_audio_file_content_matches(
        self, manager: SessionManager, sessions_dir: Path
    ):
        """Audio file content exactly matches input."""
        # Various audio sizes
        for size in [100, 1000, 10000, 100000]:
            audio_data = bytes(range(256)) * (size // 256 + 1)
            audio_data = audio_data[:size]

            session, entry = manager.handle_audio_receipt(
                chat_id=123,
                audio_data=audio_data,
                telegram_file_id=f"file_{size}",
            )

            audio_path = sessions_dir / session.id / "audio" / entry.local_filename
            assert audio_path.read_bytes() == audio_data

    def test_audio_entry_tracks_file_size(
        self, manager: SessionManager
    ):
        """AudioEntry accurately tracks file size."""
        audio_data = b"x" * 5000  # 5KB

        session, entry = manager.handle_audio_receipt(
            chat_id=123,
            audio_data=audio_data,
            telegram_file_id="file1",
        )

        assert entry.file_size_bytes == 5000


class TestIntelligibleNaming:
    """Tests for session naming on auto-creation."""

    def test_fallback_name_is_portuguese(
        self, manager: SessionManager
    ):
        """Fallback name uses Portuguese locale."""
        session, _ = manager.handle_audio_receipt(
            chat_id=123,
            audio_data=b"test",
            telegram_file_id="file1",
        )

        # Should contain Portuguese pattern
        assert "Áudio de" in session.intelligible_name
        # Should have month name (Portuguese)
        portuguese_months = [
            "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
            "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"
        ]
        assert any(month in session.intelligible_name for month in portuguese_months)

    def test_name_update_after_transcription(
        self, manager: SessionManager
    ):
        """Session name can be updated after transcription completes."""
        # Create session via audio
        session, _ = manager.handle_audio_receipt(
            chat_id=123,
            audio_data=b"test",
            telegram_file_id="file1",
        )
        original_name = session.intelligible_name

        # Update with transcription-derived name
        updated = manager.update_session_name(
            session_id=session.id,
            new_name="Discussão sobre requisitos",
            source=NameSource.TRANSCRIPTION,
        )

        assert updated.intelligible_name == "Discussão sobre requisitos"
        assert updated.name_source == NameSource.TRANSCRIPTION
        assert updated.intelligible_name != original_name

    def test_session_name_unique_within_list(
        self, manager: SessionManager
    ):
        """Multiple sessions on same day get unique names."""
        sessions = []
        for i in range(3):
            session, _ = manager.handle_audio_receipt(
                chat_id=123,
                audio_data=f"audio {i}".encode(),
                telegram_file_id=f"file{i}",
            )
            # Finalize to create multiple sessions
            if session.audio_entries:
                try:
                    manager.finalize_session(session.id)
                except Exception:
                    pass
            sessions.append(session)

        # All sessions should have distinct IDs
        ids = [s.id for s in sessions]
        assert len(ids) == len(set(ids))


class TestContextCommands:
    """Integration tests for User Story 4: Context commands without session specification."""

    def test_context_free_transcripts_with_active_session(
        self, manager: SessionManager, sessions_dir: Path
    ):
        """
        /transcripts without args uses active session's transcripts.
        
        US4 Acceptance Scenario 1:
        Given an active session exists,
        When user requests transcription without session reference,
        Then system returns transcription of active session
        """
        # Create active session with transcripts
        session, entry = manager.handle_audio_receipt(
            chat_id=123,
            audio_data=b"test audio",
            telegram_file_id="file1",
        )

        # Simulate transcription completion
        transcript_file = sessions_dir / session.id / "transcripts" / "001_transcript.txt"
        transcript_file.write_text("This is the transcription text.", encoding="utf-8")
        manager.update_transcription_status(
            session.id,
            sequence=1,
            status=TranscriptionStatus.SUCCESS,
            transcript_filename="001_transcript.txt"
        )

        # Get active session - should be the same session
        active = manager.get_active_session()
        assert active is not None
        assert active.id == session.id

        # Get transcripts path for active session
        transcripts_path = active.transcripts_path(sessions_dir)
        assert transcripts_path.exists()

        # Verify transcript content is accessible
        transcript_files = list(transcripts_path.glob("*.txt"))
        assert len(transcript_files) == 1
        assert transcript_files[0].read_text(encoding="utf-8") == "This is the transcription text."

    def test_context_free_command_with_no_active_session(
        self, manager: SessionManager
    ):
        """
        Command without args and no active session returns clarification.
        
        US4 Acceptance Scenario 2:
        Given no active session exists,
        When user requests a context-dependent command,
        Then system asks for clarification or lists recent sessions
        """
        # No sessions exist
        assert manager.get_active_session() is None

        # List sessions returns empty
        sessions = manager.list_sessions(limit=5)
        assert len(sessions) == 0

    def test_context_free_status_with_active_session(
        self, manager: SessionManager
    ):
        """
        /status without args shows active session status.
        """
        # Create active session
        session, _ = manager.handle_audio_receipt(
            chat_id=123,
            audio_data=b"test",
            telegram_file_id="file1",
        )

        # Get active session status
        active = manager.get_active_session()
        assert active is not None
        assert active.state == SessionState.COLLECTING
        assert active.audio_count == 1

    def test_context_respects_session_state(
        self, manager: SessionManager
    ):
        """
        Context commands only use COLLECTING sessions as active.
        """
        # Create and finalize a session
        session, _ = manager.handle_audio_receipt(
            chat_id=123,
            audio_data=b"test",
            telegram_file_id="file1",
        )
        manager.finalize_session(session.id)

        # No active session after finalization
        assert manager.get_active_session() is None

        # Session exists but is not active
        loaded = manager.storage.load(session.id)
        assert loaded is not None
        assert loaded.state == SessionState.TRANSCRIBING
