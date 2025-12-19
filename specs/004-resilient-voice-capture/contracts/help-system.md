# Contract: Help System

**Feature**: 004-resilient-voice-capture  
**Service**: `HelpSystem`  
**Location**: `src/services/help/registry.py`

## Purpose

Provides exhaustive, auto-generated help documentation for all commands. Ensures no command exists without documentation per Constitution Pillar II (Simplicidade Operacional).

## Interface

```python
from abc import ABC, abstractmethod
from typing import Callable, Optional
from dataclasses import dataclass

class HelpSystem(ABC):
    """Service for command registration and help generation."""
    
    @abstractmethod
    def register(
        self,
        name: str,
        description: str,
        handler: Callable,
        params: Optional[dict[str, str]] = None,
        examples: Optional[list[str]] = None,
        category: str = "general"
    ) -> None:
        """
        Register a command with its documentation.
        
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
        """
        Get help documentation.
        
        Args:
            command: Specific command (None = all commands)
            
        Returns:
            HelpResponse with formatted documentation
        """
        pass
    
    @abstractmethod
    def get_handler(self, command: str) -> Optional[CommandHandler]:
        """
        Get handler for command.
        
        Args:
            command: Command name
            
        Returns:
            CommandHandler or None if not registered
        """
        pass
    
    @abstractmethod
    def list_commands(self, category: Optional[str] = None) -> list[CommandInfo]:
        """
        List all registered commands.
        
        Args:
            category: Filter by category
            
        Returns:
            List of command info
        """
        pass
    
    @abstractmethod
    def validate_completeness(self) -> ValidationResult:
        """
        Verify all commands are documented.
        
        Used in tests to ensure no undocumented commands exist.
        
        Returns:
            ValidationResult with any issues found
        """
        pass
```

## Data Types

```python
@dataclass
class CommandInfo:
    """Information about a registered command."""
    name: str
    description: str
    params: dict[str, str]
    examples: list[str]
    category: str
    
@dataclass
class CommandHandler:
    """Handler for a command."""
    name: str
    handler: Callable
    info: CommandInfo

@dataclass
class HelpResponse:
    """Formatted help response."""
    content: str  # Formatted for display
    commands: list[CommandInfo]
    generated_at: datetime
    
@dataclass
class ValidationResult:
    """Result of completeness validation."""
    is_complete: bool
    undocumented_handlers: list[str]
    orphan_docs: list[str]
    issues: list[str]
```

## Decorator Interface

```python
# Preferred registration method via decorator
@command("/close")
@description("Finalize the current session and start processing")
@param("--force", "Skip confirmation prompt")
@example("/close")
@example("/close --force")
@category("session")
async def cmd_close(ctx: Context, force: bool = False):
    """Close active session."""
    ...
```

## Required Commands

All commands MUST be registered with full documentation:

| Command | Category | Description |
|---------|----------|-------------|
| `/help` | system | Show all available commands |
| `/help <command>` | system | Show detailed help for command |
| `/start` | session | Start a new recording session |
| `/close` | session | Finalize session and start processing |
| `/reopen <id>` | session | Reopen a previous session |
| `/status` | session | Show current session status |
| `/sessions` | search | List recent sessions chronologically |
| `/sessions <query>` | search | Search sessions semantically |
| `/recover` | recovery | Show interrupted sessions |
| `/retry <session>` | recovery | Retry failed transcriptions |

## Help Output Format

### All Commands (`/help`)

```
📖 Available Commands

📁 Session Commands
  /start      - Start a new recording session
  /close      - Finalize session and start processing
  /reopen     - Reopen a previous session
  /status     - Show current session status

🔍 Search Commands
  /sessions   - List or search sessions

🔧 Recovery Commands
  /recover    - Show interrupted sessions
  /retry      - Retry failed transcriptions

💡 System Commands
  /help       - Show this help message

Type /help <command> for detailed usage.
```

### Specific Command (`/help close`)

```
📖 /close

Finalize the current session and start processing.

When you close a session:
• All audio is preserved
• Transcription begins in background
• You can check progress with /status

Parameters:
  --force    Skip confirmation prompt

Examples:
  /close
  /close --force

Related: /start, /reopen, /status
```

## Test Cases (Contract Tests)

```python
def test_all_commands_registered():
    """Every command handler has a registration."""
    
def test_help_lists_all_commands():
    """Help output includes every registered command."""
    
def test_help_command_shows_details():
    """Help for specific command shows params and examples."""
    
def test_unknown_command_suggests_similar():
    """Unknown command suggests similar known commands."""
    
def test_categories_group_correctly():
    """Commands are grouped by category in output."""
    
def test_validation_catches_orphans():
    """Validation detects handlers without registration."""
```

## Enforcement (Test-Time)

```python
# In conftest.py or dedicated test
def test_help_completeness():
    """Fail CI if any command lacks documentation."""
    help_system = get_help_system()
    result = help_system.validate_completeness()
    
    assert result.is_complete, (
        f"Undocumented commands: {result.undocumented_handlers}\n"
        f"Issues: {result.issues}"
    )
```

## Configuration

```python
@dataclass
class HelpConfig:
    show_examples: bool = True
    show_related_commands: bool = True
    max_examples_per_command: int = 3
    format: str = "telegram"  # "telegram" | "plain" | "markdown"
```

## Dependencies

- None (self-contained)
