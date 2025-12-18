"""Contract tests for Persistence Protocol compliance."""

import pytest
from datetime import datetime, timezone

from src.models import Input, Artifact, Execution, ExecutionStatus, LLMLog, FailureLog
from src.services.persistence import (
    ArtifactStore,
    LogStore,
    FileArtifactStore,
    FileLogStore,
    create_artifact_store,
    create_log_store,
)
from src.lib.exceptions import PersistenceError


class TestArtifactStoreContract:
    """Contract tests for ArtifactStore implementations."""

    @pytest.fixture
    def store(self, temp_output_dir) -> ArtifactStore:
        """Create a FileArtifactStore for testing."""
        return FileArtifactStore(temp_output_dir)

    @pytest.fixture
    def sample_input(self) -> Input:
        """Create a sample input for testing."""
        return Input(content="Sample chaotic text for testing")

    @pytest.fixture
    def sample_execution(self, sample_input) -> Execution:
        """Create a sample execution for testing."""
        return Execution(input_id=sample_input.id)

    @pytest.fixture
    def sample_artifact(self, sample_execution) -> Artifact:
        """Create a sample artifact for testing."""
        return Artifact(
            execution_id=sample_execution.id,
            step_number=1,
            step_name="constitution",
            content="# Constitution\n\nTest content",
        )

    def test_save_input_returns_path(self, store, sample_input, sample_execution):
        """Test that save_input returns a path."""
        path = store.save_input(sample_execution.id, sample_input)

        assert isinstance(path, str)
        assert len(path) > 0
        assert "input.md" in path

    def test_save_input_is_idempotent(self, store, sample_input, sample_execution):
        """Test that saving the same input twice returns same path."""
        path1 = store.save_input(sample_execution.id, sample_input)
        path2 = store.save_input(sample_execution.id, sample_input)

        assert path1 == path2

    def test_save_artifact_returns_path(self, store, sample_artifact):
        """Test that save_artifact returns a path."""
        path = store.save_artifact(sample_artifact.execution_id, sample_artifact)

        assert isinstance(path, str)
        assert "01_constitution.md" in path

    def test_save_artifact_predictable_path(self, store, sample_execution):
        """Test that artifact path is based on step_number and step_name."""
        artifact1 = Artifact(
            execution_id=sample_execution.id,
            step_number=1,
            step_name="constitution",
            content="Content 1",
        )
        artifact2 = Artifact(
            execution_id=sample_execution.id,
            step_number=2,
            step_name="specification",
            content="Content 2",
            predecessor_id=artifact1.id,
        )

        path1 = store.save_artifact(sample_execution.id, artifact1)
        path2 = store.save_artifact(sample_execution.id, artifact2)

        assert "01_constitution" in path1
        assert "02_specification" in path2

    def test_save_execution_returns_path(self, store, sample_execution):
        """Test that save_execution returns a path."""
        path = store.save_execution(sample_execution)

        assert isinstance(path, str)
        assert "execution.json" in path

    def test_load_execution_returns_execution(self, store, sample_execution):
        """Test that load_execution returns saved execution."""
        store.save_execution(sample_execution)

        loaded = store.load_execution(sample_execution.id)

        assert loaded is not None
        assert loaded.id == sample_execution.id
        assert loaded.input_id == sample_execution.input_id

    def test_load_execution_not_found_returns_none(self, store):
        """Test that load_execution returns None for missing execution."""
        loaded = store.load_execution("nonexistent-id")

        assert loaded is None

    def test_list_artifacts_empty(self, store, sample_execution):
        """Test that list_artifacts returns empty list when no artifacts."""
        artifacts = store.list_artifacts(sample_execution.id)

        assert artifacts == []

    def test_list_artifacts_ordered_by_step(self, store, sample_execution):
        """Test that list_artifacts returns artifacts ordered by step_number."""
        # Save artifacts out of order
        artifact2 = Artifact(
            execution_id=sample_execution.id,
            step_number=2,
            step_name="specification",
            content="Spec content",
        )
        artifact1 = Artifact(
            execution_id=sample_execution.id,
            step_number=1,
            step_name="constitution",
            content="Constitution content",
        )

        store.save_artifact(sample_execution.id, artifact2)
        store.save_artifact(sample_execution.id, artifact1)

        artifacts = store.list_artifacts(sample_execution.id)

        assert len(artifacts) == 2
        assert artifacts[0].step_number == 1
        assert artifacts[1].step_number == 2


class TestLogStoreContract:
    """Contract tests for LogStore implementations."""

    @pytest.fixture
    def store(self, temp_output_dir) -> LogStore:
        """Create a FileLogStore for testing."""
        return FileLogStore(temp_output_dir)

    @pytest.fixture
    def execution_id(self) -> str:
        """Create a test execution ID."""
        from src.lib.timestamps import generate_id

        return generate_id()

    @pytest.fixture
    def sample_llm_log(self, execution_id) -> LLMLog:
        """Create a sample LLM log for testing."""
        now = datetime.now(timezone.utc)
        return LLMLog(
            execution_id=execution_id,
            step_number=1,
            provider="mock",
            prompt="Test prompt",
            response="Test response",
            prompt_sent_at=now,
            response_received_at=now,
            latency_ms=100,
        )

    @pytest.fixture
    def sample_failure(self, execution_id) -> FailureLog:
        """Create a sample failure log for testing."""
        return FailureLog(
            execution_id=execution_id,
            failed_step=2,
            error_type="TestError",
            error_message="Test failure message",
        )

    def test_append_llm_log_no_error(self, store, execution_id, sample_llm_log):
        """Test that append_llm_log completes without error."""
        # Should not raise
        store.append_llm_log(execution_id, sample_llm_log)

    def test_append_llm_log_is_append_only(self, store, execution_id):
        """Test that multiple appends accumulate."""
        now = datetime.now(timezone.utc)

        log1 = LLMLog(
            execution_id=execution_id,
            step_number=1,
            provider="mock",
            prompt="Prompt 1",
            response="Response 1",
            prompt_sent_at=now,
            response_received_at=now,
            latency_ms=100,
        )
        log2 = LLMLog(
            execution_id=execution_id,
            step_number=2,
            provider="mock",
            prompt="Prompt 2",
            response="Response 2",
            prompt_sent_at=now,
            response_received_at=now,
            latency_ms=200,
        )

        store.append_llm_log(execution_id, log1)
        store.append_llm_log(execution_id, log2)

        logs = store.load_llm_logs(execution_id)

        assert len(logs) == 2

    def test_load_llm_logs_chronological(self, store, execution_id):
        """Test that logs are returned in chronological order."""
        now = datetime.now(timezone.utc)

        for i in range(3):
            log = LLMLog(
                execution_id=execution_id,
                step_number=i + 1,
                provider="mock",
                prompt=f"Prompt {i}",
                response=f"Response {i}",
                prompt_sent_at=now,
                response_received_at=now,
                latency_ms=100,
            )
            store.append_llm_log(execution_id, log)

        logs = store.load_llm_logs(execution_id)

        assert len(logs) == 3
        assert logs[0].step_number == 1
        assert logs[1].step_number == 2
        assert logs[2].step_number == 3

    def test_load_llm_logs_empty(self, store, execution_id):
        """Test that load_llm_logs returns empty list when no logs."""
        logs = store.load_llm_logs(execution_id)

        assert logs == []

    def test_save_failure_returns_path(self, store, execution_id, sample_failure):
        """Test that save_failure returns a path."""
        path = store.save_failure(execution_id, sample_failure)

        assert isinstance(path, str)
        assert "failure.json" in path

    def test_load_failure_returns_saved(self, store, execution_id, sample_failure):
        """Test that load_failure returns saved failure."""
        store.save_failure(execution_id, sample_failure)

        loaded = store.load_failure(execution_id)

        assert loaded is not None
        assert loaded.error_type == sample_failure.error_type
        assert loaded.error_message == sample_failure.error_message

    def test_load_failure_not_found_returns_none(self, store, execution_id):
        """Test that load_failure returns None when no failure."""
        loaded = store.load_failure(execution_id)

        assert loaded is None


class TestPersistenceFactory:
    """Tests for persistence factory functions."""

    def test_create_artifact_store(self, temp_output_dir):
        """Test creating artifact store from factory."""
        store = create_artifact_store(temp_output_dir)

        assert isinstance(store, FileArtifactStore)

    def test_create_log_store(self, temp_output_dir):
        """Test creating log store from factory."""
        store = create_log_store(temp_output_dir)

        assert isinstance(store, FileLogStore)
