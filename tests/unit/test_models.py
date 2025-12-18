"""Unit tests for domain models."""

import pytest
from datetime import datetime, timezone

from src.models import Input, Artifact, Execution, ExecutionStatus, LLMLog, FailureLog
from src.lib.exceptions import ValidationError


class TestInput:
    """Tests for the Input model."""
    
    def test_create_valid_input(self):
        """Test creating a valid input."""
        input_data = Input(content="Some chaotic text here")
        
        assert input_data.content == "Some chaotic text here"
        assert input_data.id  # UUID should be generated
        assert input_data.content_hash  # Hash should be computed
        assert input_data.created_at  # Timestamp should be set
    
    def test_empty_content_rejected(self):
        """Test that empty content is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            Input(content="")
        
        assert "empty" in str(exc_info.value).lower()
    
    def test_whitespace_only_rejected(self):
        """Test that whitespace-only content is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            Input(content="   \n\t  ")
        
        assert "empty" in str(exc_info.value).lower()
    
    def test_content_hash_computed(self):
        """Test that content hash is automatically computed."""
        input1 = Input(content="test content")
        input2 = Input(content="test content")
        input3 = Input(content="different content")
        
        assert input1.content_hash == input2.content_hash
        assert input1.content_hash != input3.content_hash
    
    def test_verify_integrity(self):
        """Test integrity verification."""
        input_data = Input(content="test content")
        
        assert input_data.verify_integrity() is True
    
    def test_immutability(self):
        """Test that Input is immutable."""
        input_data = Input(content="test")
        
        with pytest.raises(Exception):  # Pydantic raises ValidationError for frozen models
            input_data.content = "modified"


class TestArtifact:
    """Tests for the Artifact model."""
    
    def test_create_valid_artifact(self):
        """Test creating a valid artifact."""
        artifact = Artifact(
            execution_id="exec-123",
            step_number=1,
            step_name="constitution",
            content="# Constitution\n\nSome content"
        )
        
        assert artifact.step_number == 1
        assert artifact.step_name == "constitution"
        assert artifact.predecessor_id is None
    
    def test_invalid_step_name_rejected(self):
        """Test that invalid step names are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            Artifact(
                execution_id="exec-123",
                step_number=1,
                step_name="invalid_step",
                content="content"
            )
        
        assert "invalid" in str(exc_info.value).lower()
    
    def test_empty_content_rejected(self):
        """Test that empty content is rejected."""
        with pytest.raises(ValidationError):
            Artifact(
                execution_id="exec-123",
                step_number=1,
                step_name="constitution",
                content=""
            )
    
    def test_get_filename(self):
        """Test filename generation."""
        artifact = Artifact(
            execution_id="exec-123",
            step_number=2,
            step_name="specification",
            content="content"
        )
        
        assert artifact.get_filename() == "02_specification.md"
    
    def test_step_number_must_be_positive(self):
        """Test that step_number must be >= 1."""
        with pytest.raises(Exception):
            Artifact(
                execution_id="exec-123",
                step_number=0,
                step_name="constitution",
                content="content"
            )


class TestExecution:
    """Tests for the Execution model."""
    
    def test_create_default_execution(self):
        """Test creating an execution with defaults."""
        execution = Execution(input_id="input-123")
        
        assert execution.status == ExecutionStatus.IN_PROGRESS
        assert execution.current_step == 1
        assert execution.total_steps == 3
        assert execution.completed_at is None
        assert execution.error_message is None
    
    def test_mark_step_complete(self):
        """Test marking a step as complete."""
        execution = Execution(input_id="input-123")
        
        updated = execution.mark_step_complete(1)
        
        assert updated.current_step == 2
        assert updated.status == ExecutionStatus.IN_PROGRESS
    
    def test_mark_final_step_complete(self):
        """Test marking the final step as complete."""
        execution = Execution(input_id="input-123", current_step=3)
        
        updated = execution.mark_step_complete(3)
        
        assert updated.status == ExecutionStatus.COMPLETED
        assert updated.completed_at is not None
        assert updated.current_step is None
    
    def test_mark_failed(self):
        """Test marking execution as failed."""
        execution = Execution(input_id="input-123", current_step=2)
        
        failed = execution.mark_failed("LLM error occurred", failed_step=2)
        
        assert failed.status == ExecutionStatus.FAILED
        assert failed.error_message == "LLM error occurred"
        assert failed.completed_at is not None
    
    def test_failed_requires_error_message(self):
        """Test that failed status requires error_message."""
        with pytest.raises(ValidationError):
            Execution(
                input_id="input-123",
                status=ExecutionStatus.FAILED,
                error_message=None
            )
    
    def test_status_properties(self):
        """Test status helper properties."""
        running = Execution(input_id="input-123")
        completed = running.mark_step_complete(3)
        failed = running.mark_failed("error")
        
        assert running.is_running is True
        assert running.is_complete is False
        assert running.is_failed is False
        
        assert completed.is_running is False
        assert completed.is_complete is True
        assert completed.is_failed is False
        
        assert failed.is_running is False
        assert failed.is_complete is False
        assert failed.is_failed is True


class TestLLMLog:
    """Tests for the LLMLog model."""
    
    def test_create_with_factory(self):
        """Test creating LLMLog with create() factory."""
        prompt_time = datetime.now(timezone.utc)
        response_time = datetime.now(timezone.utc)
        
        log = LLMLog.create(
            execution_id="exec-123",
            step_number=1,
            provider="openai",
            prompt="Test prompt",
            response="Test response",
            prompt_sent_at=prompt_time,
            response_received_at=response_time,
        )
        
        assert log.prompt == "Test prompt"
        assert log.response == "Test response"
        assert log.latency_ms >= 0
    
    def test_empty_prompt_rejected(self):
        """Test that empty prompt is rejected."""
        with pytest.raises(ValidationError):
            LLMLog(
                execution_id="exec-123",
                step_number=1,
                provider="openai",
                prompt="",
                response="response",
                prompt_sent_at=datetime.now(timezone.utc),
                response_received_at=datetime.now(timezone.utc),
                latency_ms=100,
            )


class TestFailureLog:
    """Tests for the FailureLog model."""
    
    def test_create_from_exception(self):
        """Test creating FailureLog from exception."""
        try:
            raise ValueError("Test error")
        except Exception as e:
            failure = FailureLog.from_exception(
                execution_id="exec-123",
                failed_step=2,
                exception=e,
            )
        
        assert failure.error_type == "ValueError"
        assert "Test error" in failure.error_message
        assert failure.stack_trace is not None
        assert failure.failed_step == 2
    
    def test_with_system_state(self):
        """Test creating FailureLog with system state."""
        try:
            raise RuntimeError("Error")
        except Exception as e:
            failure = FailureLog.from_exception(
                execution_id="exec-123",
                failed_step=1,
                exception=e,
                system_state={"current_artifacts": 0, "provider": "openai"},
            )
        
        assert failure.system_state is not None
        assert failure.system_state["provider"] == "openai"
