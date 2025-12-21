"""Contract tests for OracleManager.

Per contracts/oracle-manager.md for 007-contextual-oracle-feedback.

Tests all BC-OM-* behavior contracts.
"""

import pytest
import tempfile
from pathlib import Path
from datetime import datetime, timedelta
import time

from src.services.oracle.manager import OracleManager
from src.services.oracle.loader import OracleLoader


@pytest.fixture
def temp_oracles_dir():
    """Create a temporary directory for oracle files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_oracle_content():
    """Sample oracle markdown content with placeholder."""
    return """# Cético

Você é um pensador cético.

{{CONTEXT}}

Analise criticamente.
"""


@pytest.fixture
def sample_oracle_without_placeholder():
    """Sample oracle without placeholder."""
    return """# Visionário

Você é um visionário.

Expanda as possibilidades.
"""


class TestOracleLoader:
    """Tests for OracleLoader."""
    
    def test_generate_oracle_id_deterministic(self, temp_oracles_dir):
        """BC-OM-007: ID is deterministic 8-char hash."""
        loader = OracleLoader()
        file_path = temp_oracles_dir / "cetico.md"
        
        # Generate ID twice for same path
        id1 = loader.generate_oracle_id(file_path)
        id2 = loader.generate_oracle_id(file_path)
        
        assert id1 == id2
        assert len(id1) == 8
        assert id1.isalnum()
    
    def test_extract_title_from_h1(self, sample_oracle_content):
        """BC-OM-008: Title extracted from H1 heading."""
        loader = OracleLoader()
        title = loader.extract_title(sample_oracle_content, "fallback")
        
        assert title == "Cético"
    
    def test_extract_title_fallback(self):
        """BC-OM-009: Fallback to filename if no H1."""
        loader = OracleLoader()
        content = "No heading here, just content."
        title = loader.extract_title(content, "fallback_name")
        
        assert title == "fallback_name"
    
    def test_load_valid_oracle(self, temp_oracles_dir, sample_oracle_content):
        """Load a valid oracle file."""
        loader = OracleLoader()
        
        # Create oracle file
        file_path = temp_oracles_dir / "cetico.md"
        file_path.write_text(sample_oracle_content, encoding="utf-8")
        
        oracle = loader.load(file_path)
        
        assert oracle is not None
        assert oracle.name == "Cético"
        assert oracle.has_placeholder()
        assert len(oracle.id) == 8
    
    def test_load_nonexistent_file(self, temp_oracles_dir):
        """BC-OM-004: Skip nonexistent files."""
        loader = OracleLoader()
        
        oracle = loader.load(temp_oracles_dir / "nonexistent.md")
        
        assert oracle is None
    
    def test_load_empty_file(self, temp_oracles_dir):
        """BC-OM-004: Skip empty files."""
        loader = OracleLoader()
        
        file_path = temp_oracles_dir / "empty.md"
        file_path.write_text("")
        
        oracle = loader.load(file_path)
        
        assert oracle is None
    
    def test_load_non_markdown_file(self, temp_oracles_dir):
        """Skip non-markdown files."""
        loader = OracleLoader()
        
        file_path = temp_oracles_dir / "readme.txt"
        file_path.write_text("Some text content")
        
        oracle = loader.load(file_path)
        
        assert oracle is None


class TestOracleManager:
    """Tests for OracleManager."""
    
    def test_list_oracles_empty_directory(self, temp_oracles_dir):
        """BC-OM-005: Empty directory returns empty list."""
        manager = OracleManager(oracles_dir=temp_oracles_dir)
        
        oracles = manager.list_oracles()
        
        assert oracles == []
        assert manager.is_empty
    
    def test_list_oracles_nonexistent_directory(self, temp_oracles_dir):
        """BC-OM-006: Nonexistent directory returns empty list."""
        nonexistent = temp_oracles_dir / "does_not_exist"
        manager = OracleManager(oracles_dir=nonexistent)
        
        oracles = manager.list_oracles()
        
        assert oracles == []
    
    def test_list_oracles_with_files(self, temp_oracles_dir, sample_oracle_content):
        """Load oracles from directory."""
        # Create multiple oracle files
        (temp_oracles_dir / "cetico.md").write_text(sample_oracle_content, encoding="utf-8")
        (temp_oracles_dir / "visionario.md").write_text("# Visionario\n\nContent", encoding="utf-8")
        
        manager = OracleManager(oracles_dir=temp_oracles_dir)
        oracles = manager.list_oracles()
        
        assert len(oracles) == 2
        names = [o.name for o in oracles]
        assert "Cético" in names
        assert "Visionario" in names
    
    def test_cache_expiration(self, temp_oracles_dir, sample_oracle_content):
        """BC-OM-001: Cache expires after TTL."""
        # Create one oracle
        (temp_oracles_dir / "cetico.md").write_text(sample_oracle_content, encoding="utf-8")
        
        # Use very short TTL for test
        manager = OracleManager(oracles_dir=temp_oracles_dir, cache_ttl=1)
        
        # First call loads from filesystem
        oracles1 = manager.list_oracles()
        assert len(oracles1) == 1
        
        # Add another oracle
        (temp_oracles_dir / "visionario.md").write_text("# Visionario\n\nContent", encoding="utf-8")
        
        # Immediate second call should still return 1 (cached)
        oracles2 = manager.list_oracles()
        assert len(oracles2) == 1
        
        # Wait for cache to expire
        time.sleep(1.1)
        
        # Now should see the new oracle
        oracles3 = manager.list_oracles()
        assert len(oracles3) == 2
    
    def test_new_file_detection(self, temp_oracles_dir, sample_oracle_content):
        """BC-OM-002: New files detected after cache expires."""
        manager = OracleManager(oracles_dir=temp_oracles_dir, cache_ttl=1)
        
        # Empty initially
        assert manager.list_oracles() == []
        
        # Add oracle
        (temp_oracles_dir / "cetico.md").write_text(sample_oracle_content, encoding="utf-8")
        
        # Wait for cache to expire
        time.sleep(1.1)
        
        # Now should be detected
        oracles = manager.list_oracles()
        assert len(oracles) == 1
    
    def test_file_removal_detection(self, temp_oracles_dir, sample_oracle_content):
        """BC-OM-003: Removed files no longer appear after cache expires."""
        # Create oracle
        oracle_file = temp_oracles_dir / "cetico.md"
        oracle_file.write_text(sample_oracle_content, encoding="utf-8")
        
        manager = OracleManager(oracles_dir=temp_oracles_dir, cache_ttl=1)
        
        # Should have one oracle
        assert len(manager.list_oracles()) == 1
        
        # Remove the file
        oracle_file.unlink()
        
        # Wait for cache to expire
        time.sleep(1.1)
        
        # Should be empty now
        assert len(manager.list_oracles()) == 0
    
    def test_invalid_file_skipped(self, temp_oracles_dir):
        """BC-OM-004: Invalid files skipped with warning."""
        # Create valid oracle
        (temp_oracles_dir / "valid.md").write_text("# Valid\n\nContent", encoding="utf-8")
        
        # Create invalid (empty) file
        (temp_oracles_dir / "invalid.md").write_text("", encoding="utf-8")
        
        manager = OracleManager(oracles_dir=temp_oracles_dir)
        oracles = manager.list_oracles()
        
        # Only valid oracle should be loaded
        assert len(oracles) == 1
        assert oracles[0].name == "Valid"
    
    def test_get_oracle_by_id(self, temp_oracles_dir, sample_oracle_content):
        """Get oracle by 8-char ID."""
        (temp_oracles_dir / "cetico.md").write_text(sample_oracle_content, encoding="utf-8")
        
        manager = OracleManager(oracles_dir=temp_oracles_dir)
        oracles = manager.list_oracles()
        
        oracle_id = oracles[0].id
        found = manager.get_oracle(oracle_id)
        
        assert found is not None
        assert found.name == "Cético"
    
    def test_get_oracle_not_found(self, temp_oracles_dir):
        """Get oracle returns None for unknown ID."""
        manager = OracleManager(oracles_dir=temp_oracles_dir)
        
        found = manager.get_oracle("unknown1")
        
        assert found is None
    
    def test_get_oracle_by_name(self, temp_oracles_dir, sample_oracle_content):
        """Get oracle by display name (case-insensitive)."""
        (temp_oracles_dir / "cetico.md").write_text(sample_oracle_content, encoding="utf-8")
        
        manager = OracleManager(oracles_dir=temp_oracles_dir)
        
        # Case-insensitive lookup
        found = manager.get_oracle_by_name("CÉTICO")
        
        assert found is not None
        assert found.name == "Cético"
    
    def test_force_refresh(self, temp_oracles_dir, sample_oracle_content):
        """Force cache refresh."""
        manager = OracleManager(oracles_dir=temp_oracles_dir, cache_ttl=3600)
        
        # Empty initially
        assert manager.list_oracles() == []
        
        # Add oracle
        (temp_oracles_dir / "cetico.md").write_text(sample_oracle_content, encoding="utf-8")
        
        # Still empty (cached)
        assert manager.list_oracles() == []
        
        # Force refresh
        manager.refresh()
        
        # Now should be detected
        assert len(manager.list_oracles()) == 1
    
    def test_oracles_sorted_by_name(self, temp_oracles_dir):
        """Oracles returned sorted by name."""
        # Create oracles in non-alphabetical order
        (temp_oracles_dir / "z.md").write_text("# Zebra\n\nContent", encoding="utf-8")
        (temp_oracles_dir / "a.md").write_text("# Alfa\n\nContent", encoding="utf-8")
        (temp_oracles_dir / "m.md").write_text("# Middle\n\nContent", encoding="utf-8")
        
        manager = OracleManager(oracles_dir=temp_oracles_dir)
        oracles = manager.list_oracles()
        
        names = [o.name for o in oracles]
        assert names == ["Alfa", "Middle", "Zebra"]
