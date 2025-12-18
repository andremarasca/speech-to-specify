"""Integration tests for failure preservation (US3)."""

import pytest
from pathlib import Path

from src.models import Input, ExecutionStatus
from src.services.orchestrator import NarrativePipeline
from src.services.llm.mock import MockProvider
from src.services.persistence import create_artifact_store, create_log_store
from src.lib.exceptions import LLMError


class TestFailurePreservation:
    """Integration tests for preserving artifacts on failure (US3)."""
    
    @pytest.fixture
    def failing_provider(self):
        """Create a mock provider that fails on step 2."""
        return MockProvider(fail_on_prompts=["specification"])
    
    @pytest.fixture
    def pipeline_with_failure(self, temp_output_dir, failing_provider):
        """Create a pipeline that will fail on step 2."""
        artifact_store = create_artifact_store(temp_output_dir)
        log_store = create_log_store(temp_output_dir)
        
        return NarrativePipeline(
            provider=failing_provider,
            artifact_store=artifact_store,
            log_store=log_store,
        )
    
    def test_partial_artifacts_preserved_on_failure(
        self, pipeline_with_failure, sample_input_content, temp_output_dir
    ):
        """Test that artifacts before failure are preserved."""
        input_data = Input(content=sample_input_content)
        
        # Execute should raise but preserve state
        with pytest.raises(LLMError):
            pipeline_with_failure.execute(input_data)
        
        # Check that artifact from step 1 exists
        exec_id = pipeline_with_failure._current_execution.id
        artifacts_dir = Path(temp_output_dir) / "executions" / exec_id / "artifacts"
        
        artifact_files = list(artifacts_dir.glob("*.md"))
        assert len(artifact_files) == 1  # Only step 1 succeeded
        assert "01_constitution" in artifact_files[0].name
    
    def test_failure_log_created(
        self, pipeline_with_failure, sample_input_content, temp_output_dir
    ):
        """Test that failure log is created on error."""
        input_data = Input(content=sample_input_content)
        
        with pytest.raises(LLMError):
            pipeline_with_failure.execute(input_data)
        
        exec_id = pipeline_with_failure._current_execution.id
        failure_path = Path(temp_output_dir) / "executions" / exec_id / "logs" / "failure.json"
        
        assert failure_path.exists()
    
    def test_execution_marked_failed(
        self, pipeline_with_failure, sample_input_content, temp_output_dir
    ):
        """Test that execution status is marked as failed."""
        input_data = Input(content=sample_input_content)
        
        with pytest.raises(LLMError):
            pipeline_with_failure.execute(input_data)
        
        execution = pipeline_with_failure._current_execution
        assert execution.status == ExecutionStatus.FAILED
        assert execution.error_message is not None
    
    def test_failure_log_contains_step_info(
        self, pipeline_with_failure, sample_input_content, temp_output_dir
    ):
        """Test that failure log identifies the failed step."""
        import json
        
        input_data = Input(content=sample_input_content)
        
        with pytest.raises(LLMError):
            pipeline_with_failure.execute(input_data)
        
        exec_id = pipeline_with_failure._current_execution.id
        failure_path = Path(temp_output_dir) / "executions" / exec_id / "logs" / "failure.json"
        
        failure_data = json.loads(failure_path.read_text())
        assert failure_data["failed_step"] == 2
        assert "LLMError" in failure_data["error_type"]
    
    def test_llm_logs_before_failure_preserved(
        self, pipeline_with_failure, sample_input_content, temp_output_dir
    ):
        """Test that LLM logs from successful steps are preserved."""
        input_data = Input(content=sample_input_content)
        
        with pytest.raises(LLMError):
            pipeline_with_failure.execute(input_data)
        
        exec_id = pipeline_with_failure._current_execution.id
        llm_log_path = Path(temp_output_dir) / "executions" / exec_id / "logs" / "llm_traffic.jsonl"
        
        assert llm_log_path.exists()
        lines = [l for l in llm_log_path.read_text().strip().split("\n") if l]
        assert len(lines) >= 1  # At least step 1's log
