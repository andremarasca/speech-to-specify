"""Integration tests for TTS Garbage Collection.

Per T027 [US3] from tasks.md for 008-async-audio-response.

Tests:
- Age-based cleanup
- Storage limit enforcement
- File scanning
"""

from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch
import os
import time

import pytest

from src.lib.config import TTSConfig
from src.services.tts.garbage_collector import TTSGarbageCollector


@pytest.fixture
def tts_config():
    """Create test TTS configuration with short retention."""
    return TTSConfig(
        enabled=True,
        voice="pt-BR-AntonioNeural",
        format="ogg",
        timeout_seconds=5,
        max_text_length=1000,
        gc_retention_hours=1,  # 1 hour retention for testing
        gc_max_storage_mb=1,   # 1 MB limit for testing
    )


@pytest.fixture
def sessions_path(tmp_path):
    """Create temporary sessions directory with test files."""
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    return sessions


def create_tts_file(sessions_path: Path, session_id: str, sequence: int, oracle: str, 
                    age_hours: float = 0, size_bytes: int = 1024) -> Path:
    """Create a test TTS audio file with specified age and size."""
    session_dir = sessions_path / session_id / "audio" / "tts"
    session_dir.mkdir(parents=True, exist_ok=True)
    
    filename = f"{sequence:03d}_{oracle}.ogg"
    file_path = session_dir / filename
    
    # Create file with OGG header for validity
    content = b"OggS" + b"\x00" * (size_bytes - 4)
    file_path.write_bytes(content)
    
    # Set file modification time if age specified
    if age_hours > 0:
        mtime = time.time() - (age_hours * 3600)
        os.utime(file_path, (mtime, mtime))
    
    return file_path


class TestGarbageCollectorScan:
    """Tests for TTSGarbageCollector.scan_artifacts()."""
    
    def test_scan_empty_sessions(self, tts_config, sessions_path):
        """Should return empty list for empty sessions."""
        gc = TTSGarbageCollector(tts_config, sessions_path)
        
        artifacts = gc.scan_artifacts()
        
        assert artifacts == []
    
    def test_scan_finds_artifacts(self, tts_config, sessions_path):
        """Should find TTS artifacts in session directories."""
        # Create test files
        create_tts_file(sessions_path, "2025-12-21_12-00-00", 1, "cetico")
        create_tts_file(sessions_path, "2025-12-21_12-00-00", 2, "pragmatico")
        create_tts_file(sessions_path, "2025-12-21_13-00-00", 1, "visionario")
        
        gc = TTSGarbageCollector(tts_config, sessions_path)
        artifacts = gc.scan_artifacts()
        
        assert len(artifacts) == 3
    
    def test_scan_returns_sorted_by_age(self, tts_config, sessions_path):
        """Should return artifacts sorted oldest first."""
        # Create files with different ages
        create_tts_file(sessions_path, "2025-12-21_12-00-00", 1, "new", age_hours=1)
        create_tts_file(sessions_path, "2025-12-21_12-00-00", 2, "old", age_hours=5)
        create_tts_file(sessions_path, "2025-12-21_12-00-00", 3, "medium", age_hours=3)
        
        gc = TTSGarbageCollector(tts_config, sessions_path)
        artifacts = gc.scan_artifacts()
        
        # Should be sorted oldest first (larger age first)
        ages = [a.age_hours for a in artifacts]
        assert ages == sorted(ages, reverse=True)


class TestGarbageCollectorAgeCleanup:
    """Tests for age-based cleanup."""
    
    def test_removes_expired_files(self, tts_config, sessions_path):
        """Should remove files older than retention period."""
        # Create old and new files (tts_config has 1h retention)
        old_file = create_tts_file(sessions_path, "2025-12-21_12-00-00", 1, "old", age_hours=5)
        new_file = create_tts_file(sessions_path, "2025-12-21_12-00-00", 2, "new", age_hours=0.1)  # Very recent
        
        gc = TTSGarbageCollector(tts_config, sessions_path)  # 1 hour retention
        stats = gc.collect()
        
        assert stats["files_removed"] >= 1
        assert not old_file.exists()
        assert new_file.exists()
    
    def test_zero_retention_disables_age_cleanup(self, sessions_path):
        """Should not remove files based on age when retention is 0."""
        config = TTSConfig(gc_retention_hours=0, gc_max_storage_mb=1000)
        
        old_file = create_tts_file(sessions_path, "2025-12-21_12-00-00", 1, "old", age_hours=100)
        
        gc = TTSGarbageCollector(config, sessions_path)
        stats = gc.collect()
        
        # Should not remove based on age
        assert old_file.exists()


class TestGarbageCollectorStorageLimit:
    """Tests for storage limit enforcement."""
    
    def test_removes_oldest_when_over_limit(self, sessions_path):
        """Should remove oldest files when storage limit exceeded."""
        # Config with 1MB limit, files totaling over 1MB
        config = TTSConfig(gc_retention_hours=0, gc_max_storage_mb=1)  # 1MB = 1048576 bytes
        
        # Create files totaling more than 1MB limit
        file1 = create_tts_file(sessions_path, "2025-12-21_12-00-00", 1, "oldest", 
                                age_hours=5, size_bytes=400000)  # 400KB oldest
        file2 = create_tts_file(sessions_path, "2025-12-21_12-00-00", 2, "newer", 
                                age_hours=1, size_bytes=400000)  # 400KB
        file3 = create_tts_file(sessions_path, "2025-12-21_12-00-00", 3, "newest", 
                                age_hours=0, size_bytes=400000)  # 400KB newest (total 1.2MB)
        
        gc = TTSGarbageCollector(config, sessions_path)
        stats = gc.collect()
        
        # Should have removed at least one file
        assert stats["files_removed"] >= 1
        # Oldest should be removed first
        assert not file1.exists()
    
    def test_zero_storage_limit_disables_storage_cleanup(self, sessions_path):
        """Should not enforce storage limit when set to 0."""
        config = TTSConfig(gc_retention_hours=0, gc_max_storage_mb=0)
        
        # Create many files
        files = [
            create_tts_file(sessions_path, "2025-12-21_12-00-00", i, f"oracle_{i}", 
                           size_bytes=10000)
            for i in range(1, 11)
        ]
        
        gc = TTSGarbageCollector(config, sessions_path)
        stats = gc.collect()
        
        # All files should still exist
        assert all(f.exists() for f in files)


class TestGarbageCollectorStats:
    """Tests for garbage collector statistics."""
    
    def test_get_storage_stats(self, tts_config, sessions_path):
        """Should return accurate storage statistics."""
        # Create test files
        create_tts_file(sessions_path, "2025-12-21_12-00-00", 1, "a", size_bytes=1000)
        create_tts_file(sessions_path, "2025-12-21_12-00-00", 2, "b", size_bytes=2000)
        
        gc = TTSGarbageCollector(tts_config, sessions_path)
        stats = gc.get_storage_stats()
        
        assert stats["total_files"] == 2
        assert stats["total_bytes"] == 3000
    
    def test_collect_returns_stats(self, tts_config, sessions_path):
        """Should return statistics after collection."""
        create_tts_file(sessions_path, "2025-12-21_12-00-00", 1, "old", 
                       age_hours=5, size_bytes=1000)
        
        gc = TTSGarbageCollector(tts_config, sessions_path)
        stats = gc.collect()
        
        assert "files_removed" in stats
        assert "bytes_freed" in stats
        assert "errors" in stats
        assert stats["files_removed"] == 1
        assert stats["bytes_freed"] == 1000


class TestGarbageCollectorOrphan:
    """Tests for orphan artifact detection."""
    
    def test_mark_orphan_returns_count(self, tts_config, sessions_path):
        """Should return count of orphan artifacts."""
        # Create test files
        create_tts_file(sessions_path, "2025-12-21_12-00-00", 1, "a")
        create_tts_file(sessions_path, "2025-12-21_12-00-00", 2, "b")
        
        gc = TTSGarbageCollector(tts_config, sessions_path)
        count = gc.mark_orphan("2025-12-21_12-00-00")
        
        assert count == 2
    
    def test_mark_orphan_nonexistent_session(self, tts_config, sessions_path):
        """Should handle nonexistent session gracefully."""
        gc = TTSGarbageCollector(tts_config, sessions_path)
        count = gc.mark_orphan("nonexistent-session")
        
        assert count == 0
