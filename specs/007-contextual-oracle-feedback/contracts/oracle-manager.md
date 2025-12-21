# Contract: OracleManager

**Component**: `src/services/oracle/manager.py`  
**Purpose**: Load, validate, and manage oracle personalities from filesystem

## Interface

```python
from pathlib import Path
from dataclasses import dataclass

@dataclass
class Oracle:
    id: str                    # 8-char hash
    name: str                  # Display name from H1
    file_path: Path            # Absolute path
    prompt_content: str        # Full markdown content
    placeholder: str           # Context placeholder

class OracleManager:
    """Manages oracle personality files with caching."""
    
    def __init__(self, oracles_dir: Path, placeholder: str = "{{CONTEXT}}", cache_ttl: int = 10):
        """Initialize manager with configuration."""
        
    def list_oracles(self) -> list[Oracle]:
        """Return all valid oracles, refreshing cache if expired."""
        
    def get_oracle(self, oracle_id: str) -> Oracle | None:
        """Get oracle by ID, or None if not found."""
        
    def get_oracle_by_name(self, name: str) -> Oracle | None:
        """Get oracle by display name (case-insensitive)."""
        
    def refresh(self) -> None:
        """Force cache refresh."""
        
    def is_valid(self, file_path: Path) -> bool:
        """Check if file is a valid oracle (readable markdown with title)."""
```

## Behavior Contracts

### BC-OM-001: Cache Expiration

**Given** cache TTL is 10 seconds  
**When** `list_oracles()` is called twice within 10 seconds  
**Then** filesystem is scanned only once (cached result returned)

### BC-OM-002: New File Detection

**Given** a new `.md` file is added to oracles directory  
**When** `list_oracles()` is called after cache expires  
**Then** the new oracle appears in the list

### BC-OM-003: File Removal Detection

**Given** an existing oracle file is deleted  
**When** `list_oracles()` is called after cache expires  
**Then** the removed oracle no longer appears in the list

### BC-OM-004: Invalid File Handling

**Given** a malformed markdown file (no H1 title) exists in oracles directory  
**When** `list_oracles()` is called  
**Then** the file is skipped with warning log, other oracles load normally

### BC-OM-005: Empty Directory Handling

**Given** oracles directory exists but is empty  
**When** `list_oracles()` is called  
**Then** empty list is returned (no error)

### BC-OM-006: Directory Not Found Handling

**Given** oracles directory does not exist  
**When** OracleManager is initialized  
**Then** warning is logged, `list_oracles()` returns empty list

### BC-OM-007: ID Generation Determinism

**Given** oracle file at path `/prompts/oracles/cetico.md`  
**When** oracle is loaded multiple times  
**Then** the `id` is always the same 8-character hash

### BC-OM-008: Title Extraction

**Given** oracle file with first line `# Cético Radical`  
**When** oracle is loaded  
**Then** `name` is "Cético Radical" (stripped, no `#`)

### BC-OM-009: Title Fallback

**Given** oracle file `cetico.md` with no H1 heading  
**When** oracle is loaded  
**Then** `name` is "cetico" (filename without extension)

## Error Conditions

| Condition | Response | Log Level |
|-----------|----------|-----------|
| Directory not found | Empty list | WARNING |
| File not readable | Skip file | WARNING |
| File has no content | Skip file | WARNING |
| Placeholder not in content | Append context at end | INFO |

## Test Requirements

- Unit tests for title extraction regex
- Unit tests for ID generation determinism
- Integration tests for file system operations (add/remove files)
- Contract tests verifying all BC-OM-* behaviors
