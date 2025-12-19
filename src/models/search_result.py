"""Search result model for semantic and text-based session search.

Per data-model.md for 004-resilient-voice-capture.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from src.models.session import MatchType


@dataclass
class PreviewFragment:
    """A text fragment with highlight information for search preview.
    
    Attributes:
        text: The text fragment to display.
        highlight_ranges: List of (start, end) tuples indicating which
            portions of the text should be highlighted as matches.
    """
    
    text: str
    highlight_ranges: list[tuple[int, int]] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "text": self.text,
            "highlight_ranges": self.highlight_ranges,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "PreviewFragment":
        """Create from dictionary (JSON deserialization)."""
        return cls(
            text=data["text"],
            highlight_ranges=[tuple(r) for r in data.get("highlight_ranges", [])],
        )


@dataclass
class SearchResult:
    """Result of searching for sessions.
    
    Represents a single session match in search results,
    with relevance scoring and preview fragments.
    
    Per data-model.md for 004-resilient-voice-capture.
    
    Attributes:
        session_id: Unique identifier of the matched session.
        session_name: Human-readable session name (intelligible_name).
        relevance_score: Match relevance in range [0.0, 1.0].
        match_type: How the match was determined (SEMANTIC, TEXT, CHRONOLOGICAL).
        preview_fragments: Text fragments showing match context.
        session_created_at: When the session was created.
        total_audio_duration: Total duration of all audio in seconds.
        audio_count: Number of audio segments in the session.
    """
    
    session_id: str
    session_name: str
    relevance_score: float
    match_type: MatchType
    preview_fragments: list[PreviewFragment] = field(default_factory=list)
    session_created_at: Optional[datetime] = None
    total_audio_duration: float = 0.0
    audio_count: int = 0
    
    def __post_init__(self) -> None:
        """Validate relevance score is in valid range."""
        if not 0.0 <= self.relevance_score <= 1.0:
            raise ValueError(
                f"relevance_score must be in range [0.0, 1.0], got {self.relevance_score}"
            )
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "session_id": self.session_id,
            "session_name": self.session_name,
            "relevance_score": self.relevance_score,
            "match_type": self.match_type.value,
            "preview_fragments": [f.to_dict() for f in self.preview_fragments],
            "session_created_at": (
                self.session_created_at.isoformat() 
                if self.session_created_at 
                else None
            ),
            "total_audio_duration": self.total_audio_duration,
            "audio_count": self.audio_count,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "SearchResult":
        """Create from dictionary (JSON deserialization)."""
        return cls(
            session_id=data["session_id"],
            session_name=data["session_name"],
            relevance_score=data["relevance_score"],
            match_type=MatchType(data["match_type"]),
            preview_fragments=[
                PreviewFragment.from_dict(f) 
                for f in data.get("preview_fragments", [])
            ],
            session_created_at=(
                datetime.fromisoformat(data["session_created_at"])
                if data.get("session_created_at")
                else None
            ),
            total_audio_duration=data.get("total_audio_duration", 0.0),
            audio_count=data.get("audio_count", 0),
        )
