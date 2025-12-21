"""Context builder for oracle feedback requests.

Per contracts/context-builder.md for 007-contextual-oracle-feedback.

This module builds context strings from session transcripts and
LLM responses for use in oracle prompts.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from src.models.session import Session, AudioEntry, LlmEntry


def _normalize_datetime(dt: datetime) -> datetime:
    """Normalize datetime to UTC for consistent comparison.
    
    Handles both timezone-aware and naive datetimes.
    Naive datetimes are assumed to be UTC.
    """
    if dt.tzinfo is None:
        # Naive datetime - assume UTC
        return dt.replace(tzinfo=timezone.utc)
    else:
        # Convert to UTC for consistent comparison
        return dt.astimezone(timezone.utc)

logger = logging.getLogger(__name__)


@dataclass
class BuiltContext:
    """
    Result of building context from session entries.
    
    Per contracts/context-builder.md.
    
    Attributes:
        content: Formatted context string
        transcript_count: Number of transcripts included
        llm_response_count: Number of LLM responses included
        include_llm_history: Whether LLM history was included
        total_tokens_estimate: Rough token estimate
    """
    
    content: str
    transcript_count: int
    llm_response_count: int
    include_llm_history: bool
    total_tokens_estimate: int


class ContextBuilder:
    """
    Builds context string from session entries.
    
    Per contracts/context-builder.md.
    
    Responsibilities:
        - Read transcripts and LLM responses from session folder
        - Format entries chronologically with clear delimiters
        - Respect include_llm_history preference
        - Handle missing files gracefully
    """
    
    # Format strings for context entries
    TRANSCRIPT_DELIMITER = "[TRANSCRIÇÃO {seq} - {timestamp}]"
    LLM_DELIMITER = "[ORÁCULO: {name} - {timestamp}]"
    MISSING_TRANSCRIPT = "[Transcrição indisponível]"
    MISSING_LLM_RESPONSE = "[Resposta indisponível]"
    
    def __init__(self, session_dir: Path):
        """
        Initialize with session directory for file access.
        
        Args:
            session_dir: Root directory containing session folders
        """
        self.session_dir = Path(session_dir)
    
    def build(
        self,
        session: Session,
        include_llm_history: Optional[bool] = None,
    ) -> BuiltContext:
        """
        Build context from session entries.
        
        Per BC-CB-001 to BC-CB-009.
        
        Args:
            session: Session containing audio_entries and llm_entries
            include_llm_history: Override session preference (None = use session.ui_preferences)
            
        Returns:
            BuiltContext with formatted content and metadata
        """
        # Determine if we should include LLM history
        # Per BC-CB-003 and BC-CB-004: override takes precedence
        if include_llm_history is None:
            if session.ui_preferences:
                include_llm_history = session.ui_preferences.include_llm_history
            else:
                include_llm_history = True  # Default per data-model.md
        
        # Build chronological timeline of all entries
        # Per BC-CB-001: Chronological ordering
        timeline: list[tuple[datetime, str, str]] = []
        transcript_count = 0
        llm_response_count = 0
        
        # Add transcripts
        for entry in session.audio_entries:
            if entry.transcript_filename:
                timestamp = entry.received_at
                content = self._read_transcript(session, entry)
                delimiter = self.TRANSCRIPT_DELIMITER.format(
                    seq=entry.sequence,
                    timestamp=timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                )
                timeline.append((timestamp, delimiter, content))
                transcript_count += 1
        
        # Add LLM responses if enabled (Per BC-CB-002)
        if include_llm_history:
            for entry in session.llm_entries:
                timestamp = entry.created_at
                content = self._read_llm_response(session, entry)
                # Per BC-CB-008: Include oracle name in delimiter
                delimiter = self.LLM_DELIMITER.format(
                    name=entry.oracle_name,
                    timestamp=timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                )
                timeline.append((timestamp, delimiter, content))
                llm_response_count += 1
        
        # Sort by timestamp (chronological order)
        # Normalize datetimes to handle mixed timezone-aware and naive datetimes
        timeline.sort(key=lambda x: _normalize_datetime(x[0]))
        
        # Build final content string
        # Per BC-CB-005: Handle empty session
        if not timeline:
            return BuiltContext(
                content="",
                transcript_count=0,
                llm_response_count=0,
                include_llm_history=include_llm_history,
                total_tokens_estimate=0,
            )
        
        parts = []
        for _, delimiter, content in timeline:
            parts.append(f"{delimiter}\n{content}")
        
        full_content = "\n\n".join(parts)
        
        return BuiltContext(
            content=full_content,
            transcript_count=transcript_count,
            llm_response_count=llm_response_count,
            include_llm_history=include_llm_history,
            total_tokens_estimate=self.estimate_tokens(full_content),
        )
    
    def _read_transcript(self, session: Session, entry: AudioEntry) -> str:
        """
        Read transcript file content.
        
        Per BC-CB-006: Missing files return placeholder with warning.
        
        Args:
            session: Session containing the entry
            entry: AudioEntry with transcript_filename
            
        Returns:
            Transcript content or placeholder
        """
        if not entry.transcript_filename:
            return self.MISSING_TRANSCRIPT
        
        transcript_path = (
            session.transcripts_path(self.session_dir) / entry.transcript_filename
        )
        
        try:
            if transcript_path.exists():
                return transcript_path.read_text(encoding="utf-8").strip()
            else:
                logger.warning(f"Transcript file not found: {transcript_path}")
                return self.MISSING_TRANSCRIPT
        except (OSError, PermissionError) as e:
            logger.error(f"Cannot read transcript {transcript_path}: {e}")
            return self.MISSING_TRANSCRIPT
    
    def _read_llm_response(self, session: Session, entry: LlmEntry) -> str:
        """
        Read LLM response file content.
        
        Per BC-CB-007: Missing files return placeholder with warning.
        
        Args:
            session: Session containing the entry
            entry: LlmEntry with response_filename
            
        Returns:
            Response content or placeholder
        """
        response_path = (
            session.llm_responses_path(self.session_dir) / entry.response_filename
        )
        
        try:
            if response_path.exists():
                return response_path.read_text(encoding="utf-8").strip()
            else:
                logger.warning(f"LLM response file not found: {response_path}")
                return self.MISSING_LLM_RESPONSE
        except (OSError, PermissionError) as e:
            logger.error(f"Cannot read LLM response {response_path}: {e}")
            return self.MISSING_LLM_RESPONSE
    
    def estimate_tokens(self, text: str) -> int:
        """
        Rough token estimate (chars / 4).
        
        Per BC-CB-009: Simple heuristic for token estimation.
        
        Args:
            text: Text to estimate
            
        Returns:
            Estimated token count
        """
        if not text:
            return 0
        return len(text) // 4
