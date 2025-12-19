"""Help system for exhaustive command documentation.

Per contracts/help-system.md for 004-resilient-voice-capture.
Ensures no command exists without documentation per Constitution Pillar II.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Callable, Optional, Any


@dataclass
class CommandInfo:
    """Information about a registered command.
    
    Attributes:
        name: Command name (e.g., "/help", "/close")
        description: Human-readable description
        params: Parameter descriptions {name: description}
        examples: Usage examples
        category: Command category for grouping
    """
    
    name: str
    description: str
    params: dict[str, str] = field(default_factory=dict)
    examples: list[str] = field(default_factory=list)
    category: str = "general"
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "description": self.description,
            "params": self.params,
            "examples": self.examples,
            "category": self.category,
        }


@dataclass
class CommandHandler:
    """Command handler with associated info.
    
    Attributes:
        info: Command metadata and documentation
        handler: Async function that handles the command
    """
    
    info: CommandInfo
    handler: Callable[..., Any]


@dataclass
class HelpResponse:
    """Response from help system.
    
    Attributes:
        found: Whether the requested command was found
        text: Formatted help text
        commands: List of matching commands
        categories: Available categories (when listing all)
    """
    
    found: bool
    text: str
    commands: list[CommandInfo] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)


@dataclass
class ValidationResult:
    """Result of help completeness validation.
    
    Attributes:
        valid: Whether all commands are documented
        missing_docs: Commands missing documentation
        orphaned_handlers: Handlers without registration
        issues: List of validation issue descriptions
    """
    
    valid: bool
    missing_docs: list[str] = field(default_factory=list)
    orphaned_handlers: list[str] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)


class DuplicateCommandError(Exception):
    """Raised when attempting to register a duplicate command."""
    
    def __init__(self, command: str) -> None:
        self.command = command
        super().__init__(f"Command '{command}' is already registered")


class HelpSystem(ABC):
    """Service for command registration and help generation.
    
    Per contracts/help-system.md for 004-resilient-voice-capture.
    """
    
    @abstractmethod
    def register(
        self,
        name: str,
        description: str,
        handler: Callable[..., Any],
        params: Optional[dict[str, str]] = None,
        examples: Optional[list[str]] = None,
        category: str = "general"
    ) -> None:
        """Register a command with its documentation.
        
        Args:
            name: Command name (e.g., "/help", "/close")
            description: Human-readable description
            handler: Async function that handles the command
            params: Parameter descriptions {name: description}
            examples: Usage examples
            category: Command category for grouping
            
        Raises:
            DuplicateCommandError: Command already registered
        """
        pass
    
    @abstractmethod
    def get_help(self, command: Optional[str] = None) -> HelpResponse:
        """Get help documentation.
        
        Args:
            command: Specific command (None = all commands)
            
        Returns:
            HelpResponse with formatted documentation
        """
        pass
    
    @abstractmethod
    def get_handler(self, command: str) -> Optional[CommandHandler]:
        """Get handler for command.
        
        Args:
            command: Command name
            
        Returns:
            CommandHandler or None if not registered
        """
        pass
    
    @abstractmethod
    def list_commands(self, category: Optional[str] = None) -> list[CommandInfo]:
        """List all registered commands.
        
        Args:
            category: Filter by category
            
        Returns:
            List of command info
        """
        pass
    
    @abstractmethod
    def validate_completeness(self) -> ValidationResult:
        """Verify all commands are documented.
        
        Used in tests to ensure no undocumented commands exist.
        
        Returns:
            ValidationResult with any issues found
        """
        pass


# Category display configuration
CATEGORY_ICONS = {
    "session": "📁",
    "search": "🔍",
    "recovery": "🔧",
    "system": "💡",
    "general": "📋",
}

CATEGORY_ORDER = ["session", "search", "recovery", "system", "general"]


class DefaultHelpSystem(HelpSystem):
    """Default implementation of HelpSystem.
    
    Provides exhaustive command documentation with validation
    to ensure no command exists without docs.
    """
    
    # Required commands per contracts/help-system.md
    REQUIRED_COMMANDS = {
        "/help", "/start", "/close", "/status",
        "/sessions", "/reopen", "/recover", "/retry"
    }
    
    def __init__(self):
        """Initialize empty help system."""
        self._commands: dict[str, CommandHandler] = {}
        self._categories: set[str] = set()
    
    def register(
        self,
        name: str,
        description: str,
        handler: Callable[..., Any],
        params: Optional[dict[str, str]] = None,
        examples: Optional[list[str]] = None,
        category: str = "general"
    ) -> None:
        """Register a command with its documentation."""
        # Normalize name
        if not name.startswith("/"):
            name = f"/{name}"
        
        if name in self._commands:
            raise DuplicateCommandError(name)
        
        info = CommandInfo(
            name=name,
            description=description,
            params=params or {},
            examples=examples or [],
            category=category,
        )
        self._commands[name] = CommandHandler(info=info, handler=handler)
        self._categories.add(category)
    
    def get_help(self, command: Optional[str] = None) -> HelpResponse:
        """Get help documentation."""
        if command:
            # Normalize command name
            if not command.startswith("/"):
                command = f"/{command}"
            
            handler = self._commands.get(command)
            if handler:
                return HelpResponse(
                    found=True,
                    text=self._format_command_help(handler.info),
                    commands=[handler.info],
                )
            return HelpResponse(
                found=False,
                text=f"❌ Command '{command}' not found.\n\nType /help to see available commands.",
                commands=[],
            )
        
        # All commands
        all_commands = [h.info for h in self._commands.values()]
        return HelpResponse(
            found=True,
            text=self._format_all_help(all_commands),
            commands=all_commands,
            categories=list(self._categories),
        )
    
    def get_handler(self, command: str) -> Optional[CommandHandler]:
        """Get handler for command."""
        if not command.startswith("/"):
            command = f"/{command}"
        return self._commands.get(command)
    
    def list_commands(self, category: Optional[str] = None) -> list[CommandInfo]:
        """List all registered commands."""
        commands = [h.info for h in self._commands.values()]
        if category:
            commands = [c for c in commands if c.category == category]
        return sorted(commands, key=lambda c: c.name)
    
    def validate_completeness(self) -> ValidationResult:
        """Verify all commands are documented."""
        registered = set(self._commands.keys())
        missing = self.REQUIRED_COMMANDS - registered
        
        issues = [f"Missing command: {cmd}" for cmd in sorted(missing)]
        
        return ValidationResult(
            valid=len(missing) == 0,
            missing_docs=list(sorted(missing)),
            orphaned_handlers=[],
            issues=issues,
        )
    
    def _format_command_help(self, info: CommandInfo) -> str:
        """Format help for a single command."""
        lines = [
            f"📖 {info.name}",
            "",
            info.description,
            "",
        ]
        
        if info.params:
            lines.append("Parameters:")
            for name, desc in info.params.items():
                lines.append(f"  {name} - {desc}")
            lines.append("")
        
        if info.examples:
            lines.append("Examples:")
            for ex in info.examples:
                lines.append(f"  {ex}")
            lines.append("")
        
        return "\n".join(lines)
    
    def _format_all_help(self, commands: list[CommandInfo]) -> str:
        """Format help for all commands."""
        # Group by category
        by_category: dict[str, list[CommandInfo]] = {}
        for cmd in commands:
            by_category.setdefault(cmd.category, []).append(cmd)
        
        lines = ["📖 Available Commands", ""]
        
        # Output in defined order
        for cat in CATEGORY_ORDER:
            if cat not in by_category:
                continue
            cmds = sorted(by_category[cat], key=lambda c: c.name)
            icon = CATEGORY_ICONS.get(cat, "📋")
            lines.append(f"{icon} {cat.title()} Commands")
            for cmd in cmds:
                # Truncate description to fit on one line
                desc = cmd.description
                if len(desc) > 50:
                    desc = desc[:47] + "..."
                lines.append(f"  {cmd.name:<12} - {desc}")
            lines.append("")
        
        # Any categories not in order
        for cat, cmds in by_category.items():
            if cat in CATEGORY_ORDER:
                continue
            cmds = sorted(cmds, key=lambda c: c.name)
            icon = CATEGORY_ICONS.get(cat, "📋")
            lines.append(f"{icon} {cat.title()} Commands")
            for cmd in cmds:
                desc = cmd.description
                if len(desc) > 50:
                    desc = desc[:47] + "..."
                lines.append(f"  {cmd.name:<12} - {desc}")
            lines.append("")
        
        lines.append("Type /help <command> for detailed usage.")
        
        return "\n".join(lines)