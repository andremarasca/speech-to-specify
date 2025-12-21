"""TTS Garbage Collector for audio artifact cleanup.

Per plan.md for 008-async-audio-response (User Story 3).

This module provides automatic cleanup of TTS audio artifacts based on:
- Age-based retention policy (TTS_GC_RETENTION_HOURS)
- Storage limit enforcement (TTS_GC_MAX_STORAGE_MB)
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from src.lib.config import TTSConfig
from src.models.tts import TTSArtifact

logger = logging.getLogger(__name__)


class TTSGarbageCollector:
    """Garbage collector for TTS audio artifacts.
    
    Manages cleanup of TTS files based on:
    - Age: Files older than gc_retention_hours are removed
    - Storage: Oldest files removed when gc_max_storage_mb exceeded
    
    Attributes:
        config: TTS configuration with GC settings
        sessions_path: Root path for session storage
    
    Example:
        >>> from src.lib.config import get_tts_config, get_session_config
        >>> 
        >>> config = get_tts_config()
        >>> sessions_path = get_session_config().sessions_path
        >>> gc = TTSGarbageCollector(config, sessions_path)
        >>> 
        >>> stats = await gc.collect()
        >>> print(f"Removed {stats['files_removed']} files")
    """
    
    def __init__(self, config: TTSConfig, sessions_path: Path):
        """Initialize garbage collector.
        
        Args:
            config: TTS configuration with GC settings
            sessions_path: Root path for session storage
        """
        self.config = config
        self.sessions_path = sessions_path
    
    def scan_artifacts(self) -> List[TTSArtifact]:
        """Scan all TTS artifacts across sessions.
        
        Looks for audio files in sessions/*/audio/tts/ directories.
        
        Returns:
            List of TTSArtifact objects sorted by age (oldest first)
        """
        artifacts = []
        
        if not self.sessions_path.exists():
            return artifacts
        
        # Scan all session directories
        for session_dir in self.sessions_path.iterdir():
            if not session_dir.is_dir():
                continue
            
            tts_dir = session_dir / "audio" / "tts"
            if not tts_dir.exists():
                continue
            
            session_id = session_dir.name
            
            for audio_file in tts_dir.glob(f"*.{self.config.format}"):
                try:
                    # Parse filename: {seq}_{oracle}.{format}
                    stem = audio_file.stem  # e.g., "001_cetico"
                    parts = stem.split("_", 1)
                    if len(parts) != 2:
                        continue
                    
                    sequence = int(parts[0])
                    oracle_id = parts[1]
                    
                    artifact = TTSArtifact.from_file(
                        file_path=audio_file,
                        session_id=session_id,
                        sequence=sequence,
                        oracle_id=oracle_id,
                    )
                    artifacts.append(artifact)
                    
                except (ValueError, OSError) as e:
                    logger.warning(f"Error scanning artifact {audio_file}: {e}")
                    continue
        
        # Sort by age (oldest first for GC priority)
        artifacts.sort(key=lambda a: a.created_at)
        return artifacts
    
    def collect(self) -> dict:
        """Run garbage collection.
        
        Removes artifacts based on retention policy and storage limits.
        
        Returns:
            Dict with statistics:
            - files_removed: Number of files deleted
            - bytes_freed: Total bytes freed
            - errors: Number of deletion errors
        """
        stats = {
            "files_removed": 0,
            "bytes_freed": 0,
            "errors": 0,
        }
        
        artifacts = self.scan_artifacts()
        if not artifacts:
            logger.debug("No TTS artifacts found for GC")
            return stats
        
        # Phase 1: Remove expired artifacts (age-based)
        if self.config.gc_retention_hours > 0:
            expired = [a for a in artifacts if a.is_expired(self.config.gc_retention_hours)]
            for artifact in expired:
                if self._remove_artifact(artifact):
                    stats["files_removed"] += 1
                    stats["bytes_freed"] += artifact.file_size_bytes
                else:
                    stats["errors"] += 1
            
            # Remove from list for storage check
            artifacts = [a for a in artifacts if not a.is_expired(self.config.gc_retention_hours)]
        
        # Phase 2: Enforce storage limit
        if self.config.gc_max_storage_mb > 0:
            max_bytes = self.config.gc_max_storage_mb * 1024 * 1024
            total_bytes = sum(a.file_size_bytes for a in artifacts)
            
            # Remove oldest files until under limit
            while total_bytes > max_bytes and artifacts:
                oldest = artifacts.pop(0)  # Already sorted oldest first
                if self._remove_artifact(oldest):
                    stats["files_removed"] += 1
                    stats["bytes_freed"] += oldest.file_size_bytes
                    total_bytes -= oldest.file_size_bytes
                else:
                    stats["errors"] += 1
        
        if stats["files_removed"] > 0:
            logger.info(
                f"TTS GC complete: removed {stats['files_removed']} files, "
                f"freed {stats['bytes_freed'] / 1024 / 1024:.2f} MB"
            )
        
        return stats
    
    def _remove_artifact(self, artifact: TTSArtifact) -> bool:
        """Remove an artifact file.
        
        Args:
            artifact: TTSArtifact to remove
            
        Returns:
            True if removed successfully, False on error
        """
        try:
            artifact.file_path.unlink(missing_ok=True)
            logger.debug(f"Removed TTS artifact: {artifact.file_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to remove artifact {artifact.file_path}: {e}")
            return False
    
    def get_storage_stats(self) -> dict:
        """Get current storage statistics.
        
        Returns:
            Dict with:
            - total_files: Number of TTS files
            - total_bytes: Total storage used
            - oldest_age_hours: Age of oldest file in hours
        """
        artifacts = self.scan_artifacts()
        
        return {
            "total_files": len(artifacts),
            "total_bytes": sum(a.file_size_bytes for a in artifacts),
            "oldest_age_hours": artifacts[0].age_hours if artifacts else 0,
        }
    
    def mark_orphan(self, session_id: str) -> int:
        """Mark artifacts as orphan when session terminates during synthesis.
        
        Per T031b: Orphan detection for sessions that terminate mid-synthesis.
        
        Note: In the current implementation, orphan artifacts are just 
        regular artifacts that will be cleaned up by age/storage policies.
        This method could be extended to add metadata for priority cleanup.
        
        Args:
            session_id: Session that was terminated
            
        Returns:
            Number of artifacts marked as orphan
        """
        count = 0
        tts_dir = self.sessions_path / session_id / "audio" / "tts"
        
        if not tts_dir.exists():
            return count
        
        for audio_file in tts_dir.glob(f"*.{self.config.format}"):
            # Currently just logs - could be extended to add .orphan marker
            logger.debug(f"Marking orphan artifact: {audio_file}")
            count += 1
        
        return count
