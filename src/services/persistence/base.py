"""Persistence Protocol definitions."""

from typing import Protocol

from src.models import Input, Artifact, Execution, LLMLog, FailureLog
from src.lib.exceptions import PersistenceError


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
        Load failure log for an execution.

        Args:
            execution_id: UUID of the execution

        Returns:
            FailureLog if exists, None otherwise

        Raises:
            PersistenceError: If read fails
        """
        ...


__all__ = ["ArtifactStore", "LogStore", "PersistenceError"]
