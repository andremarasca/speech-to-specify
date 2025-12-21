# Contract: ContextBuilder

**Component**: `src/services/llm/context_builder.py`  
**Purpose**: Build context string from session transcripts and LLM responses

## Interface

```python
from dataclasses import dataclass
from src.models.session import Session

@dataclass
class BuiltContext:
    content: str                    # Formatted context string
    transcript_count: int           # Number of transcripts included
    llm_response_count: int         # Number of LLM responses included
    include_llm_history: bool       # Whether LLM history was included
    total_tokens_estimate: int      # Rough token estimate

class ContextBuilder:
    """Builds context string from session entries."""
    
    def __init__(self, session_dir: Path):
        """Initialize with session directory for file access."""
    
    def build(self, session: Session, include_llm_history: bool | None = None) -> BuiltContext:
        """
        Build context from session entries.
        
        Args:
            session: Session containing audio_entries and llm_entries
            include_llm_history: Override session preference (None = use session.ui_preferences)
            
        Returns:
            BuiltContext with formatted content and metadata
        """
    
    def estimate_tokens(self, text: str) -> int:
        """Rough token estimate (chars / 4)."""
```

## Context Format

```text
[TRANSCRIÇÃO 1 - 2025-12-20 10:30:00]
{transcript content}

[ORÁCULO: Cético - 2025-12-20 10:32:15]
{llm response}

[TRANSCRIÇÃO 2 - 2025-12-20 10:35:00]
{transcript content}
```

## Behavior Contracts

### BC-CB-001: Chronological Ordering

**Given** session with entries: transcript_1 (10:30), llm_1 (10:32), transcript_2 (10:35)  
**When** `build()` is called with `include_llm_history=True`  
**Then** context order is: transcript_1, llm_1, transcript_2

### BC-CB-002: Transcripts Only Mode

**Given** session with 2 transcripts and 1 LLM response  
**When** `build()` is called with `include_llm_history=False`  
**Then** only transcripts appear in context (LLM response excluded)

### BC-CB-003: Session Preference Respected

**Given** session with `ui_preferences.include_llm_history=False`  
**When** `build()` is called with `include_llm_history=None`  
**Then** LLM responses are excluded (session preference used)

### BC-CB-004: Override Preference

**Given** session with `ui_preferences.include_llm_history=False`  
**When** `build()` is called with `include_llm_history=True`  
**Then** LLM responses are included (override takes precedence)

### BC-CB-005: Empty Session Handling

**Given** session with no transcripts and no LLM responses  
**When** `build()` is called  
**Then** BuiltContext has empty `content` and counts of 0

### BC-CB-006: Missing Transcript File

**Given** session with AudioEntry pointing to non-existent transcript file  
**When** `build()` is called  
**Then** placeholder `[Transcrição indisponível]` is used, warning logged

### BC-CB-007: Missing LLM Response File

**Given** session with LlmEntry pointing to non-existent response file  
**When** `build()` is called with `include_llm_history=True`  
**Then** placeholder `[Resposta indisponível]` is used, warning logged

### BC-CB-008: Oracle Name in Delimiter

**Given** LlmEntry with `oracle_name="Visionário"`  
**When** entry is formatted in context  
**Then** delimiter includes oracle name: `[ORÁCULO: Visionário - timestamp]`

### BC-CB-009: Token Estimation

**Given** context with 4000 characters  
**When** `estimate_tokens()` is called  
**Then** returns approximately 1000 (chars / 4 heuristic)

## Error Conditions

| Condition | Response | Log Level |
|-----------|----------|-----------|
| Transcript file missing | Placeholder text | WARNING |
| LLM response file missing | Placeholder text | WARNING |
| File read permission denied | Placeholder text | ERROR |

## Test Requirements

- Unit tests for chronological sorting
- Unit tests for format string generation
- Unit tests for token estimation
- Contract tests verifying all BC-CB-* behaviors
