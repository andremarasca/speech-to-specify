"""Oracle loader for parsing markdown personality files.

Per contracts/oracle-manager.md for 007-contextual-oracle-feedback.

This module handles loading and parsing oracle markdown files,
extracting titles and generating deterministic IDs.
"""

import hashlib
import logging
import re
from pathlib import Path
from typing import Optional

from src.models.oracle import Oracle

logger = logging.getLogger(__name__)


class OracleLoader:
    """
    Loads oracle personality files from the filesystem.
    
    Per contracts/oracle-manager.md.
    
    Responsibilities:
        - Parse markdown files to extract H1 title
        - Generate deterministic 8-char ID from file path
        - Validate file content and structure
    """
    
    # Regex to match H1 heading: # Title
    H1_PATTERN = re.compile(r'^#\s+(.+)$', re.MULTILINE)
    
    def __init__(self, placeholder: str = "{{CONTEXT}}"):
        """
        Initialize the oracle loader.
        
        Args:
            placeholder: Placeholder string for context injection
        """
        self.placeholder = placeholder
    
    def generate_oracle_id(self, file_path: Path) -> str:
        """
        Generate 8-char hash from file path.
        
        Per research.md decision: Use SHA256 hash of path for determinism.
        
        Args:
            file_path: Path to the oracle file
            
        Returns:
            8-character hex hash
        """
        return hashlib.sha256(str(file_path).encode()).hexdigest()[:8]
    
    def extract_title(self, content: str, fallback_name: str) -> str:
        """
        Extract title from markdown H1 heading.
        
        Per BC-OM-008 and BC-OM-009:
            - First H1 heading becomes the name
            - Fallback to filename if no H1 found
        
        Args:
            content: Markdown file content
            fallback_name: Filename to use if no H1 found
            
        Returns:
            Extracted or fallback name (stripped)
        """
        match = self.H1_PATTERN.search(content)
        if match:
            return match.group(1).strip()
        return fallback_name
    
    def load(self, file_path: Path) -> Optional[Oracle]:
        """
        Load an oracle from a markdown file.
        
        Per BC-OM-004: Invalid files are skipped with warning log.
        
        Args:
            file_path: Path to the oracle markdown file
            
        Returns:
            Oracle if valid, None if invalid/unreadable
        """
        if not file_path.exists():
            logger.warning(f"Oracle file not found: {file_path}")
            return None
        
        if not file_path.is_file():
            logger.warning(f"Oracle path is not a file: {file_path}")
            return None
        
        if file_path.suffix.lower() != ".md":
            logger.debug(f"Skipping non-markdown file: {file_path}")
            return None
        
        try:
            content = file_path.read_text(encoding="utf-8")
        except (OSError, PermissionError) as e:
            logger.warning(f"Cannot read oracle file {file_path}: {e}")
            return None
        
        if not content.strip():
            logger.warning(f"Oracle file is empty: {file_path}")
            return None
        
        # Extract title (fallback to filename without extension)
        fallback_name = file_path.stem
        name = self.extract_title(content, fallback_name)
        
        # Generate deterministic ID
        oracle_id = self.generate_oracle_id(file_path)
        
        # Log if placeholder is missing (will use append mode)
        if self.placeholder not in content:
            logger.info(
                f"Oracle '{name}' has no placeholder '{self.placeholder}', "
                "context will be appended"
            )
        
        try:
            oracle = Oracle(
                id=oracle_id,
                name=name,
                file_path=file_path.absolute(),
                prompt_content=content,
                placeholder=self.placeholder,
            )
            logger.debug(f"Loaded oracle: {name} (id={oracle_id})")
            return oracle
        except ValueError as e:
            logger.warning(f"Invalid oracle file {file_path}: {e}")
            return None
    
    def is_valid(self, file_path: Path) -> bool:
        """
        Check if file is a valid oracle (readable markdown with content).
        
        Args:
            file_path: Path to check
            
        Returns:
            True if valid oracle file
        """
        if not file_path.exists() or not file_path.is_file():
            return False
        
        if file_path.suffix.lower() != ".md":
            return False
        
        try:
            content = file_path.read_text(encoding="utf-8")
            return bool(content.strip())
        except (OSError, PermissionError):
            return False
