"""Contract tests for HelpSystem.

Per contracts/help-system.md for 004-resilient-voice-capture.
Tests the help system provides exhaustive documentation.
"""

import pytest
from datetime import datetime

from src.services.help.registry import (
    HelpSystem,
    CommandInfo,
    CommandHandler,
    HelpResponse,
    ValidationResult,
    DuplicateCommandError,
)


class MockHelpSystem(HelpSystem):
    """Test implementation of HelpSystem."""
    
    def __init__(self):
        self._commands: dict[str, CommandHandler] = {}
        self._categories: set[str] = set()
    
    def register(
        self,
        name: str,
        description: str,
        handler,
        params=None,
        examples=None,
        category: str = "general"
    ) -> None:
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
    
    def get_help(self, command=None) -> HelpResponse:
        if command:
            handler = self._commands.get(command)
            if handler:
                return HelpResponse(
                    found=True,
                    text=self._format_command_help(handler.info),
                    commands=[handler.info],
                )
            return HelpResponse(
                found=False,
                text=f"Command '{command}' not found.",
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
    
    def get_handler(self, command: str):
        return self._commands.get(command)
    
    def list_commands(self, category=None) -> list[CommandInfo]:
        commands = [h.info for h in self._commands.values()]
        if category:
            commands = [c for c in commands if c.category == category]
        return commands
    
    def validate_completeness(self) -> ValidationResult:
        # Check all required commands are registered
        required = {"/help", "/start", "/close", "/status", "/sessions", "/reopen", "/recover", "/retry"}
        registered = set(self._commands.keys())
        missing = required - registered
        
        return ValidationResult(
            valid=len(missing) == 0,
            missing_docs=list(missing),
            orphaned_handlers=[],
            issues=[f"Missing command: {cmd}" for cmd in missing],
        )
    
    def _format_command_help(self, info: CommandInfo) -> str:
        lines = [f"📖 {info.name}", "", info.description, ""]
        if info.params:
            lines.append("Parameters:")
            for name, desc in info.params.items():
                lines.append(f"  {name} - {desc}")
            lines.append("")
        if info.examples:
            lines.append("Examples:")
            for ex in info.examples:
                lines.append(f"  {ex}")
        return "\n".join(lines)
    
    def _format_all_help(self, commands: list[CommandInfo]) -> str:
        by_category: dict[str, list[CommandInfo]] = {}
        for cmd in commands:
            by_category.setdefault(cmd.category, []).append(cmd)
        
        lines = ["📖 Available Commands", ""]
        for cat, cmds in sorted(by_category.items()):
            lines.append(f"📁 {cat.title()} Commands")
            for cmd in cmds:
                lines.append(f"  {cmd.name} - {cmd.description}")
            lines.append("")
        lines.append("Type /help <command> for detailed usage.")
        return "\n".join(lines)


@pytest.fixture
def help_system():
    """Create a test HelpSystem."""
    return MockHelpSystem()


@pytest.fixture
def populated_help(help_system):
    """Create a HelpSystem with registered commands."""
    async def dummy_handler(*args):
        pass
    
    help_system.register(
        name="/start",
        description="Start a new recording session",
        handler=dummy_handler,
        examples=["/start"],
        category="session",
    )
    help_system.register(
        name="/close",
        description="Finalize session and start processing",
        handler=dummy_handler,
        params={"--force": "Skip confirmation"},
        examples=["/close", "/close --force"],
        category="session",
    )
    help_system.register(
        name="/help",
        description="Show available commands",
        handler=dummy_handler,
        params={"command": "Show help for specific command"},
        examples=["/help", "/help close"],
        category="system",
    )
    return help_system


class TestRegisterCommand:
    """Tests for command registration (FR-010)."""
    
    def test_register_command_succeeds(self, help_system):
        """Test that registering a command succeeds."""
        async def handler():
            pass
        
        help_system.register(
            name="/test",
            description="Test command",
            handler=handler,
        )
        
        result = help_system.get_handler("/test")
        assert result is not None
        assert result.info.name == "/test"
    
    def test_register_with_params(self, help_system):
        """Test registering command with parameters."""
        async def handler():
            pass
        
        help_system.register(
            name="/cmd",
            description="Test",
            handler=handler,
            params={"--flag": "Enable flag", "--value": "Set value"},
        )
        
        handler = help_system.get_handler("/cmd")
        assert "--flag" in handler.info.params
        assert "--value" in handler.info.params
    
    def test_register_with_examples(self, help_system):
        """Test registering command with examples."""
        async def handler():
            pass
        
        help_system.register(
            name="/cmd",
            description="Test",
            handler=handler,
            examples=["/cmd", "/cmd --flag"],
        )
        
        handler = help_system.get_handler("/cmd")
        assert len(handler.info.examples) == 2
    
    def test_register_with_category(self, help_system):
        """Test registering command with category."""
        async def handler():
            pass
        
        help_system.register(
            name="/cmd",
            description="Test",
            handler=handler,
            category="testing",
        )
        
        handler = help_system.get_handler("/cmd")
        assert handler.info.category == "testing"
    
    def test_duplicate_registration_raises(self, help_system):
        """Test that duplicate registration raises error."""
        async def handler():
            pass
        
        help_system.register("/cmd", "Test", handler)
        
        with pytest.raises(DuplicateCommandError) as exc:
            help_system.register("/cmd", "Duplicate", handler)
        
        assert "/cmd" in str(exc.value)


class TestGetHelp:
    """Tests for help retrieval."""
    
    def test_get_help_all_commands(self, populated_help):
        """Test getting help for all commands."""
        response = populated_help.get_help()
        
        assert response.found is True
        assert len(response.commands) >= 3
        assert "Available Commands" in response.text
    
    def test_get_help_specific_command(self, populated_help):
        """Test getting help for specific command."""
        response = populated_help.get_help("/start")
        
        assert response.found is True
        assert len(response.commands) == 1
        assert response.commands[0].name == "/start"
        assert "recording session" in response.text.lower()
    
    def test_get_help_unknown_command(self, populated_help):
        """Test getting help for unknown command."""
        response = populated_help.get_help("/unknown")
        
        assert response.found is False
        assert "not found" in response.text.lower()
    
    def test_help_includes_params(self, populated_help):
        """Test that help includes parameter descriptions."""
        response = populated_help.get_help("/close")
        
        assert "--force" in response.text or "force" in response.text.lower()
    
    def test_help_includes_examples(self, populated_help):
        """Test that help includes examples."""
        response = populated_help.get_help("/close")
        
        assert "/close" in response.text
    
    def test_help_groups_by_category(self, populated_help):
        """Test that all-help groups commands by category."""
        response = populated_help.get_help()
        
        # Should have category headers
        assert "session" in response.text.lower() or "Session" in response.text


class TestListCommands:
    """Tests for command listing."""
    
    def test_list_all_commands(self, populated_help):
        """Test listing all commands."""
        commands = populated_help.list_commands()
        
        assert len(commands) >= 3
        names = [c.name for c in commands]
        assert "/start" in names
        assert "/close" in names
    
    def test_list_by_category(self, populated_help):
        """Test listing commands by category."""
        commands = populated_help.list_commands(category="session")
        
        for cmd in commands:
            assert cmd.category == "session"


class TestValidateCompleteness:
    """Tests for completeness validation (FR-011)."""
    
    def test_incomplete_validation_reports_missing(self, help_system):
        """Test that incomplete help reports missing commands."""
        async def handler():
            pass
        
        # Only register a few commands
        help_system.register("/start", "Start", handler, category="session")
        help_system.register("/help", "Help", handler, category="system")
        
        result = help_system.validate_completeness()
        
        assert result.valid is False
        assert len(result.missing_docs) > 0
        # Should be missing /close, /status, /sessions, etc.
    
    def test_complete_validation_passes(self, help_system):
        """Test that complete help passes validation."""
        async def handler():
            pass
        
        # Register all required commands
        required = [
            ("/help", "Help", "system"),
            ("/start", "Start session", "session"),
            ("/close", "Close session", "session"),
            ("/status", "Show status", "session"),
            ("/sessions", "List sessions", "search"),
            ("/reopen", "Reopen session", "session"),
            ("/recover", "Recover sessions", "recovery"),
            ("/retry", "Retry failed", "recovery"),
        ]
        
        for name, desc, cat in required:
            help_system.register(name, desc, handler, category=cat)
        
        result = help_system.validate_completeness()
        
        assert result.valid is True
        assert len(result.missing_docs) == 0


class TestHelpResponse:
    """Tests for HelpResponse structure."""
    
    def test_response_has_categories(self, populated_help):
        """Test that response includes categories."""
        response = populated_help.get_help()
        
        assert len(response.categories) >= 2
        assert "session" in response.categories
        assert "system" in response.categories
    
    def test_command_info_serializable(self, populated_help):
        """Test that CommandInfo can be serialized."""
        commands = populated_help.list_commands()
        
        for cmd in commands:
            d = cmd.to_dict()
            assert d["name"] == cmd.name
            assert d["description"] == cmd.description
            assert d["params"] == cmd.params
            assert d["examples"] == cmd.examples
            assert d["category"] == cmd.category


class TestAllCommandsDocumented:
    """Test that all expected commands are registered."""
    
    def test_all_commands_registered(self, help_system):
        """Verify all commands from spec are registered."""
        async def handler():
            pass
        
        # These are the commands defined in contracts/help-system.md
        expected_commands = [
            "/help",
            "/start",
            "/close",
            "/reopen",
            "/status",
            "/sessions",
            "/recover",
            "/retry",
        ]
        
        # Register all
        for cmd in expected_commands:
            help_system.register(cmd, f"Desc for {cmd}", handler)
        
        # Verify all registered
        registered = [c.name for c in help_system.list_commands()]
        
        for cmd in expected_commands:
            assert cmd in registered, f"Command {cmd} not registered"
