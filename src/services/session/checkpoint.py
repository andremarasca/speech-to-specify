"""Checkpoint persistence helper for crash recovery.

Per plan.md for 005-telegram-ux-overhaul.

This module provides helper functions for saving and loading
checkpoint data to enable session recovery after crashes.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.models.session import Session
from src.models.ui_state import CheckpointData, UIState

logger = logging.getLogger(__name__)


def save_checkpoint(
    session: Session,
    sessions_root: Path,
    audio_sequence: Optional[int] = None,
    processing_state: Optional[str] = None,
    ui_state: Optional[UIState] = None,
) -> CheckpointData:
    """Save a checkpoint for crash recovery.
    
    Creates or updates checkpoint data in the session and persists
    the session metadata to disk.
    
    Args:
        session: The session to checkpoint
        sessions_root: Root directory for sessions
        audio_sequence: Last received audio sequence number
        processing_state: Current processing state description
        ui_state: Current UI state (optional)
        
    Returns:
        The created CheckpointData
    """
    checkpoint = CheckpointData(
        last_checkpoint_at=datetime.now(),
        last_audio_sequence=audio_sequence or session.audio_count,
        processing_state=processing_state,
        ui_state=ui_state,
    )
    
    session.checkpoint_data = checkpoint
    
    # Persist to disk
    metadata_path = session.metadata_path(sessions_root)
    try:
        metadata_path.parent.mkdir(parents=True, exist_ok=True)
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(session.to_dict(), f, indent=2, ensure_ascii=False)
        logger.debug(f"Checkpoint saved for session {session.id}")
    except Exception as e:
        logger.error(f"Failed to save checkpoint for session {session.id}: {e}")
        raise
    
    return checkpoint


def load_checkpoint(session: Session) -> Optional[CheckpointData]:
    """Load checkpoint data from a session.
    
    Args:
        session: The session to get checkpoint from
        
    Returns:
        CheckpointData if exists, None otherwise
    """
    return session.checkpoint_data


def clear_checkpoint(session: Session, sessions_root: Path) -> None:
    """Clear checkpoint data after successful recovery or finalization.
    
    Args:
        session: The session to clear checkpoint from
        sessions_root: Root directory for sessions
    """
    session.checkpoint_data = None
    
    # Persist to disk
    metadata_path = session.metadata_path(sessions_root)
    try:
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(session.to_dict(), f, indent=2, ensure_ascii=False)
        logger.debug(f"Checkpoint cleared for session {session.id}")
    except Exception as e:
        logger.error(f"Failed to clear checkpoint for session {session.id}: {e}")
        raise


def has_checkpoint(session: Session) -> bool:
    """Check if a session has checkpoint data.
    
    Args:
        session: The session to check
        
    Returns:
        True if checkpoint data exists
    """
    return session.checkpoint_data is not None


def is_orphaned_session(session: Session) -> bool:
    """Check if a session is orphaned (has checkpoint but not finalized).
    
    An orphaned session indicates the bot crashed during collection
    or processing, and the session needs recovery.
    
    Args:
        session: The session to check
        
    Returns:
        True if session is orphaned
    """
    from src.models.session import SessionState
    
    # A session is orphaned if:
    # 1. It has checkpoint data AND
    # 2. It's in COLLECTING or INTERRUPTED state AND
    # 3. It has at least one audio entry
    if not session.checkpoint_data:
        return False
    
    if session.state not in (SessionState.COLLECTING, SessionState.INTERRUPTED):
        return False
    
    return session.audio_count > 0


def find_orphaned_sessions(sessions_root: Path) -> list[Session]:
    """Find all orphaned sessions in the sessions directory.
    
    Scans all session directories and returns sessions that
    appear to be orphaned (need recovery).
    
    Args:
        sessions_root: Root directory for sessions
        
    Returns:
        List of orphaned sessions
    """
    orphaned = []
    
    if not sessions_root.exists():
        return orphaned
    
    for session_dir in sessions_root.iterdir():
        if not session_dir.is_dir():
            continue
        
        metadata_path = session_dir / "metadata.json"
        if not metadata_path.exists():
            continue
        
        try:
            with open(metadata_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            session = Session.from_dict(data)
            
            if is_orphaned_session(session):
                orphaned.append(session)
                logger.info(f"Found orphaned session: {session.id}")
                
        except Exception as e:
            logger.warning(f"Failed to load session from {session_dir}: {e}")
            continue
    
    return orphaned


def recover_session(session: Session, sessions_root: Path) -> Session:
    """Recover an orphaned session.
    
    Transitions the session from INTERRUPTED back to COLLECTING
    and clears the checkpoint data to prepare for continued use.
    
    Args:
        session: The orphaned session to recover
        sessions_root: Root directory for sessions
        
    Returns:
        The recovered session
    """
    from src.models.session import SessionState
    
    if session.state == SessionState.INTERRUPTED:
        session.state = SessionState.COLLECTING
    
    # Clear checkpoint but preserve audio entries
    clear_checkpoint(session, sessions_root)
    
    logger.info(f"Recovered session {session.id} with {session.audio_count} audio(s)")
    return session
