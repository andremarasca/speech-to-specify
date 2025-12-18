"""Input entity representing chaotic text provided by the user."""

from datetime import datetime
import hashlib

from pydantic import BaseModel, Field, field_validator, model_validator

from src.lib.timestamps import generate_id, generate_timestamp


class Input(BaseModel):
    """
    Texto desestruturado fornecido pelo usuário como ponto de partida.

    Immutable after creation. The content_hash is automatically calculated
    from the content to enable integrity verification.
    """

    id: str = Field(default_factory=generate_id, description="Unique identifier (UUID)")
    content: str = Field(..., description="Raw chaotic text content")
    content_hash: str = Field(default="", description="SHA-256 hash of content")
    source_path: str | None = Field(default=None, description="Original file path if applicable")
    created_at: datetime = Field(default_factory=generate_timestamp, description="UTC timestamp")

    model_config = {
        "frozen": True,  # Immutable after creation
        "str_strip_whitespace": False,  # Preserve original whitespace
    }

    @field_validator("content")
    @classmethod
    def content_not_empty(cls, v: str) -> str:
        """Validate that content is not empty or whitespace-only."""
        if not v or not v.strip():
            from src.lib.exceptions import ValidationError

            raise ValidationError(
                "Input content cannot be empty or whitespace-only", field="content"
            )
        return v

    @model_validator(mode="after")
    def compute_hash(self) -> "Input":
        """Compute content hash if not provided."""
        if not self.content_hash:
            computed_hash = hashlib.sha256(self.content.encode("utf-8")).hexdigest()
            # Since model is frozen, we need to use object.__setattr__
            object.__setattr__(self, "content_hash", computed_hash)
        return self

    def verify_integrity(self) -> bool:
        """Verify that content_hash matches the actual content."""
        computed = hashlib.sha256(self.content.encode("utf-8")).hexdigest()
        return computed == self.content_hash

    @classmethod
    def from_file(cls, file_path: str) -> "Input":
        """
        Create an Input from a file.

        Args:
            file_path: Path to the input file

        Returns:
            Input instance with content loaded from file

        Raises:
            ValidationError: If file cannot be read or is empty
        """
        from pathlib import Path
        from src.lib.exceptions import ValidationError

        path = Path(file_path)

        if not path.exists():
            raise ValidationError(f"Input file not found: {file_path}", field="source_path")

        if not path.is_file():
            raise ValidationError(f"Path is not a file: {file_path}", field="source_path")

        try:
            content = path.read_text(encoding="utf-8")
        except Exception as e:
            raise ValidationError(f"Failed to read file: {e}", field="content")

        return cls(content=content, source_path=str(path.absolute()))
