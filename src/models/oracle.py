"""Oracle model for contextual feedback personalities.

Per data-model.md for 007-contextual-oracle-feedback.

This module defines the Oracle dataclass representing a loaded oracle
personality from the filesystem. Oracles are markdown files that contain
LLM prompts with context placeholders.
"""

from dataclasses import dataclass
from pathlib import Path


@dataclass
class Oracle:
    """
    Represents a loaded oracle personality from the filesystem.
    
    Per data-model.md for 007-contextual-oracle-feedback.
    
    Attributes:
        id: 8-character SHA256 hash of file path (unique, immutable)
        name: Display name extracted from markdown H1 (non-empty, stripped)
        file_path: Absolute path to the .md file (exists, readable)
        prompt_content: Full content of the markdown file (non-empty)
        placeholder: Placeholder string for context injection (default: {{CONTEXT}})
    
    Validation Rules:
        - File must exist and be readable
        - First line must contain H1 heading (# Title) or fallback to filename
        - If placeholder not found in content, use append mode
    """
    
    id: str  # 8-char SHA256 hash
    name: str  # Display name from H1
    file_path: Path  # Absolute path
    prompt_content: str  # Full markdown content
    placeholder: str = "{{CONTEXT}}"  # Context placeholder
    
    def has_placeholder(self) -> bool:
        """Check if the oracle prompt contains the placeholder."""
        return self.placeholder in self.prompt_content
    
    def __post_init__(self):
        """Validate oracle fields after initialization."""
        if not self.id or len(self.id) != 8:
            raise ValueError("Oracle id must be exactly 8 characters")
        if not self.name:
            raise ValueError("Oracle name cannot be empty")
        if not self.prompt_content:
            raise ValueError("Oracle prompt_content cannot be empty")
