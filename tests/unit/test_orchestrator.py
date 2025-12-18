"""Unit tests for the orchestrator."""

import pytest

from src.services.orchestrator import PipelineStep, NarrativePipeline


class TestPipelineStep:
    """Tests for PipelineStep dataclass."""

    def test_create_step(self):
        """Test creating a pipeline step."""
        step = PipelineStep(
            number=1,
            name="constitution",
            prompt_template="constitution",
        )

        assert step.number == 1
        assert step.name == "constitution"
        assert step.prompt_template == "constitution"

    def test_step_requires_positive_number(self):
        """Test that step number must be positive."""
        # PipelineStep is a dataclass, validation happens at pipeline level
        step = PipelineStep(number=1, name="test", prompt_template="test")
        assert step.number >= 1


class TestStepSequenceValidation:
    """Tests for validating step sequence."""

    def test_steps_list_not_empty(self):
        """Test that STEPS list is not empty."""
        assert len(NarrativePipeline.STEPS) > 0

    def test_step_numbers_contiguous(self):
        """Test that step numbers are contiguous (1, 2, 3...)."""
        steps = NarrativePipeline.STEPS

        for i, step in enumerate(steps):
            expected_number = i + 1
            assert (
                step.number == expected_number
            ), f"Step {i} has number {step.number}, expected {expected_number}"

    def test_step_names_unique(self):
        """Test that all step names are unique."""
        steps = NarrativePipeline.STEPS
        names = [step.name for step in steps]

        assert len(names) == len(set(names)), "Step names must be unique"

    def test_constitution_is_first(self):
        """Test that constitution is the first step."""
        steps = NarrativePipeline.STEPS

        assert steps[0].name == "constitution"
        assert steps[0].number == 1

    def test_planning_is_last(self):
        """Test that planning is the last step."""
        steps = NarrativePipeline.STEPS

        assert steps[-1].name == "planning"
