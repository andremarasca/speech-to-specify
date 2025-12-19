"""Integration tests for crash recovery flow.

Tests complete crash recovery workflow including detection,
recovery actions, and command handlers.
"""

import pytest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.models.session import (
    AudioEntry,
    Session,
    SessionState,
    TranscriptionStatus,
)
from src.services.session.storage import SessionStorage
from src.services.session.manager import (
    SessionManager,
    RecoveryAction,
    RecoverResult,
    InterruptedSession,
    InvalidStateError,
)


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


class TestCrashRecoveryWorkflow:
    """Test complete crash recovery workflow."""
    
    def test_detect_interrupted_session(self, manager: SessionManager):
        """Test detection of interrupted sessions."""
        # Create session and mark as interrupted
        session = manager.create_session(chat_id=12345)
        manager.add_audio(session.id, create_audio_entry(1))
        manager.transition_state(session.id, SessionState.INTERRUPTED)
        
        # Detect interrupted sessions
        interrupted = manager.detect_interrupted_sessions()
        
        assert len(interrupted) >= 1
        found = next((i for i in interrupted if i.session_id == session.id), None)
        assert found is not None
        assert found.audio_count == 1
        assert RecoveryAction.RESUME in found.recovery_options
    
    def test_recovery_resume_workflow(self, manager: SessionManager):
        """Test full resume workflow: detect → resume → continue recording."""
        # Setup: Create and interrupt session
        session = manager.create_session(chat_id=12345)
        manager.add_audio(session.id, create_audio_entry(1))
        manager.transition_state(session.id, SessionState.INTERRUPTED)
        
        # Verify session is interrupted
        interrupted = manager.get_session(session.id)
        assert interrupted.state == SessionState.INTERRUPTED
        
        # Recover with RESUME
        result = manager.recover_session(session.id, RecoveryAction.RESUME)
        
        assert result.new_state == SessionState.COLLECTING
        assert "recovered" in result.message.lower() or "resumed" in result.message.lower()
        
        # Verify we can continue recording
        manager.add_audio(session.id, create_audio_entry(2))
        updated = manager.get_session(session.id)
        assert updated.audio_count == 2
    
    def test_recovery_finalize_workflow(self, manager: SessionManager):
        """Test finalize workflow: interrupt → finalize → process."""
        # Setup: Create and interrupt session with audio
        session = manager.create_session(chat_id=12345)
        manager.add_audio(session.id, create_audio_entry(1))
        manager.add_audio(session.id, create_audio_entry(2))
        manager.transition_state(session.id, SessionState.INTERRUPTED)
        
        # Recover with FINALIZE
        result = manager.recover_session(session.id, RecoveryAction.FINALIZE)
        
        assert result.new_state == SessionState.TRANSCRIBING
        assert "finalize" in result.message.lower()
        
        # Verify session is now in processing state
        finalized = manager.get_session(session.id)
        assert finalized.state == SessionState.TRANSCRIBING
        assert finalized.audio_count == 2
    
    def test_recovery_discard_workflow(self, manager: SessionManager):
        """Test discard workflow: interrupt → discard but preserve audio."""
        # Setup: Create and interrupt session with audio
        session = manager.create_session(chat_id=12345)
        original_audio = create_audio_entry(1)
        manager.add_audio(session.id, original_audio)
        manager.transition_state(session.id, SessionState.INTERRUPTED)
        
        # Recover with DISCARD
        result = manager.recover_session(session.id, RecoveryAction.DISCARD)
        
        assert result.new_state == SessionState.ERROR
        assert "discard" in result.message.lower()
        
        # Verify audio is preserved
        discarded = manager.get_session(session.id)
        assert discarded.audio_count == 1  # Audio still there
        assert discarded.state == SessionState.ERROR
    
    def test_stale_session_detection(self, manager: SessionManager):
        """Test detection of sessions inactive for too long."""
        # Create session with old audio
        session = manager.create_session(chat_id=12345)
        
        # Add audio with old timestamp
        old_audio = AudioEntry(
            sequence=1,
            received_at=datetime.now(timezone.utc) - timedelta(hours=2),
            telegram_file_id="file_1",
            local_filename="001_audio.ogg",
            file_size_bytes=1024,
            duration_seconds=10.0,
        )
        manager.add_audio(session.id, old_audio)
        
        # Detect with 1-hour threshold
        interrupted = manager.detect_interrupted_sessions(
            inactivity_threshold=timedelta(hours=1)
        )
        
        # Should find this stale session
        found = next((i for i in interrupted if i.session_id == session.id), None)
        assert found is not None
    
    def test_cannot_recover_non_interrupted(self, manager: SessionManager):
        """Test that recover fails for non-interrupted sessions."""
        session = manager.create_session(chat_id=12345)
        
        # Try to recover COLLECTING session
        with pytest.raises(InvalidStateError):
            manager.recover_session(session.id, RecoveryAction.RESUME)
    
    def test_recovery_options_based_on_state(self, manager: SessionManager):
        """Test that recovery options vary based on session state."""
        # Session with audio
        session1 = manager.create_session(chat_id=12345)
        manager.add_audio(session1.id, create_audio_entry(1))
        manager.transition_state(session1.id, SessionState.INTERRUPTED)
        
        # Session without audio (empty)
        session2 = manager.create_session(chat_id=12346)
        manager.transition_state(session2.id, SessionState.INTERRUPTED)
        
        interrupted = manager.detect_interrupted_sessions()
        
        session1_info = next((i for i in interrupted if i.session_id == session1.id), None)
        session2_info = next((i for i in interrupted if i.session_id == session2.id), None)
        
        # Session with audio should have all options
        if session1_info:
            assert RecoveryAction.RESUME in session1_info.recovery_options
            assert RecoveryAction.FINALIZE in session1_info.recovery_options
        
        # Both should have DISCARD
        if session2_info:
            assert RecoveryAction.DISCARD in session2_info.recovery_options


class TestRecoveryEdgeCases:
    """Test edge cases in recovery."""
    
    def test_recover_empty_session_finalize(self, manager: SessionManager):
        """Test finalize fails gracefully for empty session."""
        session = manager.create_session(chat_id=12345)
        manager.transition_state(session.id, SessionState.INTERRUPTED)
        
        # Finalize empty session
        result = manager.recover_session(session.id, RecoveryAction.FINALIZE)
        
        # Should mark as error instead
        assert result.new_state == SessionState.ERROR
    
    def test_multiple_recovery_attempts(self, manager: SessionManager):
        """Test that recovery can only be done once."""
        session = manager.create_session(chat_id=12345)
        manager.add_audio(session.id, create_audio_entry(1))
        manager.transition_state(session.id, SessionState.INTERRUPTED)
        
        # First recovery succeeds
        result = manager.recover_session(session.id, RecoveryAction.RESUME)
        assert result.new_state == SessionState.COLLECTING
        
        # Second recovery fails (no longer interrupted)
        with pytest.raises(InvalidStateError):
            manager.recover_session(session.id, RecoveryAction.RESUME)


class TestRecoveryDataIntegrity:
    """Test data integrity during recovery."""
    
    def test_resume_preserves_audio(self, manager: SessionManager):
        """Test that RESUME preserves all audio entries."""
        session = manager.create_session(chat_id=12345)
        
        # Add multiple audio entries
        for i in range(5):
            manager.add_audio(session.id, create_audio_entry(i + 1))
        
        original = manager.get_session(session.id)
        original_count = original.audio_count
        
        # Interrupt and resume
        manager.transition_state(session.id, SessionState.INTERRUPTED)
        manager.recover_session(session.id, RecoveryAction.RESUME)
        
        # Verify all audio preserved
        resumed = manager.get_session(session.id)
        assert resumed.audio_count == original_count
    
    def test_finalize_preserves_audio(self, manager: SessionManager):
        """Test that FINALIZE preserves all audio entries."""
        session = manager.create_session(chat_id=12345)
        
        for i in range(3):
            manager.add_audio(session.id, create_audio_entry(i + 1))
        
        manager.transition_state(session.id, SessionState.INTERRUPTED)
        manager.recover_session(session.id, RecoveryAction.FINALIZE)
        
        finalized = manager.get_session(session.id)
        assert finalized.audio_count == 3
    
    def test_discard_preserves_audio(self, manager: SessionManager):
        """Test that DISCARD preserves audio files."""
        session = manager.create_session(chat_id=12345)
        manager.add_audio(session.id, create_audio_entry(1))
        
        manager.transition_state(session.id, SessionState.INTERRUPTED)
        manager.recover_session(session.id, RecoveryAction.DISCARD)
        
        discarded = manager.get_session(session.id)
        # Audio entries still in metadata
        assert discarded.audio_count == 1
