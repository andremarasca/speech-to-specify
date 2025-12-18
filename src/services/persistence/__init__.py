"""Persistence abstraction layer for artifacts and logs."""

from src.services.persistence.base import ArtifactStore, LogStore, PersistenceError
from src.services.persistence.artifacts import FileArtifactStore
from src.services.persistence.logs import FileLogStore


def create_artifact_store(output_dir: str) -> ArtifactStore:
    """Create the default artifact store implementation."""
    return FileArtifactStore(output_dir)


def create_log_store(output_dir: str) -> LogStore:
    """Create the default log store implementation."""
    return FileLogStore(output_dir)


__all__ = [
    "ArtifactStore",
    "LogStore",
    "PersistenceError",
    "FileArtifactStore",
    "FileLogStore",
    "create_artifact_store",
    "create_log_store",
]
