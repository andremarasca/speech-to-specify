# Contract: Downstream Processor

**Module**: `src/services/session/processor.py`  
**Purpose**: Integrate transcribed sessions with existing narrative pipeline

## Interface

### DownstreamProcessor

```python
from abc import ABC, abstractmethod
from pathlib import Path
from dataclasses import dataclass

@dataclass
class ProcessingResult:
    success: bool
    output_files: list[str]  # Relative paths within output/
    error_message: Optional[str] = None
    exit_code: int = 0

class DownstreamProcessor(ABC):
    @abstractmethod
    def consolidate_transcripts(self, session_path: Path) -> Path:
        """
        Consolidate all transcript files into single input.txt.
        Returns path to consolidated file.
        """
        pass
    
    @abstractmethod
    def process(self, session_path: Path) -> ProcessingResult:
        """
        Invoke downstream narrative pipeline.
        1. Consolidate transcripts → process/input.txt
        2. Call narrative pipeline with input.txt
        3. Results written to process/output/
        """
        pass
    
    @abstractmethod
    def list_outputs(self, session_path: Path) -> list[Path]:
        """List all files in process/output/."""
        pass
```

## Integration with Existing Pipeline

### Invocation

```python
from argparse import Namespace
from src.cli.main import run

def invoke_narrative_pipeline(input_file: Path, output_dir: Path) -> int:
    args = Namespace(
        input_file=str(input_file),
        output_dir=str(output_dir),
        provider=None,  # Uses default from config
        verbose=False
    )
    return run(args)
```

### File Layout

```text
{session}/
└── process/
    ├── input.txt          # Consolidated transcripts (INPUT)
    └── output/            # Narrative pipeline results (OUTPUT)
        ├── executions/
        │   └── {timestamp}/
        │       ├── execution.json
        │       ├── input.md
        │       └── artifacts/
        │           ├── 01_constitution.md
        │           ├── 02_specification.md
        │           ├── 03_planning.md
        │           └── 04_tasks.md
        └── ...
```

## Transcript Consolidation

### Format

```text
# Voice Session: {session_id}
# Recorded: {created_at}
# Total audios: {count}

---

## Recording 1 ({timestamp})

{transcript_001}

---

## Recording 2 ({timestamp})

{transcript_002}

---

[... additional recordings ...]
```

### Rules

- Transcripts ordered by sequence number (ascending)
- Empty transcripts marked: `[Transcription failed - see error log]`
- Timestamps from `received_at` in AudioEntry
- UTF-8 encoding

## Configuration

```python
class ProcessorConfig:
    default_provider: str = "deepseek"  # DEFAULT_LLM_PROVIDER env var
    verbose: bool = False
```

## Error Handling

| Error | Handling |
|-------|----------|
| No transcripts found | Return `ProcessingResult(success=False, error_message="No transcripts")` |
| Narrative pipeline fails | Return with exit_code and error_message |
| Output dir not writable | Raise `PermissionError` |

## Usage Pattern

```python
# After session reaches TRANSCRIBED state
processor = DownstreamProcessor(config)
result = processor.process(session_path)

if result.success:
    session_manager.transition_state(session_id, SessionState.PROCESSED)
else:
    session_manager.add_error(session_id, ErrorEntry(
        operation="process",
        message=result.error_message,
        recoverable=True  # User can retry /process
    ))
```

## Testing Contract

```python
def test_downstream_processor_contract():
    # GIVEN a session with transcripts
    session_path = create_test_session_with_transcripts()
    processor = get_downstream_processor()
    
    # WHEN processing the session
    result = processor.process(session_path)
    
    # THEN output files are created
    assert result.success
    assert len(result.output_files) > 0
    assert (session_path / "process" / "output").exists()
```

## Communication Contract

The downstream processor communicates with the narrative pipeline exclusively via:

1. **Input**: Single text file at `process/input.txt`
2. **Output**: Artifacts in `process/output/` directory
3. **Exit Code**: 0 = success, non-zero = failure

No other communication mechanism is allowed (no shared memory, no message queues, no environment variable mutation).
