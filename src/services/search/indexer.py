"""Embedding indexer for session search.

Per contracts/search-service.md for 004-resilient-voice-capture.
Generates and manages session embeddings for semantic search.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class EmbeddingResult:
    """Result of embedding generation.
    
    Attributes:
        session_id: Session that was embedded
        success: Whether embedding was generated
        vector_dimension: Dimension of embedding vector
        source_text_length: Length of source text
        error: Error message if failed
    """
    
    session_id: str
    success: bool
    vector_dimension: int = 0
    source_text_length: int = 0
    error: Optional[str] = None


@dataclass
class IndexEntry:
    """Entry in embedding index.
    
    Attributes:
        session_id: Session identifier
        vector: Embedding vector
        source_text_hash: Hash of text used to generate embedding
        created_at: When embedding was generated
    """
    
    session_id: str
    vector: list[float]
    source_text_hash: str
    created_at: datetime


class EmbeddingIndexer(ABC):
    """Service for generating and managing session embeddings.
    
    Per contracts/search-service.md for 004-resilient-voice-capture.
    """
    
    @abstractmethod
    def generate_embedding(self, session_id: str) -> EmbeddingResult:
        """Generate embedding for session from transcripts.
        
        Args:
            session_id: Session to embed
            
        Returns:
            EmbeddingResult with status
        """
        pass
    
    @abstractmethod
    def get_embedding(self, session_id: str) -> Optional[list[float]]:
        """Get cached embedding for session.
        
        Args:
            session_id: Session to look up
            
        Returns:
            Embedding vector or None if not indexed
        """
        pass
    
    @abstractmethod
    def has_embedding(self, session_id: str) -> bool:
        """Check if session has embedding.
        
        Args:
            session_id: Session to check
            
        Returns:
            True if embedding exists
        """
        pass
    
    @abstractmethod
    def invalidate(self, session_id: str) -> None:
        """Invalidate cached embedding.
        
        Called when session content changes (e.g., reopen with new audio).
        
        Args:
            session_id: Session to invalidate
        """
        pass
    
    @abstractmethod
    def get_all_embeddings(self) -> dict[str, list[float]]:
        """Get all cached embeddings.
        
        Returns:
            Dict mapping session_id to embedding vector
        """
        pass
    
    @abstractmethod
    def save_index(self, path: Path) -> None:
        """Persist embedding index to disk.
        
        Args:
            path: Path to save index file
        """
        pass
    
    @abstractmethod
    def load_index(self, path: Path) -> None:
        """Load embedding index from disk.
        
        Args:
            path: Path to index file
        """
        pass
