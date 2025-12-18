"""Integration tests for the narrative pipeline orchestrator."""

import pytest
from pathlib import Path

from src.models import Input, Execution, ExecutionStatus
from src.services.orchestrator import NarrativePipeline, PipelineStep
from src.services.llm import get_provider
from src.services.persistence import create_artifact_store, create_log_store
from src.lib.exceptions import ValidationError, LLMError


class TestNarrativePipeline:
    """Integration tests for complete pipeline execution."""
    
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
    
    def test_complete_pipeline_execution(self, pipeline, sample_input_content, temp_output_dir):
        """Test that pipeline produces all 3 artifacts."""
        input_data = Input(content=sample_input_content)
        
        execution = pipeline.execute(input_data)
        
        # Check execution completed
        assert execution.status == ExecutionStatus.COMPLETED
        assert execution.is_complete
        
        # Check artifacts were created
        artifacts_dir = Path(temp_output_dir) / "executions" / execution.id / "artifacts"
        assert artifacts_dir.exists()
        
        artifact_files = list(artifacts_dir.glob("*.md"))
        assert len(artifact_files) == 3
        
        # Check file names match expected steps
        filenames = [f.name for f in artifact_files]
        assert "01_constitution.md" in filenames
        assert "02_specification.md" in filenames
        assert "03_planning.md" in filenames
    
    def test_artifacts_have_content(self, pipeline, sample_input_content, temp_output_dir):
        """Test that generated artifacts have meaningful content."""
        input_data = Input(content=sample_input_content)
        
        execution = pipeline.execute(input_data)
        
        artifacts_dir = Path(temp_output_dir) / "executions" / execution.id / "artifacts"
        
        for artifact_file in artifacts_dir.glob("*.md"):
            content = artifact_file.read_text()
            assert len(content) > 100  # Should have substantial content
            assert "---" in content  # Should have YAML front matter
    
    def test_input_persisted(self, pipeline, sample_input_content, temp_output_dir):
        """Test that input is persisted."""
        input_data = Input(content=sample_input_content)
        
        execution = pipeline.execute(input_data)
        
        input_path = Path(temp_output_dir) / "executions" / execution.id / "input.md"
        assert input_path.exists()
        
        content = input_path.read_text(encoding="utf-8")
        # Check key phrases from the input (handle encoding differences)
        assert "pipeline" in content.lower()
        assert "OpenAI" in content or "openai" in content.lower()
    
    def test_execution_metadata_persisted(self, pipeline, sample_input_content, temp_output_dir):
        """Test that execution metadata is persisted."""
        input_data = Input(content=sample_input_content)
        
        execution = pipeline.execute(input_data)
        
        exec_path = Path(temp_output_dir) / "executions" / execution.id / "execution.json"
        assert exec_path.exists()
    
    def test_empty_input_rejected(self, pipeline):
        """Test that empty input is rejected before execution."""
        with pytest.raises(ValidationError):
            Input(content="")
    
    def test_whitespace_input_rejected(self, pipeline):
        """Test that whitespace-only input is rejected."""
        with pytest.raises(ValidationError):
            Input(content="   \n\t  ")
    
    def test_execution_has_correct_step_count(self, pipeline, sample_input_content):
        """Test that execution reports correct total steps."""
        input_data = Input(content=sample_input_content)
        
        execution = pipeline.execute(input_data)
        
        assert execution.total_steps == 3
    
    def test_artifacts_form_chain(self, pipeline, sample_input_content, temp_output_dir):
        """Test that artifacts reference their predecessors."""
        input_data = Input(content=sample_input_content)
        
        pipeline.execute(input_data)
        
        # Artifacts should form a chain via predecessor_id
        artifact_store = pipeline._artifact_store
        artifacts = artifact_store.list_artifacts(pipeline._current_execution.id)
        
        assert len(artifacts) == 3
        assert artifacts[0].predecessor_id is None  # First has no predecessor
        assert artifacts[1].predecessor_id == artifacts[0].id
        assert artifacts[2].predecessor_id == artifacts[1].id


class TestPipelineStepSequence:
    """Tests for pipeline step ordering."""
    
    def test_steps_are_fixed(self):
        """Test that pipeline has fixed step sequence."""
        steps = NarrativePipeline.STEPS
        
        assert len(steps) == 3
        assert steps[0].name == "constitution"
        assert steps[1].name == "specification"
        assert steps[2].name == "planning"
    
    def test_step_numbers_are_sequential(self):
        """Test that step numbers are 1, 2, 3."""
        steps = NarrativePipeline.STEPS
        
        for i, step in enumerate(steps, 1):
            assert step.number == i
    
    def test_each_step_has_prompt_template(self):
        """Test that each step references a prompt template."""
        steps = NarrativePipeline.STEPS
        
        for step in steps:
            assert step.prompt_template is not None
            assert len(step.prompt_template) > 0
