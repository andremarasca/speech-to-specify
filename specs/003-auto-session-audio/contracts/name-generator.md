# Contract: Name Generator

**Module**: `src/services/session/name_generator.py`  
**Feature**: 003-auto-session-audio

## Purpose

Generate human-readable, intelligible names for sessions based on their content or creation context. Names follow a cascading fallback strategy to ensure sessions always have meaningful identifiers.

## Interface

```python
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional
from src.models.session import NameSource


class NameGenerator(ABC):
    """Contract for generating intelligible session names."""

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
```

## Behavior Specification

### Fallback Name Generation

| Input | Output |
|-------|--------|
| `2025-12-18T10:30:00` | `"Áudio de 18 de Dezembro"` |
| `2025-01-01T00:00:00` | `"Áudio de 1 de Janeiro"` |
| `2025-06-15T23:59:59` | `"Áudio de 15 de Junho"` |

### Transcript Name Extraction

| Input Transcript | Output |
|-----------------|--------|
| `"Então, sobre o relatório mensal de vendas..."` | `"relatório mensal de vendas"` |
| `"Um, é, tipo, preciso falar sobre o projeto"` | `"preciso falar projeto"` |
| `"Ok"` | `None` (too short) |
| `""` | `None` (empty) |

**Filler words to exclude** (Portuguese):
- `um`, `uma`, `é`, `eh`, `então`, `tipo`, `né`, `ok`, `bom`, `olha`

### LLM Title Extraction

Searches for patterns:
1. Markdown heading: `# Title` or `## Title`
2. Bold title: `**Title**` at start of line
3. First non-empty line if under 50 chars

### Uniqueness Enforcement

| Base Name | Existing Names | Output |
|-----------|----------------|--------|
| `"relatório"` | `{}` | `"relatório"` |
| `"relatório"` | `{"relatório"}` | `"relatório (2)"` |
| `"relatório"` | `{"relatório", "relatório (2)"}` | `"relatório (3)"` |

## Error Handling

- `generate_fallback_name`: Never fails (timestamp always valid)
- `generate_from_transcript`: Returns `None` on failure (not exception)
- `generate_from_llm_output`: Returns `None` on failure (not exception)
- `ensure_unique`: Never fails (infinite counter is theoretical)

## Testing Requirements

### Contract Tests

```python
def test_fallback_name_format():
    """Name must be in Portuguese locale format."""
    
def test_fallback_name_all_months():
    """All 12 months must produce correct Portuguese names."""

def test_transcript_filters_fillers():
    """Filler words must be excluded from name."""

def test_transcript_too_short_returns_none():
    """Transcripts under 3 meaningful words return None."""

def test_uniqueness_adds_suffix():
    """Collision adds (2), (3), etc."""

def test_uniqueness_preserves_unique():
    """Non-colliding names unchanged."""
```
