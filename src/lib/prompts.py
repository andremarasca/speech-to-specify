"""Prompt template loading and rendering utilities."""

from pathlib import Path
from string import Template

from src.lib.exceptions import ValidationError


class PromptLoader:
    """
    Load and render prompt templates from the prompts/ directory.

    Templates use simple string substitution with {{ variable }} syntax.
    """

    # Default prompts directory relative to project root
    DEFAULT_PROMPTS_DIR = Path(__file__).parent.parent.parent / "prompts"

    def __init__(self, prompts_dir: Path | str | None = None):
        """
        Initialize the prompt loader.

        Args:
            prompts_dir: Directory containing prompt templates.
                        Defaults to project's prompts/ directory.
        """
        self._prompts_dir = Path(prompts_dir) if prompts_dir else self.DEFAULT_PROMPTS_DIR

    def load(self, template_name: str) -> str:
        """
        Load a prompt template by name.

        Args:
            template_name: Name of the template (e.g., "constitution", "specification")
                          .md extension is optional

        Returns:
            str: The raw template content

        Raises:
            ValidationError: If template not found
        """
        # Normalize name
        if not template_name.endswith(".md"):
            template_name = f"{template_name}.md"

        template_path = self._prompts_dir / template_name

        if not template_path.exists():
            raise ValidationError(
                f"Prompt template not found: {template_name}", field="template_name"
            )

        return template_path.read_text(encoding="utf-8")

    def render(self, template_name: str, **variables) -> str:
        """
        Load and render a prompt template with variables.

        Args:
            template_name: Name of the template
            **variables: Variables to substitute in the template

        Returns:
            str: The rendered prompt

        Raises:
            ValidationError: If template not found or variable substitution fails
        """
        template_content = self.load(template_name)

        # Convert {{ var }} to $var for string.Template
        # This is a simple approach; for complex needs, consider jinja2
        for key in variables:
            template_content = template_content.replace(f"{{{{ {key} }}}}", f"${{{key}}}")

        try:
            template = Template(template_content)
            return template.safe_substitute(**variables)
        except Exception as e:
            raise ValidationError(
                f"Failed to render template '{template_name}': {e}", field="template"
            )

    def list_templates(self) -> list[str]:
        """
        List all available prompt templates.

        Returns:
            List of template names (without .md extension)
        """
        if not self._prompts_dir.exists():
            return []

        return [p.stem for p in self._prompts_dir.glob("*.md") if p.is_file()]


# Global loader instance (lazy loaded)
_loader: PromptLoader | None = None


def get_prompt_loader() -> PromptLoader:
    """Get the global prompt loader instance."""
    global _loader
    if _loader is None:
        _loader = PromptLoader()
    return _loader


def load_prompt(template_name: str, **variables) -> str:
    """
    Convenience function to load and render a prompt.

    Args:
        template_name: Name of the template
        **variables: Variables to substitute

    Returns:
        str: The rendered prompt
    """
    return get_prompt_loader().render(template_name, **variables)
