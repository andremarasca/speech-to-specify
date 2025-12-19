# Persistence Contract

**Interface**: `ArtifactStore`, `LogStore`  
**Purpose**: Abstração para persistência de artefatos e logs

## ArtifactStore Protocol

```python
from typing import Protocol
from src.models import Input, Artifact, Execution

class ArtifactStore(Protocol):
    """
    Contract for artifact persistence implementations.
    
    Responsible for persisting and retrieving inputs, artifacts, and execution metadata.
    Current implementation uses filesystem, but contract allows for future alternatives.
    """
    
    def save_input(self, execution_id: str, input_data: Input) -> str:
        """
        Persist input data for an execution.
        
        Args:
            execution_id: UUID of the execution
            input_data: Input entity to persist
        
        Returns:
            str: Path/location where input was saved
        
        Raises:
            PersistenceError: If save fails
        
        Contract:
            - MUST persist before returning
            - MUST be idempotent (same input, same result)
            - MUST NOT modify input_data
        """
        ...
    
    def save_artifact(self, execution_id: str, artifact: Artifact) -> str:
        """
        Persist an artifact for an execution.
        
        Args:
            execution_id: UUID of the execution
            artifact: Artifact entity to persist
        
        Returns:
            str: Path/location where artifact was saved
        
        Raises:
            PersistenceError: If save fails
        
        Contract:
            - MUST persist before returning
            - MUST create predictable path based on step_number and step_name
            - MUST NOT modify artifact
        """
        ...
    
    def save_execution(self, execution: Execution) -> str:
        """
        Persist or update execution metadata.
        
        Args:
            execution: Execution entity to persist
        
        Returns:
            str: Path/location where metadata was saved
        
        Raises:
            PersistenceError: If save fails
        
        Contract:
            - MUST persist before returning
            - MAY overwrite existing execution metadata
        """
        ...
    
    def load_execution(self, execution_id: str) -> Execution | None:
        """
        Load execution metadata by ID.
        
        Args:
            execution_id: UUID of the execution
        
        Returns:
            Execution if found, None otherwise
        
        Raises:
            PersistenceError: If read fails (not for missing data)
        """
        ...
    
    def list_artifacts(self, execution_id: str) -> list[Artifact]:
        """
        List all artifacts for an execution.
        
        Args:
            execution_id: UUID of the execution
        
        Returns:
            List of artifacts ordered by step_number
        
        Raises:
            PersistenceError: If read fails
        """
        ...
```

## LogStore Protocol

```python
from typing import Protocol
from src.models import LLMLog, FailureLog

class LogStore(Protocol):
    """
    Contract for log persistence implementations.
    
    Responsible for append-only logging of LLM interactions and failures.
    """
    
    def append_llm_log(self, execution_id: str, log: LLMLog) -> None:
        """
        Append an LLM interaction log entry.
        
        Args:
            execution_id: UUID of the execution
            log: LLM log entry to append
        
        Raises:
            PersistenceError: If append fails
        
        Contract:
            - MUST append, never overwrite
            - MUST flush/sync before returning
            - MUST maintain chronological order
        """
        ...
    
    def save_failure(self, execution_id: str, failure: FailureLog) -> str:
        """
        Persist a failure log.
        
        Args:
            execution_id: UUID of the execution
            failure: Failure log to persist
        
        Returns:
            str: Path/location where failure was saved
        
        Raises:
            PersistenceError: If save fails
        
        Contract:
            - MUST persist before returning
            - SHOULD be called at most once per execution
        """
        ...
    
    def load_llm_logs(self, execution_id: str) -> list[LLMLog]:
        """
        Load all LLM logs for an execution.
        
        Args:
            execution_id: UUID of the execution
        
        Returns:
            List of LLM logs in chronological order
        
        Raises:
            PersistenceError: If read fails
        """
        ...
    
    def load_failure(self, execution_id: str) -> FailureLog | None:
        """
        Load failure log for an execution if exists.
        
        Args:
            execution_id: UUID of the execution
        
        Returns:
            FailureLog if exists, None otherwise
        
        Raises:
            PersistenceError: If read fails (not for missing data)
        """
        ...
```

## Error Contract

```python
class PersistenceError(Exception):
    """
    Exception for persistence operations.
    
    Attributes:
        operation: Name of the operation that failed
        path: Path/location involved (if applicable)
        message: Human-readable error description
    """
    
    def __init__(
        self,
        operation: str,
        message: str,
        path: str | None = None
    ):
        self.operation = operation
        self.path = path
        self.message = message
        super().__init__(f"[{operation}] {message}" + (f" at {path}" if path else ""))
```

## Filesystem Implementation

### Directory Structure

```
{output_dir}/
└── executions/
    └── {execution_id}/
        ├── input.md                     # Input.content as markdown
        ├── execution.json               # Execution metadata
        ├── artifacts/
        │   └── {step:02d}_{name}.md     # Artifact.content as markdown
        └── logs/
            ├── llm_traffic.jsonl        # LLMLog entries, one per line
            └── failure.json             # FailureLog if exists
```

### File Formats

**execution.json**:
```json
{
  "id": "uuid",
  "input_id": "uuid",
  "status": "completed|in_progress|failed",
  "started_at": "2025-12-18T10:00:00Z",
  "completed_at": "2025-12-18T10:01:30Z",
  "current_step": null,
  "total_steps": 3,
  "error_message": null
}
```

**llm_traffic.jsonl** (one entry):
```json
{"id":"uuid","execution_id":"uuid","step_number":1,"provider":"openai","prompt":"...","response":"...","prompt_sent_at":"2025-12-18T10:00:05Z","response_received_at":"2025-12-18T10:00:15Z","latency_ms":10000}
```

**failure.json**:
```json
{
  "id": "uuid",
  "execution_id": "uuid",
  "failed_step": 2,
  "error_type": "LLMError",
  "error_message": "Rate limit exceeded",
  "stack_trace": "...",
  "system_state": {"artifacts_completed": 1},
  "occurred_at": "2025-12-18T10:00:20Z"
}
```

## Validation

Contract tests MUST verify:

1. `save_input` creates readable file
2. `save_artifact` creates file with correct naming
3. `save_execution` creates valid JSON
4. `append_llm_log` appends (not overwrites)
5. `load_*` methods return correct data after save
6. Operations are idempotent where specified
7. PersistenceError raised on I/O failures

## Atomicity Guarantees

- Single file operations are atomic (write to temp, rename)
- No cross-file transactions required
- Partial failure leaves valid partial state
- Directory creation is idempotent
