"""Execution entity representing a processing run through the pipeline."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, model_validator

from src.lib.timestamps import generate_id, generate_timestamp


class ExecutionStatus(str, Enum):
    """Possible states for an execution."""

    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class Execution(BaseModel):
    """
    Instância de processamento de uma entrada através da cadeia completa.

    Tracks the progress of an input through all pipeline steps.
    Status transitions: in_progress → completed | in_progress → failed
    """

    id: str = Field(default_factory=generate_id, description="Unique identifier (UUID)")
    input_id: str = Field(..., description="Reference to the input being processed")
    status: ExecutionStatus = Field(
        default=ExecutionStatus.IN_PROGRESS, description="Current execution state"
    )
    started_at: datetime = Field(default_factory=generate_timestamp, description="Start timestamp")
    completed_at: datetime | None = Field(default=None, description="Completion timestamp")
    current_step: int | None = Field(default=1, description="Current step being processed")
    total_steps: int = Field(default=4, ge=1, description="Total steps in the chain")
    error_message: str | None = Field(default=None, description="Error message if failed")

    model_config = {
        "use_enum_values": True,
    }

    @model_validator(mode="after")
    def validate_state_consistency(self) -> "Execution":
        """Validate that state fields are consistent with status."""
        if self.status == ExecutionStatus.COMPLETED:
            if self.completed_at is None:
                object.__setattr__(self, "completed_at", generate_timestamp())

        if self.status == ExecutionStatus.FAILED:
            if self.completed_at is None:
                object.__setattr__(self, "completed_at", generate_timestamp())
            if not self.error_message:
                from src.lib.exceptions import ValidationError

                raise ValidationError(
                    "error_message is required when status is 'failed'", field="error_message"
                )

        if self.current_step is not None and self.current_step > self.total_steps:
            from src.lib.exceptions import ValidationError

            raise ValidationError(
                f"current_step ({self.current_step}) cannot exceed total_steps ({self.total_steps})",
                field="current_step",
            )

        return self

    def mark_step_complete(self, step: int) -> "Execution":
        """
        Create a new Execution with the step marked as complete.

        Args:
            step: The step number that was completed

        Returns:
            New Execution instance with updated state
        """
        next_step = step + 1 if step < self.total_steps else None
        new_status = ExecutionStatus.IN_PROGRESS
        completed_at = None

        if step >= self.total_steps:
            new_status = ExecutionStatus.COMPLETED
            completed_at = generate_timestamp()
            next_step = None

        return Execution(
            id=self.id,
            input_id=self.input_id,
            status=new_status,
            started_at=self.started_at,
            completed_at=completed_at,
            current_step=next_step,
            total_steps=self.total_steps,
            error_message=None,
        )

    def mark_failed(self, error_message: str, failed_step: int | None = None) -> "Execution":
        """
        Create a new Execution marked as failed.

        Args:
            error_message: Description of the failure
            failed_step: Step where failure occurred

        Returns:
            New Execution instance with failed state
        """
        return Execution(
            id=self.id,
            input_id=self.input_id,
            status=ExecutionStatus.FAILED,
            started_at=self.started_at,
            completed_at=generate_timestamp(),
            current_step=failed_step or self.current_step,
            total_steps=self.total_steps,
            error_message=error_message,
        )

    @property
    def is_complete(self) -> bool:
        """Check if execution completed successfully."""
        return self.status == ExecutionStatus.COMPLETED

    @property
    def is_failed(self) -> bool:
        """Check if execution failed."""
        return self.status == ExecutionStatus.FAILED

    @property
    def is_running(self) -> bool:
        """Check if execution is still in progress."""
        return self.status == ExecutionStatus.IN_PROGRESS
