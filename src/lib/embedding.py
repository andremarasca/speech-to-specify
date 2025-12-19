"""Lazy-loaded embedding service for semantic matching.

This module provides a singleton EmbeddingService that loads the
sentence-transformers model on first use. Uses all-MiniLM-L6-v2 for
384-dimensional embeddings optimized for CPU inference.

Following research.md decision: Local-only processing, no cloud.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Sentinel for lazy loading
_embedding_service: Optional["EmbeddingService"] = None


class EmbeddingService:
    """
    Singleton service for computing semantic embeddings.

    Uses sentence-transformers with all-MiniLM-L6-v2 model (~90MB).
    Model is loaded lazily on first embed() call to avoid startup cost.

    Thread-safe for concurrent embed() calls after initialization.
    """

    MODEL_NAME = "all-MiniLM-L6-v2"
    EMBEDDING_DIM = 384

    def __init__(self):
        """Initialize embedding service (model loaded lazily)."""
        self._model = None
        self._initialized = False

    def _ensure_loaded(self) -> None:
        """Load model if not already loaded."""
        if self._initialized:
            return

        try:
            from sentence_transformers import SentenceTransformer

            logger.info(f"Loading embedding model: {self.MODEL_NAME}")
            self._model = SentenceTransformer(self.MODEL_NAME)
            self._initialized = True
            logger.info(f"Embedding model loaded successfully")

        except ImportError as e:
            logger.error("sentence-transformers not installed")
            raise ImportError(
                "sentence-transformers is required for semantic matching. "
                "Install with: pip install sentence-transformers"
            ) from e

        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")
            raise RuntimeError(f"Failed to load embedding model: {e}") from e

    def embed(self, text: str) -> list[float]:
        """
        Compute embedding vector for text.

        Args:
            text: Input text to embed

        Returns:
            384-dimensional embedding vector as list of floats

        Raises:
            RuntimeError: If model fails to load or encode
        """
        self._ensure_loaded()

        try:
            # encode() returns numpy array, convert to list for JSON serialization
            embedding = self._model.encode(text, convert_to_numpy=True)
            return embedding.tolist()

        except Exception as e:
            logger.error(f"Failed to compute embedding: {e}")
            raise RuntimeError(f"Failed to compute embedding: {e}") from e

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Compute embeddings for multiple texts efficiently.

        Args:
            texts: List of input texts

        Returns:
            List of 384-dimensional embedding vectors

        Raises:
            RuntimeError: If model fails to load or encode
        """
        if not texts:
            return []

        self._ensure_loaded()

        try:
            embeddings = self._model.encode(texts, convert_to_numpy=True)
            return [emb.tolist() for emb in embeddings]

        except Exception as e:
            logger.error(f"Failed to compute batch embeddings: {e}")
            raise RuntimeError(f"Failed to compute batch embeddings: {e}") from e

    @property
    def is_loaded(self) -> bool:
        """Check if model is loaded."""
        return self._initialized


def get_embedding_service() -> EmbeddingService:
    """
    Get the singleton EmbeddingService instance.

    Returns:
        The shared EmbeddingService instance
    """
    global _embedding_service

    if _embedding_service is None:
        _embedding_service = EmbeddingService()

    return _embedding_service


def cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
    """
    Compute cosine similarity between two vectors.

    Args:
        vec1: First embedding vector
        vec2: Second embedding vector

    Returns:
        Cosine similarity in range [-1.0, 1.0]

    Raises:
        ValueError: If vectors have different dimensions
    """
    if len(vec1) != len(vec2):
        raise ValueError(
            f"Vector dimensions must match: {len(vec1)} != {len(vec2)}"
        )

    # Compute dot product and magnitudes
    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    magnitude1 = sum(a * a for a in vec1) ** 0.5
    magnitude2 = sum(b * b for b in vec2) ** 0.5

    # Avoid division by zero
    if magnitude1 == 0 or magnitude2 == 0:
        return 0.0

    return dot_product / (magnitude1 * magnitude2)
