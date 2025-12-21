"""Contract tests for ContextBuilder.

Per contracts/context-builder.md for 007-contextual-oracle-feedback.

Tests all BC-CB-* behavior contracts.
"""

import pytest
import tempfile
from pathlib import Path
from datetime import datetime
from unittest.mock import MagicMock

from src.services.llm.context_builder import ContextBuilder, BuiltContext
from src.models.session import (
    Session,
    SessionState,
    AudioEntry,
    LlmEntry,
    ContextSnapshot,
    TranscriptionStatus,
)
from src.models.ui_state import UIPreferences


@pytest.fixture
def temp_sessions_dir():
    """Create a temporary sessions directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_session(temp_sessions_dir):
    """Create a sample session with audio entries."""
    session_id = "2025-12-20_10-30-00"
    session = Session(
        id=session_id,
        state=SessionState.COLLECTING,
        created_at=datetime(2025, 12, 20, 10, 30, 0),
        chat_id=12345,
    )
    
    # Create session directory structure
    session_dir = temp_sessions_dir / session_id
    session_dir.mkdir(parents=True)
    (session_dir / "transcripts").mkdir()
    (session_dir / "llm_responses").mkdir()
    
    return session


def add_transcript(session, temp_sessions_dir, sequence, content, received_at):
    """Helper to add a transcript to session."""
    filename = f"{sequence:03d}_audio.txt"
    transcript_path = temp_sessions_dir / session.id / "transcripts" / filename
    transcript_path.write_text(content)
    
    entry = AudioEntry(
        sequence=sequence,
        received_at=received_at,
        telegram_file_id=f"file_{sequence}",
        local_filename=f"{sequence:03d}_audio.ogg",
        file_size_bytes=1000,
        transcription_status=TranscriptionStatus.SUCCESS,
        transcript_filename=filename,
    )
    session.audio_entries.append(entry)
    return entry


def add_llm_response(session, temp_sessions_dir, sequence, oracle_name, content, created_at):
    """Helper to add an LLM response to session."""
    filename = f"{sequence:03d}_{oracle_name.lower()}.txt"
    response_path = temp_sessions_dir / session.id / "llm_responses" / filename
    response_path.write_text(content)
    
    entry = LlmEntry(
        sequence=sequence,
        created_at=created_at,
        oracle_name=oracle_name,
        oracle_id="abc12345",
        response_filename=filename,
        context_snapshot=ContextSnapshot(
            transcript_count=1,
            llm_response_count=0,
            include_llm_history=True,
        ),
    )
    session.llm_entries.append(entry)
    return entry


class TestContextBuilder:
    """Tests for ContextBuilder."""
    
    def test_chronological_ordering(self, temp_sessions_dir, sample_session):
        """BC-CB-001: Entries are ordered chronologically."""
        # Add transcript at 10:30
        add_transcript(
            sample_session, temp_sessions_dir, 1,
            "First transcript",
            datetime(2025, 12, 20, 10, 30, 0)
        )
        
        # Add LLM response at 10:32
        add_llm_response(
            sample_session, temp_sessions_dir, 1,
            "Cético",
            "LLM feedback here",
            datetime(2025, 12, 20, 10, 32, 0)
        )
        
        # Add transcript at 10:35
        add_transcript(
            sample_session, temp_sessions_dir, 2,
            "Second transcript",
            datetime(2025, 12, 20, 10, 35, 0)
        )
        
        builder = ContextBuilder(temp_sessions_dir)
        result = builder.build(sample_session, include_llm_history=True)
        
        # Verify order: transcript 1 -> llm 1 -> transcript 2
        assert "First transcript" in result.content
        assert "LLM feedback here" in result.content
        assert "Second transcript" in result.content
        
        # Verify chronological order by position
        pos_t1 = result.content.find("First transcript")
        pos_llm = result.content.find("LLM feedback here")
        pos_t2 = result.content.find("Second transcript")
        
        assert pos_t1 < pos_llm < pos_t2
    
    def test_transcripts_only_mode(self, temp_sessions_dir, sample_session):
        """BC-CB-002: Only transcripts when include_llm_history=False."""
        add_transcript(
            sample_session, temp_sessions_dir, 1,
            "Transcript content",
            datetime(2025, 12, 20, 10, 30, 0)
        )
        
        add_llm_response(
            sample_session, temp_sessions_dir, 1,
            "Cético",
            "LLM feedback",
            datetime(2025, 12, 20, 10, 32, 0)
        )
        
        builder = ContextBuilder(temp_sessions_dir)
        result = builder.build(sample_session, include_llm_history=False)
        
        assert "Transcript content" in result.content
        assert "LLM feedback" not in result.content
        assert result.transcript_count == 1
        assert result.llm_response_count == 0
        assert result.include_llm_history is False
    
    def test_session_preference_respected(self, temp_sessions_dir, sample_session):
        """BC-CB-003: Session preference used when override is None."""
        sample_session.ui_preferences = UIPreferences(include_llm_history=False)
        
        add_transcript(
            sample_session, temp_sessions_dir, 1,
            "Transcript",
            datetime(2025, 12, 20, 10, 30, 0)
        )
        
        add_llm_response(
            sample_session, temp_sessions_dir, 1,
            "Cético",
            "LLM response",
            datetime(2025, 12, 20, 10, 32, 0)
        )
        
        builder = ContextBuilder(temp_sessions_dir)
        result = builder.build(sample_session, include_llm_history=None)
        
        # Session preference (False) should be used
        assert "LLM response" not in result.content
    
    def test_override_preference(self, temp_sessions_dir, sample_session):
        """BC-CB-004: Override takes precedence over session preference."""
        sample_session.ui_preferences = UIPreferences(include_llm_history=False)
        
        add_transcript(
            sample_session, temp_sessions_dir, 1,
            "Transcript",
            datetime(2025, 12, 20, 10, 30, 0)
        )
        
        add_llm_response(
            sample_session, temp_sessions_dir, 1,
            "Cético",
            "LLM response should appear",
            datetime(2025, 12, 20, 10, 32, 0)
        )
        
        builder = ContextBuilder(temp_sessions_dir)
        result = builder.build(sample_session, include_llm_history=True)
        
        # Override (True) should be used despite session preference (False)
        assert "LLM response should appear" in result.content
    
    def test_empty_session_handling(self, temp_sessions_dir, sample_session):
        """BC-CB-005: Empty session returns empty context."""
        builder = ContextBuilder(temp_sessions_dir)
        result = builder.build(sample_session)
        
        assert result.content == ""
        assert result.transcript_count == 0
        assert result.llm_response_count == 0
        assert result.total_tokens_estimate == 0
    
    def test_missing_transcript_file(self, temp_sessions_dir, sample_session):
        """BC-CB-006: Missing transcript uses placeholder."""
        # Add audio entry but don't create the transcript file
        entry = AudioEntry(
            sequence=1,
            received_at=datetime(2025, 12, 20, 10, 30, 0),
            telegram_file_id="file_1",
            local_filename="001_audio.ogg",
            file_size_bytes=1000,
            transcription_status=TranscriptionStatus.SUCCESS,
            transcript_filename="001_audio.txt",  # File doesn't exist
        )
        sample_session.audio_entries.append(entry)
        
        builder = ContextBuilder(temp_sessions_dir)
        result = builder.build(sample_session)
        
        assert "[Transcrição indisponível]" in result.content
        assert result.transcript_count == 1
    
    def test_missing_llm_response_file(self, temp_sessions_dir, sample_session):
        """BC-CB-007: Missing LLM response uses placeholder."""
        add_transcript(
            sample_session, temp_sessions_dir, 1,
            "Transcript",
            datetime(2025, 12, 20, 10, 30, 0)
        )
        
        # Add LLM entry but don't create the response file
        entry = LlmEntry(
            sequence=1,
            created_at=datetime(2025, 12, 20, 10, 32, 0),
            oracle_name="Cético",
            oracle_id="abc12345",
            response_filename="001_cetico.txt",  # File doesn't exist
            context_snapshot=ContextSnapshot(
                transcript_count=1,
                llm_response_count=0,
                include_llm_history=True,
            ),
        )
        sample_session.llm_entries.append(entry)
        
        builder = ContextBuilder(temp_sessions_dir)
        result = builder.build(sample_session, include_llm_history=True)
        
        assert "[Resposta indisponível]" in result.content
        assert result.llm_response_count == 1
    
    def test_oracle_name_in_delimiter(self, temp_sessions_dir, sample_session):
        """BC-CB-008: Oracle name appears in LLM entry delimiter."""
        add_transcript(
            sample_session, temp_sessions_dir, 1,
            "Transcript",
            datetime(2025, 12, 20, 10, 30, 0)
        )
        
        add_llm_response(
            sample_session, temp_sessions_dir, 1,
            "Visionário",
            "LLM response",
            datetime(2025, 12, 20, 10, 32, 0)
        )
        
        builder = ContextBuilder(temp_sessions_dir)
        result = builder.build(sample_session, include_llm_history=True)
        
        assert "[ORÁCULO: Visionário -" in result.content
    
    def test_token_estimation(self, temp_sessions_dir, sample_session):
        """BC-CB-009: Token estimation uses chars/4 heuristic."""
        # Create content with known length
        content = "a" * 4000  # 4000 chars should be ~1000 tokens
        
        add_transcript(
            sample_session, temp_sessions_dir, 1,
            content,
            datetime(2025, 12, 20, 10, 30, 0)
        )
        
        builder = ContextBuilder(temp_sessions_dir)
        result = builder.build(sample_session)
        
        # Should be approximately 1000 tokens (plus delimiter overhead)
        assert result.total_tokens_estimate >= 1000
    
    def test_estimate_tokens_method(self, temp_sessions_dir):
        """Direct test of estimate_tokens method."""
        builder = ContextBuilder(temp_sessions_dir)
        
        assert builder.estimate_tokens("") == 0
        assert builder.estimate_tokens("a" * 4) == 1
        assert builder.estimate_tokens("a" * 400) == 100
        assert builder.estimate_tokens("a" * 4000) == 1000
