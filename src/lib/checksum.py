"""Checksum service for file integrity verification.

Provides SHA-256 hashing for audio files to ensure data integrity
and detect corruption. Per Constitution Pillar I (Integridade do Usuário).
"""

import hashlib
from pathlib import Path
from typing import Optional


class ChecksumService:
    """Service for computing and verifying file checksums.
    
    Uses SHA-256 algorithm for cryptographic integrity guarantees.
    Checksums are prefixed with algorithm identifier for future extensibility.
    """
    
    ALGORITHM = "sha256"
    CHUNK_SIZE = 8192  # 8KB chunks for memory efficiency
    
    @classmethod
    def compute_file_checksum(cls, file_path: Path) -> str:
        """Compute SHA-256 checksum of a file.
        
        Args:
            file_path: Path to the file to checksum.
            
        Returns:
            Checksum string in format "sha256:<hex_digest>".
            
        Raises:
            FileNotFoundError: If file does not exist.
            PermissionError: If file cannot be read.
            IsADirectoryError: If path is a directory.
        """
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(cls.CHUNK_SIZE):
                hasher.update(chunk)
        return f"{cls.ALGORITHM}:{hasher.hexdigest()}"
    
    @classmethod
    def compute_bytes_checksum(cls, data: bytes) -> str:
        """Compute SHA-256 checksum of bytes data.
        
        Args:
            data: Bytes to checksum.
            
        Returns:
            Checksum string in format "sha256:<hex_digest>".
        """
        hasher = hashlib.sha256()
        hasher.update(data)
        return f"{cls.ALGORITHM}:{hasher.hexdigest()}"
    
    @classmethod
    def verify_file_checksum(cls, file_path: Path, expected_checksum: str) -> bool:
        """Verify a file's checksum matches expected value.
        
        Args:
            file_path: Path to the file to verify.
            expected_checksum: Expected checksum in format "algorithm:hex_digest".
            
        Returns:
            True if checksum matches, False otherwise.
            
        Raises:
            FileNotFoundError: If file does not exist.
            ValueError: If checksum format is invalid.
        """
        # Parse expected checksum
        if ":" not in expected_checksum:
            raise ValueError(
                f"Invalid checksum format: {expected_checksum}. "
                f"Expected format 'algorithm:hex_digest'."
            )
        
        algorithm, _ = expected_checksum.split(":", 1)
        if algorithm != cls.ALGORITHM:
            raise ValueError(
                f"Unsupported checksum algorithm: {algorithm}. "
                f"Only '{cls.ALGORITHM}' is supported."
            )
        
        actual_checksum = cls.compute_file_checksum(file_path)
        return actual_checksum == expected_checksum
    
    @classmethod
    def parse_checksum(cls, checksum: str) -> tuple[str, str]:
        """Parse a checksum string into algorithm and hex digest.
        
        Args:
            checksum: Checksum in format "algorithm:hex_digest".
            
        Returns:
            Tuple of (algorithm, hex_digest).
            
        Raises:
            ValueError: If format is invalid.
        """
        if ":" not in checksum:
            raise ValueError(
                f"Invalid checksum format: {checksum}. "
                f"Expected format 'algorithm:hex_digest'."
            )
        return tuple(checksum.split(":", 1))  # type: ignore
    
    @classmethod
    def get_hex_digest(cls, checksum: str) -> str:
        """Extract hex digest from a checksum string.
        
        Args:
            checksum: Checksum in format "algorithm:hex_digest".
            
        Returns:
            The hex digest portion.
            
        Raises:
            ValueError: If format is invalid.
        """
        _, hex_digest = cls.parse_checksum(checksum)
        return hex_digest
