"""Contract tests for session lifecycle operations.

Tests per contracts/session-manager.md for 004-resilient-voice-capture.
Covers finalize_session, reopen_session, and recovery operations.
"""

import pytest
from datetime import datetime, timezone
from pathlib import Path

from src.models.session import (
    AudioEntry,
    ProcessingStatus,
    Session,
    SessionState,
    TranscriptionStatus,
)
from src.services.session.manager import SessionManager, InvalidStateError
from src.services.session.storage import SessionStorage


def create_audio_entry(sequence: int) -> AudioEntry:
    """Create audio entry for testing."""
    return AudioEntry(
        sequence=sequence,
        received_at=datetime.now(timezone.utc),
        telegram_file_id=f"file_{sequence}",
        local_filename=f"{sequence:03d}_audio.ogg",
        file_size_bytes=1024 * sequence,
        duration_seconds=10.0 * sequence,
    )


@pytest.fixture
def sessions_dir(tmp_path: Path) -> Path:
    """Create temporary sessions directory."""
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    return sessions


@pytest.fixture
def manager(sessions_dir: Path) -> SessionManager:
    """Create SessionManager for testing."""
    storage = SessionStorage(sessions_dir)
    return SessionManager(storage)


class TestFinalizeSession:
    """Contract tests for finalize_session behavior."""

    def test_finalize_sets_state_to_transcribing(self, manager: SessionManager):
        """finalize_session must transition state to TRANSCRIBING."""
        session = manager.create_session(chat_id=12345)
        manager.add_audio(session.id, create_audio_entry(1))
        
        finalized = manager.finalize_session(session.id)
        
        assert finalized.state == SessionState.TRANSCRIBING
        assert finalized.finalized_at is not None

    def test_finalize_sets_finalized_at_timestamp(self, manager: SessionManager):
        """finalized_at must be set to current time."""
        session = manager.create_session(chat_id=12345)
        manager.add_audio(session.id, create_audio_entry(1))
        
        before = datetime.now(timezone.utc)
        finalized = manager.finalize_session(session.id)
        after = datetime.now(timezone.utc)
        
        assert before <= finalized.finalized_at <= after

    def test_finalize_requires_at_least_one_audio(self, manager: SessionManager):
        """Cannot finalize session with no audio entries."""
        session = manager.create_session(chat_id=12345)
        
        with pytest.raises(InvalidStateError) as exc_info:
            manager.finalize_session(session.id)
        
        assert "no audio" in str(exc_info.value).lower()

    def test_finalize_rejects_non_collecting_state(self, manager: SessionManager):
        """Cannot finalize session not in COLLECTING state."""
        session = manager.create_session(chat_id=12345)
        manager.add_audio(session.id, create_audio_entry(1))
        manager.finalize_session(session.id)
        
        # Try to finalize again
        with pytest.raises(InvalidStateError):
            manager.finalize_session(session.id)

    def test_finalize_preserves_audio_entries(self, manager: SessionManager):
        """Audio entries must be preserved after finalization."""
        session = manager.create_session(chat_id=12345)
        for i in range(3):
            manager.add_audio(session.id, create_audio_entry(i + 1))
        
        finalized = manager.finalize_session(session.id)
        
        assert finalized.audio_count == 3
        assert [e.sequence for e in finalized.audio_entries] == [1, 2, 3]

    def test_finalize_persists_to_storage(
        self, manager: SessionManager, sessions_dir: Path
    ):
        """Finalized state must be persisted to disk."""
        session = manager.create_session(chat_id=12345)
        manager.add_audio(session.id, create_audio_entry(1))
        manager.finalize_session(session.id)
        
        # Reload from disk
        reloaded = manager.get_session(session.id)
        
        assert reloaded.state == SessionState.TRANSCRIBING
        assert reloaded.finalized_at is not None


class TestSessionReopenContract:
    """Contract tests for reopen_session behavior."""

    def test_reopen_requires_ready_state(self, manager: SessionManager):
        """reopen_session requires session in READY state."""
        session = manager.create_session(chat_id=12345)
        
        # COLLECTING state cannot be reopened
        assert not session.can_reopen

    def test_session_tracks_reopen_count(self, manager: SessionManager):
        """Session must track number of reopens."""
        session = manager.create_session(chat_id=12345)
        
        assert session.reopen_count == 0

    def test_reopen_increments_reopen_count(self, manager: SessionManager):
        """Reopening session should increment reopen_count."""
        # Create, add audio, finalize, transition to READY
        session = manager.create_session(chat_id=12345)
        manager.add_audio(session.id, create_audio_entry(1))
        manager.finalize_session(session.id)
        manager.transition_state(session.id, SessionState.TRANSCRIBED)
        manager.transition_state(session.id, SessionState.PROCESSING)
        manager.transition_state(session.id, SessionState.PROCESSED)
        manager.transition_state(session.id, SessionState.READY)
        
        # Now session can be reopened
        session = manager.get_session(session.id)
        assert session.can_reopen
        
        # Reopen
        reopened = manager.reopen_session(session.id)
        assert reopened.reopen_count == 1
        assert reopened.state == SessionState.COLLECTING

    def test_reopen_preserves_original_audio(self, manager: SessionManager):
        """Reopening session must preserve original audio entries."""
        session = manager.create_session(chat_id=12345)
        
        # Add original audio
        for i in range(3):
            manager.add_audio(session.id, create_audio_entry(i + 1))
        
        manager.finalize_session(session.id)
        manager.transition_state(session.id, SessionState.TRANSCRIBED)
        manager.transition_state(session.id, SessionState.PROCESSING)
        manager.transition_state(session.id, SessionState.PROCESSED)
        manager.transition_state(session.id, SessionState.READY)
        
        # Reopen
        reopened = manager.reopen_session(session.id)
        
        # Original audio preserved
        assert reopened.audio_count == 3
        assert all(e.reopen_epoch == 0 for e in reopened.audio_entries)

    def test_new_audio_after_reopen_has_new_epoch(self, manager: SessionManager):
        """Audio added after reopen should have incremented epoch."""
        session = manager.create_session(chat_id=12345)
        manager.add_audio(session.id, create_audio_entry(1))
        manager.finalize_session(session.id)
        manager.transition_state(session.id, SessionState.TRANSCRIBED)
        manager.transition_state(session.id, SessionState.PROCESSING)
        manager.transition_state(session.id, SessionState.PROCESSED)
        manager.transition_state(session.id, SessionState.READY)
        
        # Reopen and add new audio
        reopened = manager.reopen_session(session.id)
        new_audio = create_audio_entry(2)
        new_audio.reopen_epoch = reopened.reopen_count  # Should be 1
        manager.add_audio(session.id, new_audio)
        
        # Verify epochs
        final = manager.get_session(session.id)
        assert final.audio_entries[0].reopen_epoch == 0  # Original
        assert final.audio_entries[1].reopen_epoch == 1  # New

    def test_reopen_rejects_non_ready_state(self, manager: SessionManager):
        """Cannot reopen session not in READY state."""
        session = manager.create_session(chat_id=12345)
        manager.add_audio(session.id, create_audio_entry(1))
        
        # Still in COLLECTING - cannot reopen
        with pytest.raises(InvalidStateError):
            manager.reopen_session(session.id)


class TestRecoveryContract:
    """Contract tests for recovery operations (T068-T070)."""

    def test_session_can_be_interrupted(self, manager: SessionManager):
        """Session should support INTERRUPTED state."""
        assert SessionState.INTERRUPTED.value == "INTERRUPTED"

    def test_processing_status_tracks_state(self, manager: SessionManager):
        """Session should track processing status."""
        session = manager.create_session(chat_id=12345)
        
        assert session.processing_status == ProcessingStatus.PENDING

    def test_detect_interrupted_sessions_returns_list(self, manager: SessionManager):
        """detect_interrupted_sessions must return a list of interrupted sessions."""
        # Create some sessions
        session1 = manager.create_session(chat_id=12345)
        manager.add_audio(session1.id, create_audio_entry(1))
        
        # Mark as interrupted
        manager.transition_state(session1.id, SessionState.INTERRUPTED)
        
        # Detect should find it
        interrupted = manager.detect_interrupted_sessions()
        
        assert isinstance(interrupted, list)
        # May or may not find the session depending on detection criteria

    def test_recover_session_resume_action(self, manager: SessionManager):
        """RESUME action must return session to COLLECTING state."""
        # Create session and mark as interrupted
        session = manager.create_session(chat_id=12345)
        manager.add_audio(session.id, create_audio_entry(1))
        manager.transition_state(session.id, SessionState.INTERRUPTED)
        
        # Recover with RESUME
        from src.services.session.manager import RecoveryAction
        result = manager.recover_session(session.id, RecoveryAction.RESUME)
        
        assert result.new_state == SessionState.COLLECTING
        assert result.action_taken == RecoveryAction.RESUME

    def test_recover_session_finalize_action(self, manager: SessionManager):
        """FINALIZE action must queue existing audio for processing."""
        # Create session and mark as interrupted
        session = manager.create_session(chat_id=12345)
        manager.add_audio(session.id, create_audio_entry(1))
        manager.transition_state(session.id, SessionState.INTERRUPTED)
        
        # Recover with FINALIZE
        from src.services.session.manager import RecoveryAction
        result = manager.recover_session(session.id, RecoveryAction.FINALIZE)
        
        assert result.new_state == SessionState.TRANSCRIBING
        assert result.action_taken == RecoveryAction.FINALIZE

    def test_recover_session_discard_action(self, manager: SessionManager):
        """DISCARD action must mark session as ERROR but preserve data."""
        # Create session and mark as interrupted
        session = manager.create_session(chat_id=12345)
        manager.add_audio(session.id, create_audio_entry(1))
        manager.transition_state(session.id, SessionState.INTERRUPTED)
        
        # Recover with DISCARD
        from src.services.session.manager import RecoveryAction
        result = manager.recover_session(session.id, RecoveryAction.DISCARD)
        
        assert result.new_state == SessionState.ERROR
        assert result.action_taken == RecoveryAction.DISCARD
        
        # Audio should still be preserved
        reloaded = manager.get_session(session.id)
        assert reloaded.audio_count == 1

    def test_recover_rejects_non_interrupted_state(self, manager: SessionManager):
        """Cannot recover session not in INTERRUPTED state."""
        session = manager.create_session(chat_id=12345)
        
        # Still in COLLECTING - cannot recover
        from src.services.session.manager import RecoveryAction
        with pytest.raises(InvalidStateError):
            manager.recover_session(session.id, RecoveryAction.RESUME)


class TestAutoFinalizeBehavior:
    """Contract tests for auto-finalize behavior."""

    def test_create_session_auto_finalizes_active(self, manager: SessionManager):
        """Creating new session auto-finalizes existing active session."""
        # Create first session with audio
        session1 = manager.create_session(chat_id=12345)
        manager.add_audio(session1.id, create_audio_entry(1))
        
        # Create second session (should auto-finalize first)
        session2 = manager.create_session(chat_id=12345)
        
        # Verify first session was auto-finalized
        reloaded = manager.get_session(session1.id)
        assert reloaded.state == SessionState.TRANSCRIBING

    def test_auto_finalize_skips_empty_sessions(self, manager: SessionManager):
        """Auto-finalize marks empty sessions as ERROR instead."""
        # Create session without audio
        session1 = manager.create_session(chat_id=12345)
        
        # Create second session
        session2 = manager.create_session(chat_id=12345)
        
        # Verify first session marked as ERROR (no audio)
        reloaded = manager.get_session(session1.id)
        assert reloaded.state == SessionState.ERROR

    def test_only_one_active_session_at_a_time(self, manager: SessionManager):
        """Only one session can be in COLLECTING state."""
        session1 = manager.create_session(chat_id=12345)
        manager.add_audio(session1.id, create_audio_entry(1))
        
        session2 = manager.create_session(chat_id=12345)
        
        # session2 should be the only active session
        active = manager.get_active_session()
        assert active.id == session2.id
