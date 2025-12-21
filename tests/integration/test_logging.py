"""Integration tests for LLM interaction logging."""

import pytest
from pathlib import Path

from src.models import Input
from src.services.orchestrator import NarrativePipeline
from src.services.llm import get_provider
from src.services.persistence import create_artifact_store, create_log_store


class TestLLMLogging:
    """Integration tests for LLM interaction logging (US2)."""

    @pytest.fixture
    def pipeline(self, temp_output_dir):
        """Create a pipeline with mock provider."""
        artifact_store = create_artifact_store(temp_output_dir)
        log_store = create_log_store(temp_output_dir)
        provider = get_provider("mock")

        return NarrativePipeline(
            provider=provider,
            artifact_store=artifact_store,
            log_store=log_store,
        )

    def test_all_llm_calls_logged(self, pipeline, sample_input_content, temp_output_dir):
        """Test that every LLM call produces a log entry."""
        input_data = Input(content=sample_input_content)

        execution = pipeline.execute(input_data)

        # Check logs exist
        logs_dir = Path(temp_output_dir) / "executions" / execution.id / "logs"
        llm_log_path = logs_dir / "llm_traffic.jsonl"

        assert llm_log_path.exists()

        # Count log entries (one per line in JSONL)
        lines = [l for l in llm_log_path.read_text(encoding="utf-8").strip().split("\n") if l]
        assert len(lines) == 5  # One per step

    def test_log_contains_prompt_and_response(
        self, pipeline, sample_input_content, temp_output_dir
    ):
        """Test that logs contain both prompt and response."""
        import json

        input_data = Input(content=sample_input_content)
        execution = pipeline.execute(input_data)

        logs_dir = Path(temp_output_dir) / "executions" / execution.id / "logs"
        llm_log_path = logs_dir / "llm_traffic.jsonl"

        for line in llm_log_path.read_text(encoding="utf-8").strip().split("\n"):
            log_entry = json.loads(line)

            assert "prompt" in log_entry
            assert "response" in log_entry
            assert len(log_entry["prompt"]) > 0
            assert len(log_entry["response"]) > 0

    def test_log_contains_timestamps(self, pipeline, sample_input_content, temp_output_dir):
        """Test that logs contain timestamp information."""
        import json

        input_data = Input(content=sample_input_content)
        execution = pipeline.execute(input_data)

        logs_dir = Path(temp_output_dir) / "executions" / execution.id / "logs"
        llm_log_path = logs_dir / "llm_traffic.jsonl"

        for line in llm_log_path.read_text(encoding="utf-8").strip().split("\n"):
            log_entry = json.loads(line)

            assert "prompt_sent_at" in log_entry
            assert "response_received_at" in log_entry
            assert "latency_ms" in log_entry
            assert log_entry["latency_ms"] >= 0

    def test_log_contains_provider_name(self, pipeline, sample_input_content, temp_output_dir):
        """Test that logs identify the provider."""
        import json

        input_data = Input(content=sample_input_content)
        execution = pipeline.execute(input_data)

        logs_dir = Path(temp_output_dir) / "executions" / execution.id / "logs"
        llm_log_path = logs_dir / "llm_traffic.jsonl"

        for line in llm_log_path.read_text(encoding="utf-8").strip().split("\n"):
            log_entry = json.loads(line)

            assert "provider" in log_entry
            assert log_entry["provider"] == "mock"

    def test_logs_in_chronological_order(self, pipeline, sample_input_content, temp_output_dir):
        """Test that logs are in chronological order."""
        import json

        input_data = Input(content=sample_input_content)
        execution = pipeline.execute(input_data)

        logs_dir = Path(temp_output_dir) / "executions" / execution.id / "logs"
        llm_log_path = logs_dir / "llm_traffic.jsonl"

        step_numbers = []
        for line in llm_log_path.read_text(encoding="utf-8").strip().split("\n"):
            log_entry = json.loads(line)
            step_numbers.append(log_entry["step_number"])

        assert step_numbers == [1, 2, 3, 4, 5]

    def test_log_entries_have_unique_ids(self, pipeline, sample_input_content, temp_output_dir):
        """Test that each log entry has a unique ID."""
        import json

        input_data = Input(content=sample_input_content)
        execution = pipeline.execute(input_data)

        logs_dir = Path(temp_output_dir) / "executions" / execution.id / "logs"
        llm_log_path = logs_dir / "llm_traffic.jsonl"

        ids = []
        for line in llm_log_path.read_text(encoding="utf-8").strip().split("\n"):
            log_entry = json.loads(line)
            ids.append(log_entry["id"])

        assert len(ids) == len(set(ids)), "Log entry IDs must be unique"

    def test_log_store_can_reload_logs(self, pipeline, sample_input_content, temp_output_dir):
        """Test that logs can be reloaded from storage."""
        input_data = Input(content=sample_input_content)
        execution = pipeline.execute(input_data)

        # Use the log store to reload
        log_store = create_log_store(temp_output_dir)
        logs = log_store.load_llm_logs(execution.id)

        assert len(logs) == 5
        assert all(log.execution_id == execution.id for log in logs)
