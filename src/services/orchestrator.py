"""Narrative pipeline orchestrator - the core transformation engine."""

from dataclasses import dataclass
from datetime import datetime

from src.models import Input, Artifact, Execution, ExecutionStatus, LLMLog, FailureLog
from src.services.llm.base import LLMProvider
from src.services.persistence.base import ArtifactStore, LogStore
from src.lib.prompts import load_prompt
from src.lib.timestamps import generate_timestamp
from src.lib.exceptions import LLMError, ValidationError, NarrativeError


@dataclass(frozen=True)
class PipelineStep:
    """
    Definition of a single step in the narrative pipeline.

    Attributes:
        number: Step number in sequence (1-indexed)
        name: Semantic name (e.g., "constitution")
        prompt_template: Name of the prompt template to use
    """

    number: int
    name: str
    prompt_template: str


class NarrativePipeline:
    """
    Orchestrates the transformation of chaotic text into structured artifacts.

    The pipeline executes a fixed sequence of steps, each producing an artifact
    that builds on the previous ones. All LLM interactions are logged for auditability.

    Steps:
        1. constitution - Extract governing principles
        2. specification - Define requirements and user stories
        3. planning - Create implementation plan
    """

    # Fixed step sequence - immutable pipeline definition
    STEPS = [
        PipelineStep(number=1, name="constitution", prompt_template="constitution"),
        PipelineStep(number=2, name="specification", prompt_template="specification"),
        PipelineStep(number=3, name="planning", prompt_template="planning"),
    ]

    def __init__(
        self,
        provider: LLMProvider,
        artifact_store: ArtifactStore,
        log_store: LogStore,
        verbose: bool = False,
    ):
        """
        Initialize the pipeline.

        Args:
            provider: LLM provider for text generation
            artifact_store: Storage for artifacts and execution metadata
            log_store: Storage for LLM interaction logs
            verbose: Whether to output detailed progress
        """
        self._provider = provider
        self._artifact_store = artifact_store
        self._log_store = log_store
        self._verbose = verbose

        # Runtime state
        self._current_execution: Execution | None = None
        self._artifacts: dict[int, Artifact] = {}  # step_number -> Artifact
        self._input: Input | None = None

    def execute(self, input_data: Input) -> Execution:
        """
        Execute the complete pipeline on the given input.

        Args:
            input_data: The chaotic text to transform

        Returns:
            Execution: The completed execution with status and metadata

        Raises:
            ValidationError: If input validation fails
            LLMError: If any LLM call fails
        """
        # Validate input
        self._validate_input(input_data)

        # Initialize execution
        self._input = input_data
        self._current_execution = Execution(
            input_id=input_data.id,
            total_steps=len(self.STEPS),
        )
        self._artifacts = {}

        # Persist input and initial execution state
        self._artifact_store.save_input(self._current_execution.id, input_data)
        self._artifact_store.save_execution(self._current_execution)

        self._log_progress(f"Execution started: {self._current_execution.id}")

        # Execute each step sequentially
        for step in self.STEPS:
            self._log_progress(f"Processing step {step.number}/{len(self.STEPS)}: {step.name}")

            try:
                # Execute the step
                artifact = self._execute_step(step)

                # Store artifact
                self._artifacts[step.number] = artifact

                # Persist artifact immediately (before next step)
                self._artifact_store.save_artifact(self._current_execution.id, artifact)

                # Update execution state
                self._current_execution = self._current_execution.mark_step_complete(step.number)
                self._artifact_store.save_execution(self._current_execution)

            except (LLMError, ValidationError, NarrativeError) as e:
                # Handle failure: preserve state and re-raise
                self._handle_failure(step, e)
                raise
            except Exception as e:
                # Wrap unexpected errors
                wrapped = NarrativeError(f"Unexpected error in step {step.name}: {e}")
                self._handle_failure(step, wrapped)
                raise wrapped from e

        self._log_progress(f"Execution completed: {self._get_output_path()}")

        return self._current_execution

    def _validate_input(self, input_data: Input) -> None:
        """Validate input before processing."""
        if not input_data.content or not input_data.content.strip():
            raise ValidationError("Input content cannot be empty", field="content")

        if not input_data.verify_integrity():
            raise ValidationError("Input integrity check failed", field="content_hash")

    def _execute_step(self, step: PipelineStep) -> Artifact:
        """
        Execute a single pipeline step.

        Args:
            step: The step to execute

        Returns:
            Artifact: The generated artifact
        """
        # Build the prompt with context
        prompt = self._build_prompt(step)

        # Call LLM with logging
        response = self._call_llm(step, prompt)

        # Create artifact
        predecessor_id = None
        if step.number > 1:
            predecessor_id = self._artifacts[step.number - 1].id

        artifact = Artifact(
            execution_id=self._current_execution.id,
            step_number=step.number,
            step_name=step.name,
            predecessor_id=predecessor_id,
            content=response,
        )

        return artifact

    def _build_prompt(self, step: PipelineStep) -> str:
        """Build the prompt for a step with all required context."""
        # Always include the original input
        variables = {
            "input_content": self._input.content,
        }

        # Add previous artifacts as context
        if step.number >= 2 and 1 in self._artifacts:
            variables["constitution_content"] = self._artifacts[1].content

        if step.number >= 3 and 2 in self._artifacts:
            variables["specification_content"] = self._artifacts[2].content

        return load_prompt(step.prompt_template, **variables)

    def _call_llm(self, step: PipelineStep, prompt: str) -> str:
        """
        Call the LLM and log the interaction.

        Args:
            step: Current pipeline step
            prompt: The prompt to send

        Returns:
            str: The LLM response

        Raises:
            LLMError: If the LLM call fails
        """
        prompt_sent_at = generate_timestamp()

        if self._verbose:
            self._log_progress(f"  Prompt: {len(prompt)} chars")

        # Make the LLM call
        response = self._provider.complete(prompt)

        response_received_at = generate_timestamp()
        latency_ms = int((response_received_at - prompt_sent_at).total_seconds() * 1000)

        if self._verbose:
            self._log_progress(f"  Response: {len(response)} chars (latency: {latency_ms}ms)")

        # Log the interaction
        llm_log = LLMLog.create(
            execution_id=self._current_execution.id,
            step_number=step.number,
            provider=self._provider.provider_name,
            prompt=prompt,
            response=response,
            prompt_sent_at=prompt_sent_at,
            response_received_at=response_received_at,
        )

        self._log_store.append_llm_log(self._current_execution.id, llm_log)

        return response

    def _get_output_path(self) -> str:
        """Get the output directory path for the current execution."""
        if self._current_execution:
            return f"output/executions/{self._current_execution.id}"
        return "output/executions/"

    def _log_progress(self, message: str) -> None:
        """Log progress to stdout."""
        print(message)

    def _handle_failure(self, step: PipelineStep, error: Exception) -> None:
        """
        Handle a failure during pipeline execution.

        Preserves all completed work and logs the failure for debugging.

        Args:
            step: The step that failed
            error: The exception that was raised
        """
        import sys

        # Mark execution as failed
        error_message = str(error)
        self._current_execution = self._current_execution.mark_failed(
            error_message=error_message, failed_step=step.number
        )
        self._artifact_store.save_execution(self._current_execution)

        # Create and persist failure log
        system_state = {
            "completed_steps": list(self._artifacts.keys()),
            "provider": self._provider.provider_name,
            "total_steps": len(self.STEPS),
        }

        failure_log = FailureLog.from_exception(
            execution_id=self._current_execution.id,
            failed_step=step.number,
            exception=error,
            system_state=system_state,
        )

        self._log_store.save_failure(self._current_execution.id, failure_log)

        # Log to stderr
        self._log_progress(f"Error at step {step.number} ({step.name}): {error_message}")
        print(f"Error: {error_message}", file=sys.stderr)
