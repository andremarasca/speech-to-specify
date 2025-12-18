"""File-based artifact storage implementation."""

import json
from pathlib import Path
from datetime import datetime

from src.models import Input, Artifact, Execution
from src.lib.exceptions import PersistenceError


class FileArtifactStore:
    """
    Filesystem-based implementation of ArtifactStore.

    Directory structure:
        {output_dir}/
        └── executions/
            └── {execution_id}/
                ├── input.md
                ├── execution.json
                └── artifacts/
                    ├── 01_constitution.md
                    ├── 02_specification.md
                    └── 03_planning.md
    """

    def __init__(self, output_dir: str):
        """
        Initialize the file artifact store.

        Args:
            output_dir: Base directory for all outputs
        """
        self._output_dir = Path(output_dir)

    def _execution_dir(self, execution_id: str) -> Path:
        """Get the directory for a specific execution."""
        return self._output_dir / "executions" / execution_id

    def _artifacts_dir(self, execution_id: str) -> Path:
        """Get the artifacts directory for a specific execution."""
        return self._execution_dir(execution_id) / "artifacts"

    def _ensure_dir(self, path: Path) -> None:
        """Ensure a directory exists, creating it if necessary."""
        try:
            path.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            raise PersistenceError(
                f"Failed to create directory: {e}", path=str(path), operation="mkdir"
            )

    def save_input(self, execution_id: str, input_data: Input) -> str:
        """Persist input data as a markdown file."""
        exec_dir = self._execution_dir(execution_id)
        self._ensure_dir(exec_dir)

        input_path = exec_dir / "input.md"

        # Create markdown with metadata header
        content = f"""---
id: {input_data.id}
content_hash: {input_data.content_hash}
source_path: {input_data.source_path or "N/A"}
created_at: {input_data.created_at.isoformat()}
---

{input_data.content}
"""

        try:
            input_path.write_text(content, encoding="utf-8")
        except Exception as e:
            raise PersistenceError(
                f"Failed to save input: {e}", path=str(input_path), operation="write"
            )

        return str(input_path)

    def save_artifact(self, execution_id: str, artifact: Artifact) -> str:
        """Persist an artifact as a markdown file."""
        artifacts_dir = self._artifacts_dir(execution_id)
        self._ensure_dir(artifacts_dir)

        filename = artifact.get_filename()
        artifact_path = artifacts_dir / filename

        # Create markdown with metadata header
        header_lines = [
            "---",
            f"id: {artifact.id}",
            f"execution_id: {artifact.execution_id}",
            f"step_number: {artifact.step_number}",
            f"step_name: {artifact.step_name}",
        ]

        if artifact.predecessor_id:
            header_lines.append(f"predecessor_id: {artifact.predecessor_id}")

        header_lines.extend(
            [
                f"created_at: {artifact.created_at.isoformat()}",
                "---",
                "",
            ]
        )

        content = "\n".join(header_lines) + artifact.content

        try:
            artifact_path.write_text(content, encoding="utf-8")
        except Exception as e:
            raise PersistenceError(
                f"Failed to save artifact: {e}", path=str(artifact_path), operation="write"
            )

        return str(artifact_path)

    def save_execution(self, execution: Execution) -> str:
        """Persist execution metadata as JSON."""
        exec_dir = self._execution_dir(execution.id)
        self._ensure_dir(exec_dir)

        exec_path = exec_dir / "execution.json"

        # Convert to dict, handling datetime serialization
        data = execution.model_dump()

        # Serialize datetime fields
        for key in ["started_at", "completed_at"]:
            if data.get(key) and isinstance(data[key], datetime):
                data[key] = data[key].isoformat()

        try:
            exec_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception as e:
            raise PersistenceError(
                f"Failed to save execution: {e}", path=str(exec_path), operation="write"
            )

        return str(exec_path)

    def load_execution(self, execution_id: str) -> Execution | None:
        """Load execution metadata from JSON."""
        exec_path = self._execution_dir(execution_id) / "execution.json"

        if not exec_path.exists():
            return None

        try:
            data = json.loads(exec_path.read_text(encoding="utf-8"))
            return Execution(**data)
        except json.JSONDecodeError as e:
            raise PersistenceError(
                f"Invalid JSON in execution file: {e}", path=str(exec_path), operation="read"
            )
        except Exception as e:
            raise PersistenceError(
                f"Failed to load execution: {e}", path=str(exec_path), operation="read"
            )

    def list_artifacts(self, execution_id: str) -> list[Artifact]:
        """List all artifacts for an execution, ordered by step number."""
        artifacts_dir = self._artifacts_dir(execution_id)

        if not artifacts_dir.exists():
            return []

        artifacts = []

        try:
            for artifact_file in sorted(artifacts_dir.glob("*.md")):
                artifact = self._load_artifact_file(artifact_file)
                if artifact:
                    artifacts.append(artifact)
        except Exception as e:
            raise PersistenceError(
                f"Failed to list artifacts: {e}", path=str(artifacts_dir), operation="list"
            )

        return sorted(artifacts, key=lambda a: a.step_number)

    def _load_artifact_file(self, path: Path) -> Artifact | None:
        """Load an artifact from a markdown file with YAML front matter."""
        try:
            content = path.read_text(encoding="utf-8")

            # Parse YAML front matter
            if not content.startswith("---"):
                return None

            parts = content.split("---", 2)
            if len(parts) < 3:
                return None

            # Parse metadata
            metadata = {}
            for line in parts[1].strip().split("\n"):
                if ":" in line:
                    key, value = line.split(":", 1)
                    metadata[key.strip()] = value.strip()

            # Create artifact
            return Artifact(
                id=metadata.get("id", ""),
                execution_id=metadata.get("execution_id", ""),
                step_number=int(metadata.get("step_number", 0)),
                step_name=metadata.get("step_name", ""),
                predecessor_id=metadata.get("predecessor_id") or None,
                content=parts[2].strip(),
                created_at=metadata.get("created_at", ""),
            )
        except Exception:
            return None
