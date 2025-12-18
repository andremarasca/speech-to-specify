"""File-based log storage implementation."""

import json
from pathlib import Path
from datetime import datetime

from src.models import LLMLog, FailureLog
from src.lib.exceptions import PersistenceError


class FileLogStore:
    """
    Filesystem-based implementation of LogStore.
    
    Directory structure:
        {output_dir}/
        └── executions/
            └── {execution_id}/
                └── logs/
                    ├── llm_traffic.jsonl   (append-only)
                    └── failure.json        (single file)
    """
    
    def __init__(self, output_dir: str):
        """
        Initialize the file log store.
        
        Args:
            output_dir: Base directory for all outputs
        """
        self._output_dir = Path(output_dir)
    
    def _logs_dir(self, execution_id: str) -> Path:
        """Get the logs directory for a specific execution."""
        return self._output_dir / "executions" / execution_id / "logs"
    
    def _ensure_dir(self, path: Path) -> None:
        """Ensure a directory exists, creating it if necessary."""
        try:
            path.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            raise PersistenceError(
                f"Failed to create directory: {e}",
                path=str(path),
                operation="mkdir"
            )
    
    def _serialize_log(self, log: LLMLog) -> str:
        """Serialize an LLMLog to JSON string."""
        data = log.model_dump()
        
        # Serialize datetime fields
        for key in ["prompt_sent_at", "response_received_at"]:
            if data.get(key) and isinstance(data[key], datetime):
                data[key] = data[key].isoformat()
        
        return json.dumps(data, ensure_ascii=False)
    
    def append_llm_log(self, execution_id: str, log: LLMLog) -> None:
        """Append an LLM interaction log entry to JSONL file."""
        logs_dir = self._logs_dir(execution_id)
        self._ensure_dir(logs_dir)
        
        log_path = logs_dir / "llm_traffic.jsonl"
        
        try:
            line = self._serialize_log(log) + "\n"
            
            # Append mode, create if not exists
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(line)
                f.flush()  # Ensure data is written
        except Exception as e:
            raise PersistenceError(
                f"Failed to append LLM log: {e}",
                path=str(log_path),
                operation="append"
            )
    
    def save_failure(self, execution_id: str, failure: FailureLog) -> str:
        """Persist a failure log as JSON."""
        logs_dir = self._logs_dir(execution_id)
        self._ensure_dir(logs_dir)
        
        failure_path = logs_dir / "failure.json"
        
        # Convert to dict
        data = failure.model_dump()
        
        # Serialize datetime
        if data.get("occurred_at") and isinstance(data["occurred_at"], datetime):
            data["occurred_at"] = data["occurred_at"].isoformat()
        
        try:
            failure_path.write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding="utf-8"
            )
        except Exception as e:
            raise PersistenceError(
                f"Failed to save failure log: {e}",
                path=str(failure_path),
                operation="write"
            )
        
        return str(failure_path)
    
    def load_llm_logs(self, execution_id: str) -> list[LLMLog]:
        """Load all LLM logs for an execution in chronological order."""
        log_path = self._logs_dir(execution_id) / "llm_traffic.jsonl"
        
        if not log_path.exists():
            return []
        
        logs = []
        
        try:
            with open(log_path, "r", encoding="utf-8") as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    
                    try:
                        data = json.loads(line)
                        logs.append(LLMLog(**data))
                    except json.JSONDecodeError as e:
                        raise PersistenceError(
                            f"Invalid JSON on line {line_num}: {e}",
                            path=str(log_path),
                            operation="read"
                        )
        except PersistenceError:
            raise
        except Exception as e:
            raise PersistenceError(
                f"Failed to load LLM logs: {e}",
                path=str(log_path),
                operation="read"
            )
        
        return logs
    
    def load_failure(self, execution_id: str) -> FailureLog | None:
        """Load failure log for an execution if it exists."""
        failure_path = self._logs_dir(execution_id) / "failure.json"
        
        if not failure_path.exists():
            return None
        
        try:
            data = json.loads(failure_path.read_text(encoding="utf-8"))
            return FailureLog(**data)
        except json.JSONDecodeError as e:
            raise PersistenceError(
                f"Invalid JSON in failure file: {e}",
                path=str(failure_path),
                operation="read"
            )
        except Exception as e:
            raise PersistenceError(
                f"Failed to load failure log: {e}",
                path=str(failure_path),
                operation="read"
            )
