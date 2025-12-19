"""Name generator for intelligible session names.

This module implements the NameGenerator contract for creating
human-readable session names based on content or timestamps.

Following research.md decision: Cascading fallback strategy
(timestamp → transcription → LLM title → user-assigned).
"""

import logging
import re
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

from src.models.session import NameSource

logger = logging.getLogger(__name__)

# Portuguese month names for fallback generation
MONTH_NAMES_PT = [
    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"
]

# Portuguese filler words to filter from transcriptions
FILLER_WORDS_PT = {
    "um", "uma", "uns", "umas",
    "o", "a", "os", "as",
    "é", "eh", "ah", "oh", "uh",
    "então", "tipo", "né", "sabe",
    "assim", "bem", "bom", "olha",
    "e", "ou", "mas", "porque",
    "que", "de", "do", "da", "dos", "das",
    "no", "na", "nos", "nas",
    "em", "para", "por", "com",
}


class NameGenerator(ABC):
    """
    Contract for generating intelligible session names.

    Implementations should follow the cascading fallback strategy
    defined in research.md.
    """

    @abstractmethod
    def generate_fallback_name(self, created_at: datetime) -> str:
        """
        Generate a fallback name based on creation timestamp.

        Format: "Áudio de {day} de {month}" in Portuguese locale.
        Example: "Áudio de 18 de Dezembro"

        Args:
            created_at: Session creation timestamp

        Returns:
            Human-readable timestamp-based name
        """
        pass

    @abstractmethod
    def generate_from_transcript(self, transcript: str) -> Optional[str]:
        """
        Extract a name from transcription text.

        Takes the first 3-5 meaningful words, excluding fillers.
        Returns None if transcript is too short or meaningless.

        Args:
            transcript: Full transcription text

        Returns:
            Extracted name or None if extraction fails
        """
        pass

    @abstractmethod
    def generate_from_llm_output(self, llm_output: str) -> Optional[str]:
        """
        Extract a title from LLM processing output.

        Looks for explicit title markers or first heading.
        Returns None if no title found.

        Args:
            llm_output: LLM-generated artifact content

        Returns:
            Extracted title or None if not found
        """
        pass

    @abstractmethod
    def ensure_unique(
        self,
        base_name: str,
        existing_names: set[str]
    ) -> str:
        """
        Ensure name uniqueness by adding suffix if needed.

        Format: "{base_name} (N)" where N starts at 2.

        Args:
            base_name: Proposed name
            existing_names: Set of existing session names

        Returns:
            Unique name (may be unchanged if already unique)
        """
        pass


class DefaultNameGenerator(NameGenerator):
    """
    Default implementation of NameGenerator.

    Uses Portuguese locale for fallback names and filters
    Portuguese filler words from transcriptions.
    """

    MAX_NAME_LENGTH = 100
    MIN_MEANINGFUL_WORDS = 2
    MAX_WORDS_FROM_TRANSCRIPT = 5

    def generate_fallback_name(self, created_at: datetime) -> str:
        """Generate Portuguese timestamp-based fallback name."""
        day = created_at.day
        month = MONTH_NAMES_PT[created_at.month - 1]
        return f"Áudio de {day} de {month}"

    def generate_from_transcript(self, transcript: str) -> Optional[str]:
        """Extract meaningful words from transcript as name."""
        if not transcript or not transcript.strip():
            return None

        # Tokenize and filter
        words = transcript.split()
        meaningful = [
            w for w in words
            if w.lower().strip(".,!?;:") not in FILLER_WORDS_PT
            and len(w) > 1  # Skip single characters
        ]

        # Need minimum meaningful content
        if len(meaningful) < self.MIN_MEANINGFUL_WORDS:
            return None

        # Take first N meaningful words
        name_words = meaningful[:self.MAX_WORDS_FROM_TRANSCRIPT]
        name = " ".join(name_words)

        # Truncate to max length, preserving whole words
        if len(name) > self.MAX_NAME_LENGTH:
            name = name[:self.MAX_NAME_LENGTH].rsplit(" ", 1)[0]

        # Clean up trailing punctuation
        name = name.rstrip(".,!?;:")

        return name.strip() if name.strip() else None

    def generate_from_llm_output(self, llm_output: str) -> Optional[str]:
        """Extract title from LLM output using common patterns."""
        if not llm_output or not llm_output.strip():
            return None

        # Pattern 1: Explicit title line
        # "Title: Something"
        title_match = re.search(
            r"^(?:title|título|nome):\s*(.+)$",
            llm_output,
            re.IGNORECASE | re.MULTILINE
        )
        if title_match:
            title = title_match.group(1).strip()
            if title:
                return title[:self.MAX_NAME_LENGTH]

        # Pattern 2: Markdown heading
        # "# Something" or "## Something"
        heading_match = re.search(
            r"^#{1,2}\s+(.+)$",
            llm_output,
            re.MULTILINE
        )
        if heading_match:
            title = heading_match.group(1).strip()
            if title:
                return title[:self.MAX_NAME_LENGTH]

        # Pattern 3: First non-empty line (if short enough)
        lines = llm_output.strip().split("\n")
        for line in lines:
            line = line.strip()
            if line and len(line) <= 60:  # Short lines might be titles
                # Skip if it looks like content, not a title
                if not line.endswith((".", ",", ";")):
                    return line[:self.MAX_NAME_LENGTH]
                break

        return None

    def ensure_unique(
        self,
        base_name: str,
        existing_names: set[str]
    ) -> str:
        """Add numeric suffix to ensure uniqueness."""
        if base_name not in existing_names:
            return base_name

        counter = 2
        while f"{base_name} ({counter})" in existing_names:
            counter += 1

        return f"{base_name} ({counter})"


# Singleton instance
_name_generator: Optional[DefaultNameGenerator] = None


def get_name_generator() -> NameGenerator:
    """
    Get the singleton NameGenerator instance.

    Returns:
        The shared NameGenerator instance
    """
    global _name_generator

    if _name_generator is None:
        _name_generator = DefaultNameGenerator()

    return _name_generator
