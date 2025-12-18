"""Log entities for LLM interactions and failures."""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from src.lib.timestamps import generate_id, generate_timestamp


class LLMLog(BaseModel):
    """
    Registro de uma interação com provedor de LLM.

    Immutable after creation. Captures the complete request/response
    cycle for audit and debugging purposes.
    """

    id: str = Field(default_factory=generate_id, description="Unique identifier (UUID)")
    execution_id: str = Field(..., description="Reference to the execution")
    step_number: int = Field(..., ge=1, description="Step that generated this interaction")
    provider: str = Field(..., description="Provider name (e.g., 'openai', 'anthropic')")
    prompt: str = Field(..., description="Prompt sent to the LLM")
    response: str = Field(..., description="Response received from the LLM")
    prompt_sent_at: datetime = Field(..., description="Timestamp when prompt was sent")
    response_received_at: datetime = Field(..., description="Timestamp when response was received")
    latency_ms: int = Field(..., ge=0, description="Latency in milliseconds")

    model_config = {
        "frozen": True,  # Immutable after creation
    }

    @field_validator("prompt")
    @classmethod
    def prompt_not_empty(cls, v: str) -> str:
        """Validate that prompt is not empty."""
        if not v or not v.strip():
            from src.lib.exceptions import ValidationError

            raise ValidationError("LLM prompt cannot be empty", field="prompt")
        return v

    @classmethod
    def create(
        cls,
        execution_id: str,
        step_number: int,
        provider: str,
        prompt: str,
        response: str,
        prompt_sent_at: datetime,
        response_received_at: datetime,
    ) -> "LLMLog":
        """
        Create an LLMLog with computed latency.

        Args:
            execution_id: Execution this log belongs to
            step_number: Step number in the pipeline
            provider: LLM provider name
            prompt: The prompt sent
            response: The response received
            prompt_sent_at: When the prompt was sent
            response_received_at: When the response was received

        Returns:
            LLMLog instance with computed latency_ms
        """
        latency_ms = int((response_received_at - prompt_sent_at).total_seconds() * 1000)

        return cls(
            execution_id=execution_id,
            step_number=step_number,
            provider=provider,
            prompt=prompt,
            response=response,
            prompt_sent_at=prompt_sent_at,
            response_received_at=response_received_at,
            latency_ms=latency_ms,
        )


class FailureLog(BaseModel):
    """
    Registro de falha durante processamento.

    Immutable after creation. Captures failure context for
    debugging and recovery.
    """

    id: str = Field(default_factory=generate_id, description="Unique identifier (UUID)")
    execution_id: str = Field(..., description="Reference to the failed execution")
    failed_step: int = Field(..., ge=1, description="Step where failure occurred")
    error_type: str = Field(..., description="Exception class name")
    error_message: str = Field(..., description="Human-readable error description")
    stack_trace: str | None = Field(default=None, description="Stack trace for debugging")
    system_state: dict | None = Field(default=None, description="System state at failure time")
    occurred_at: datetime = Field(
        default_factory=generate_timestamp, description="Failure timestamp"
    )

    model_config = {
        "frozen": True,  # Immutable after creation
    }

    @classmethod
    def from_exception(
        cls,
        execution_id: str,
        failed_step: int,
        exception: Exception,
        system_state: dict | None = None,
    ) -> "FailureLog":
        """
        Create a FailureLog from an exception.

        Args:
            execution_id: Execution that failed
            failed_step: Step where failure occurred
            exception: The exception that was raised
            system_state: Optional snapshot of system state

        Returns:
            FailureLog instance
        """
        import traceback

        return cls(
            execution_id=execution_id,
            failed_step=failed_step,
            error_type=type(exception).__name__,
            error_message=str(exception),
            stack_trace=traceback.format_exc(),
            system_state=system_state,
        )
