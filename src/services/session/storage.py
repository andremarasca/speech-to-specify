"""Session storage with atomic JSON persistence.

This module implements filesystem-based session storage using atomic
write operations (temp file + os.replace) to prevent data corruption.

Following research.md decision: Pure stdlib, no external dependencies.
"""

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Optional

from src.models.session import Session

logger = logging.getLogger(__name__)


class SessionStorageError(Exception):
    """Base exception for session storage errors."""

    pass


class SessionNotFoundError(SessionStorageError):
    """Raised when a session cannot be found."""

    pass


class SessionStorage:
    """
    Atomic JSON-based session storage.

    Implements the SessionStorage interface from contracts/session-manager.md.
    Uses temp file + os.replace() pattern for atomic writes.
    """

    def __init__(self, sessions_dir: Path):
        """
        Initialize session storage.

        Args:
            sessions_dir: Root directory for session folders
        """
        self.sessions_dir = sessions_dir
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

    def save(self, session: Session) -> None:
        """
        Persist session state atomically.

        Uses temp file + os.replace() for POSIX-atomic writes.
        Crash during write leaves old file intact.

        Args:
            session: Session to persist
        """
        session_path = session.folder_path(self.sessions_dir)
        session_path.mkdir(parents=True, exist_ok=True)

        metadata_path = session.metadata_path(self.sessions_dir)

        # Convert session to JSON
        data = session.to_dict()
        json_content = json.dumps(data, indent=2, ensure_ascii=False)

        # Atomic write: write to temp file, then replace
        # This ensures we never have a partial write
        temp_fd, temp_path = tempfile.mkstemp(
            dir=session_path,
            prefix=".metadata_",
            suffix=".tmp",
        )

        try:
            with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
                f.write(json_content)
                f.flush()
                os.fsync(f.fileno())  # Force write to disk

            # Atomic replace (POSIX-atomic on same filesystem)
            os.replace(temp_path, metadata_path)
            logger.debug(f"Saved session {session.id} to {metadata_path}")

        except Exception as e:
            # Clean up temp file on error
            try:
                os.unlink(temp_path)
            except OSError:
                pass
            raise SessionStorageError(f"Failed to save session {session.id}: {e}") from e

    def load(self, session_id: str) -> Optional[Session]:
        """
        Load session from storage.

        Args:
            session_id: Session identifier

        Returns:
            Session if found, None otherwise
        """
        session_path = self.sessions_dir / session_id
        metadata_path = session_path / "metadata.json"

        if not metadata_path.exists():
            return None

        try:
            with open(metadata_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return Session.from_dict(data)

        except json.JSONDecodeError as e:
            logger.error(f"Corrupted metadata for session {session_id}: {e}")
            raise SessionStorageError(
                f"Corrupted metadata for session {session_id}"
            ) from e

        except Exception as e:
            logger.error(f"Failed to load session {session_id}: {e}")
            raise SessionStorageError(f"Failed to load session {session_id}: {e}") from e

    def exists(self, session_id: str) -> bool:
        """Check if a session exists."""
        metadata_path = self.sessions_dir / session_id / "metadata.json"
        return metadata_path.exists()

    def list_sessions(self, limit: int = 10) -> list[Session]:
        """
        List recent sessions, newest first.

        Args:
            limit: Maximum number of sessions to return

        Returns:
            List of sessions, sorted by creation time (newest first)
        """
        sessions = []

        if not self.sessions_dir.exists():
            return sessions

        # Scan session directories
        for entry in self.sessions_dir.iterdir():
            if not entry.is_dir():
                continue

            metadata_path = entry / "metadata.json"
            if not metadata_path.exists():
                continue

            try:
                session = self.load(entry.name)
                if session:
                    sessions.append(session)
            except SessionStorageError:
                # Skip corrupted sessions
                logger.warning(f"Skipping corrupted session: {entry.name}")
                continue

        # Sort by creation time (newest first)
        # Session IDs are timestamp-based, so lexicographic sort works
        sessions.sort(key=lambda s: s.id, reverse=True)

        return sessions[:limit]

    def delete(self, session_id: str) -> bool:
        """
        Delete a session and its folder.

        Args:
            session_id: Session identifier

        Returns:
            True if deleted, False if not found
        """
        session_path = self.sessions_dir / session_id

        if not session_path.exists():
            return False

        import shutil

        try:
            shutil.rmtree(session_path)
            logger.info(f"Deleted session {session_id}")
            return True
        except Exception as e:
            raise SessionStorageError(f"Failed to delete session {session_id}: {e}") from e

    def create_session_folders(self, session: Session) -> None:
        """
        Create the folder structure for a new session.

        Creates:
            sessions/{id}/
            sessions/{id}/audio/
            sessions/{id}/transcripts/
            sessions/{id}/process/

        Args:
            session: Session to create folders for
        """
        session_path = session.folder_path(self.sessions_dir)
        session_path.mkdir(parents=True, exist_ok=True)

        # Create subdirectories
        session.audio_path(self.sessions_dir).mkdir(exist_ok=True)
        session.transcripts_path(self.sessions_dir).mkdir(exist_ok=True)
        session.process_path(self.sessions_dir).mkdir(exist_ok=True)

        logger.debug(f"Created session folder structure at {session_path}")
