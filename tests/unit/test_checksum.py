"""Unit tests for ChecksumService.

Per tasks.md T006 for 004-resilient-voice-capture.
Tests SHA-256 file integrity verification functionality.
"""

import hashlib
import tempfile
from pathlib import Path

import pytest

from src.lib.checksum import ChecksumService


class TestChecksumService:
    """Tests for ChecksumService."""
    
    def test_compute_file_checksum_returns_sha256_prefix(self, tmp_path: Path) -> None:
        """Checksum should include algorithm prefix."""
        test_file = tmp_path / "test.txt"
        test_file.write_bytes(b"hello world")
        
        result = ChecksumService.compute_file_checksum(test_file)
        
        assert result.startswith("sha256:")
    
    def test_compute_file_checksum_matches_hashlib(self, tmp_path: Path) -> None:
        """Checksum should match direct hashlib computation."""
        test_content = b"test content for checksum"
        test_file = tmp_path / "test.bin"
        test_file.write_bytes(test_content)
        
        expected_hash = hashlib.sha256(test_content).hexdigest()
        result = ChecksumService.compute_file_checksum(test_file)
        
        assert result == f"sha256:{expected_hash}"
    
    def test_compute_file_checksum_empty_file(self, tmp_path: Path) -> None:
        """Empty file should produce valid checksum."""
        test_file = tmp_path / "empty.txt"
        test_file.write_bytes(b"")
        
        expected_hash = hashlib.sha256(b"").hexdigest()
        result = ChecksumService.compute_file_checksum(test_file)
        
        assert result == f"sha256:{expected_hash}"
    
    def test_compute_file_checksum_large_file(self, tmp_path: Path) -> None:
        """Large file should be processed correctly in chunks."""
        # Create a file larger than chunk size (8KB)
        large_content = b"x" * (10 * 1024)  # 10KB
        test_file = tmp_path / "large.bin"
        test_file.write_bytes(large_content)
        
        expected_hash = hashlib.sha256(large_content).hexdigest()
        result = ChecksumService.compute_file_checksum(test_file)
        
        assert result == f"sha256:{expected_hash}"
    
    def test_compute_file_checksum_file_not_found(self) -> None:
        """Non-existent file should raise FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            ChecksumService.compute_file_checksum(Path("/nonexistent/file.txt"))
    
    def test_compute_file_checksum_directory(self, tmp_path: Path) -> None:
        """Directory should raise an error (IsADirectoryError on Unix, PermissionError on Windows)."""
        with pytest.raises((IsADirectoryError, PermissionError)):
            ChecksumService.compute_file_checksum(tmp_path)
    
    def test_compute_bytes_checksum(self) -> None:
        """Bytes checksum should match file checksum for same content."""
        test_content = b"test bytes content"
        expected_hash = hashlib.sha256(test_content).hexdigest()
        
        result = ChecksumService.compute_bytes_checksum(test_content)
        
        assert result == f"sha256:{expected_hash}"
    
    def test_compute_bytes_checksum_empty(self) -> None:
        """Empty bytes should produce valid checksum."""
        expected_hash = hashlib.sha256(b"").hexdigest()
        result = ChecksumService.compute_bytes_checksum(b"")
        
        assert result == f"sha256:{expected_hash}"
    
    def test_verify_file_checksum_valid(self, tmp_path: Path) -> None:
        """Valid checksum should return True."""
        test_content = b"verification test"
        test_file = tmp_path / "verify.txt"
        test_file.write_bytes(test_content)
        
        checksum = ChecksumService.compute_file_checksum(test_file)
        result = ChecksumService.verify_file_checksum(test_file, checksum)
        
        assert result is True
    
    def test_verify_file_checksum_invalid(self, tmp_path: Path) -> None:
        """Invalid checksum should return False."""
        test_file = tmp_path / "verify.txt"
        test_file.write_bytes(b"original content")
        
        fake_checksum = "sha256:" + "a" * 64
        result = ChecksumService.verify_file_checksum(test_file, fake_checksum)
        
        assert result is False
    
    def test_verify_file_checksum_file_modified(self, tmp_path: Path) -> None:
        """Modified file should fail verification."""
        test_file = tmp_path / "modify.txt"
        test_file.write_bytes(b"original content")
        
        checksum = ChecksumService.compute_file_checksum(test_file)
        
        # Modify the file
        test_file.write_bytes(b"modified content")
        
        result = ChecksumService.verify_file_checksum(test_file, checksum)
        assert result is False
    
    def test_verify_file_checksum_invalid_format(self, tmp_path: Path) -> None:
        """Invalid checksum format should raise ValueError."""
        test_file = tmp_path / "test.txt"
        test_file.write_bytes(b"test")
        
        with pytest.raises(ValueError, match="Invalid checksum format"):
            ChecksumService.verify_file_checksum(test_file, "invalid_no_colon")
    
    def test_verify_file_checksum_unsupported_algorithm(self, tmp_path: Path) -> None:
        """Unsupported algorithm should raise ValueError."""
        test_file = tmp_path / "test.txt"
        test_file.write_bytes(b"test")
        
        with pytest.raises(ValueError, match="Unsupported checksum algorithm"):
            ChecksumService.verify_file_checksum(test_file, "md5:abc123")
    
    def test_verify_file_checksum_file_not_found(self) -> None:
        """Non-existent file should raise FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            ChecksumService.verify_file_checksum(
                Path("/nonexistent/file.txt"),
                "sha256:" + "a" * 64
            )
    
    def test_parse_checksum_valid(self) -> None:
        """Valid checksum should be parsed correctly."""
        algorithm, hex_digest = ChecksumService.parse_checksum("sha256:abc123def")
        
        assert algorithm == "sha256"
        assert hex_digest == "abc123def"
    
    def test_parse_checksum_multiple_colons(self) -> None:
        """Checksum with colons in hex should parse correctly."""
        algorithm, hex_digest = ChecksumService.parse_checksum("sha256:abc:def:123")
        
        assert algorithm == "sha256"
        assert hex_digest == "abc:def:123"
    
    def test_parse_checksum_invalid_format(self) -> None:
        """Invalid format should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid checksum format"):
            ChecksumService.parse_checksum("no_colon_here")
    
    def test_get_hex_digest(self) -> None:
        """Should extract hex digest from checksum."""
        expected_digest = "a" * 64
        result = ChecksumService.get_hex_digest(f"sha256:{expected_digest}")
        
        assert result == expected_digest
    
    def test_get_hex_digest_invalid_format(self) -> None:
        """Invalid format should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid checksum format"):
            ChecksumService.get_hex_digest("invalid")
    
    def test_deterministic_checksums(self, tmp_path: Path) -> None:
        """Same content should always produce same checksum."""
        test_content = b"deterministic test content"
        test_file = tmp_path / "deterministic.txt"
        test_file.write_bytes(test_content)
        
        checksum1 = ChecksumService.compute_file_checksum(test_file)
        checksum2 = ChecksumService.compute_file_checksum(test_file)
        
        assert checksum1 == checksum2
    
    def test_different_content_different_checksums(self, tmp_path: Path) -> None:
        """Different content should produce different checksums."""
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        file1.write_bytes(b"content A")
        file2.write_bytes(b"content B")
        
        checksum1 = ChecksumService.compute_file_checksum(file1)
        checksum2 = ChecksumService.compute_file_checksum(file2)
        
        assert checksum1 != checksum2
