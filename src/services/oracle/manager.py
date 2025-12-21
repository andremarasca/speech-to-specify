"""Oracle manager for loading and caching oracle personalities.

Per contracts/oracle-manager.md for 007-contextual-oracle-feedback.

This module provides the OracleManager class that handles:
    - Loading oracles from filesystem
    - Caching with TTL-based expiration
    - Automatic detection of new/removed files
"""

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from src.models.oracle import Oracle
from src.services.oracle.loader import OracleLoader

logger = logging.getLogger(__name__)


class OracleManager:
    """
    Manages oracle personality files with caching.
    
    Per contracts/oracle-manager.md.
    
    Implements lazy loading with TTL cache to balance freshness
    with performance. New oracle files are detected automatically
    after cache expiration.
    
    Per research.md: Uses TTL cache instead of file watchers for
    simplicity and stdlib purity.
    """
    
    def __init__(
        self,
        oracles_dir: Path,
        placeholder: str = "{{CONTEXT}}",
        cache_ttl: int = 10,
    ):
        """
        Initialize manager with configuration.
        
        Args:
            oracles_dir: Directory containing oracle markdown files
            placeholder: Placeholder string for context injection
            cache_ttl: Cache time-to-live in seconds
        """
        self.oracles_dir = Path(oracles_dir)
        self.placeholder = placeholder
        self.cache_ttl = cache_ttl
        
        self._loader = OracleLoader(placeholder=placeholder)
        self._cache: dict[str, Oracle] = {}
        self._cache_expiry: datetime = datetime.min
        
        # Log warning if directory doesn't exist (BC-OM-006)
        if not self.oracles_dir.exists():
            logger.warning(
                f"Oracles directory does not exist: {self.oracles_dir}. "
                "No oracles will be available until directory is created."
            )
    
    def _is_cache_valid(self) -> bool:
        """Check if cache is still valid."""
        return datetime.now() < self._cache_expiry
    
    def _reload_cache(self) -> None:
        """
        Reload oracles from filesystem.
        
        Scans the oracles directory for .md files and loads them.
        Invalid files are skipped with warnings.
        """
        self._cache.clear()
        
        if not self.oracles_dir.exists():
            logger.debug(f"Oracles directory missing: {self.oracles_dir}")
            self._cache_expiry = datetime.now() + timedelta(seconds=self.cache_ttl)
            return
        
        if not self.oracles_dir.is_dir():
            logger.warning(f"Oracles path is not a directory: {self.oracles_dir}")
            self._cache_expiry = datetime.now() + timedelta(seconds=self.cache_ttl)
            return
        
        # Scan for markdown files
        for file_path in self.oracles_dir.glob("*.md"):
            oracle = self._loader.load(file_path)
            if oracle:
                self._cache[oracle.id] = oracle
        
        self._cache_expiry = datetime.now() + timedelta(seconds=self.cache_ttl)
        logger.debug(f"Loaded {len(self._cache)} oracles from {self.oracles_dir}")
    
    def list_oracles(self) -> list[Oracle]:
        """
        Return all valid oracles, refreshing cache if expired.
        
        Per BC-OM-001: Cache expiration triggers filesystem scan.
        Per BC-OM-005: Returns empty list if directory is empty.
        
        Returns:
            List of Oracle objects sorted by name
        """
        if not self._is_cache_valid():
            self._reload_cache()
        
        # Return sorted by name for consistent ordering
        return sorted(self._cache.values(), key=lambda o: o.name.lower())
    
    def get_oracle(self, oracle_id: str) -> Optional[Oracle]:
        """
        Get oracle by ID, or None if not found.
        
        Per BC-OM-007: ID is deterministic 8-char hash.
        
        Args:
            oracle_id: 8-character oracle identifier
            
        Returns:
            Oracle if found, None otherwise
        """
        if not self._is_cache_valid():
            self._reload_cache()
        
        return self._cache.get(oracle_id)
    
    def get_oracle_by_name(self, name: str) -> Optional[Oracle]:
        """
        Get oracle by display name (case-insensitive).
        
        Args:
            name: Display name to search for
            
        Returns:
            Oracle if found, None otherwise
        """
        if not self._is_cache_valid():
            self._reload_cache()
        
        name_lower = name.lower()
        for oracle in self._cache.values():
            if oracle.name.lower() == name_lower:
                return oracle
        return None
    
    def refresh(self) -> None:
        """
        Force cache refresh.
        
        Useful when files have been modified and immediate
        update is needed without waiting for TTL expiration.
        """
        self._reload_cache()
    
    def is_valid(self, file_path: Path) -> bool:
        """
        Check if file is a valid oracle (readable markdown with title).
        
        Args:
            file_path: Path to check
            
        Returns:
            True if valid oracle file
        """
        return self._loader.is_valid(file_path)
    
    @property
    def oracle_count(self) -> int:
        """Get the number of cached oracles."""
        if not self._is_cache_valid():
            self._reload_cache()
        return len(self._cache)
    
    @property
    def is_empty(self) -> bool:
        """Check if no oracles are available."""
        return self.oracle_count == 0
