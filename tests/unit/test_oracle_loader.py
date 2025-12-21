"""Unit tests for OracleLoader.

Per tasks.md T023 for 007-contextual-oracle-feedback.

Tests oracle file parsing and title extraction.
"""

import pytest
import tempfile
from pathlib import Path

from src.services.oracle.loader import OracleLoader


class TestOracleLoaderTitleExtraction:
    """Tests for title extraction from oracle files."""
    
    def test_extract_simple_h1(self):
        """Extract title from simple H1."""
        loader = OracleLoader()
        content = "# Simple Title\n\nContent here"
        
        title = loader.extract_title(content, "fallback")
        
        assert title == "Simple Title"
    
    def test_extract_h1_with_accents(self):
        """Extract title with Portuguese accents."""
        loader = OracleLoader()
        content = "# Cético Profissional\n\nAnálise crítica"
        
        title = loader.extract_title(content, "fallback")
        
        assert title == "Cético Profissional"
    
    def test_extract_h1_with_emoji(self):
        """Extract title with emoji."""
        loader = OracleLoader()
        content = "# 🎭 Teatro\n\nContent"
        
        title = loader.extract_title(content, "fallback")
        
        assert title == "🎭 Teatro"
    
    def test_extract_h1_not_at_start(self):
        """Extract H1 that's not at document start."""
        loader = OracleLoader()
        content = """Some preamble text

# Actual Title

More content"""
        
        title = loader.extract_title(content, "fallback")
        
        assert title == "Actual Title"
    
    def test_h1_with_multiple_spaces(self):
        """Handle H1 with multiple spaces after #."""
        loader = OracleLoader()
        content = "#   Title With Spaces\n\nContent"
        
        title = loader.extract_title(content, "fallback")
        
        assert title == "Title With Spaces"
    
    def test_fallback_no_h1(self):
        """Use fallback when no H1 present."""
        loader = OracleLoader()
        content = "Just some content without heading"
        
        title = loader.extract_title(content, "my_fallback")
        
        assert title == "my_fallback"
    
    def test_fallback_h2_only(self):
        """Use fallback when only H2 present (not H1)."""
        loader = OracleLoader()
        content = "## Secondary Heading\n\nContent"
        
        title = loader.extract_title(content, "fallback")
        
        assert title == "fallback"
    
    def test_first_h1_wins(self):
        """First H1 is used when multiple exist."""
        loader = OracleLoader()
        content = """# First Title

# Second Title

Content"""
        
        title = loader.extract_title(content, "fallback")
        
        assert title == "First Title"
    
    def test_title_is_stripped(self):
        """Title is stripped of leading/trailing whitespace."""
        loader = OracleLoader()
        content = "#   Padded Title   \n\nContent"
        
        title = loader.extract_title(content, "fallback")
        
        assert title == "Padded Title"


class TestOracleLoaderIdGeneration:
    """Tests for oracle ID generation."""
    
    def test_id_is_8_chars(self):
        """ID is exactly 8 characters."""
        loader = OracleLoader()
        
        id1 = loader.generate_oracle_id(Path("/path/to/oracle.md"))
        
        assert len(id1) == 8
    
    def test_id_is_hex(self):
        """ID is valid hex string."""
        loader = OracleLoader()
        
        id1 = loader.generate_oracle_id(Path("/some/path.md"))
        
        # Should be parseable as hex
        int(id1, 16)
    
    def test_id_is_deterministic(self):
        """Same path always produces same ID."""
        loader = OracleLoader()
        path = Path("/consistent/path.md")
        
        id1 = loader.generate_oracle_id(path)
        id2 = loader.generate_oracle_id(path)
        id3 = loader.generate_oracle_id(path)
        
        assert id1 == id2 == id3
    
    def test_different_paths_different_ids(self):
        """Different paths produce different IDs."""
        loader = OracleLoader()
        
        id1 = loader.generate_oracle_id(Path("/path/a.md"))
        id2 = loader.generate_oracle_id(Path("/path/b.md"))
        
        assert id1 != id2


class TestOracleLoaderFileLoading:
    """Tests for oracle file loading."""
    
    def test_load_complete_oracle(self):
        """Load a complete, valid oracle file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            loader = OracleLoader(placeholder="{{CONTEXT}}")
            
            content = """# Test Oracle

You are a test oracle.

{{CONTEXT}}

Provide feedback."""
            
            file_path = Path(tmpdir) / "test.md"
            file_path.write_text(content)
            
            oracle = loader.load(file_path)
            
            assert oracle is not None
            assert oracle.name == "Test Oracle"
            assert oracle.prompt_content == content
            assert oracle.has_placeholder()
    
    def test_load_oracle_without_placeholder(self):
        """Load oracle that has no placeholder."""
        with tempfile.TemporaryDirectory() as tmpdir:
            loader = OracleLoader(placeholder="{{CONTEXT}}")
            
            content = """# No Placeholder Oracle

Just instructions, no placeholder."""
            
            file_path = Path(tmpdir) / "test.md"
            file_path.write_text(content)
            
            oracle = loader.load(file_path)
            
            assert oracle is not None
            assert not oracle.has_placeholder()
    
    def test_load_uses_filename_fallback(self):
        """Oracle uses filename when no H1."""
        with tempfile.TemporaryDirectory() as tmpdir:
            loader = OracleLoader()
            
            content = "No heading, just content."
            
            file_path = Path(tmpdir) / "my_oracle_name.md"
            file_path.write_text(content)
            
            oracle = loader.load(file_path)
            
            assert oracle is not None
            assert oracle.name == "my_oracle_name"
    
    def test_is_valid_checks_file(self):
        """is_valid correctly validates oracle files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            loader = OracleLoader()
            tmppath = Path(tmpdir)
            
            # Valid file
            valid = tmppath / "valid.md"
            valid.write_text("# Valid\n\nContent")
            assert loader.is_valid(valid)
            
            # Empty file
            empty = tmppath / "empty.md"
            empty.write_text("")
            assert not loader.is_valid(empty)
            
            # Non-markdown
            txt = tmppath / "file.txt"
            txt.write_text("Content")
            assert not loader.is_valid(txt)
            
            # Nonexistent
            assert not loader.is_valid(tmppath / "nonexistent.md")
