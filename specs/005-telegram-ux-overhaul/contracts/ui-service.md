# Contract: UIService

**Feature**: 005-telegram-ux-overhaul  
**Module**: `src/services/telegram/ui_service.py`  
**Date**: 2025-12-19

## Purpose

UIService is the presentation layer adapter that generates Telegram-specific UI elements (inline keyboards, formatted messages) while delegating business logic to existing services. It enforces the separation between channel (Telegram) and processing core.

## Interface

```python
from abc import ABC, abstractmethod
from telegram import Message, InlineKeyboardMarkup
from src.models.session import Session
from src.models.ui_state import UIState, UIPreferences, KeyboardType, ProgressState

class UIServiceProtocol(ABC):
    """Protocol for Telegram UI presentation layer."""
    
    @abstractmethod
    async def send_session_created(
        self, 
        chat_id: int, 
        session: Session, 
        audio_count: int
    ) -> Message:
        """
        Send session creation confirmation with inline keyboard.
        
        Args:
            chat_id: Telegram chat ID
            session: Newly created session
            audio_count: Number of audio files received
            
        Returns:
            Sent message (for tracking message_id)
        """
        ...
    
    @abstractmethod
    async def send_audio_received(
        self, 
        chat_id: int, 
        audio_number: int,
        session_name: str
    ) -> Message:
        """
        Send brief audio receipt confirmation.
        
        Args:
            chat_id: Telegram chat ID
            audio_number: Sequence number of received audio
            session_name: Current session name for context
            
        Returns:
            Sent message
        """
        ...
    
    @abstractmethod
    async def update_status_message(
        self, 
        message: Message, 
        session: Session,
        keyboard_type: KeyboardType
    ) -> None:
        """
        Edit existing status message with updated content.
        
        Args:
            message: Message to edit
            session: Current session state
            keyboard_type: Type of keyboard to display
        """
        ...
    
    @abstractmethod
    async def send_progress(
        self, 
        chat_id: int, 
        progress: ProgressState,
        preferences: UIPreferences
    ) -> Message:
        """
        Send or update progress message.
        
        Args:
            chat_id: Telegram chat ID
            progress: Current progress state
            preferences: User UI preferences
            
        Returns:
            Progress message (for subsequent updates)
        """
        ...
    
    @abstractmethod
    async def update_progress(
        self, 
        message: Message, 
        progress: ProgressState,
        preferences: UIPreferences
    ) -> None:
        """
        Edit existing progress message.
        
        Args:
            message: Message to edit
            progress: Updated progress state
            preferences: User UI preferences
        """
        ...
    
    @abstractmethod
    async def send_confirmation_dialog(
        self, 
        chat_id: int, 
        context: "ConfirmationContext"
    ) -> Message:
        """
        Send confirmation dialog with options.
        
        Args:
            chat_id: Telegram chat ID
            context: Confirmation context with options
            
        Returns:
            Dialog message
        """
        ...
    
    @abstractmethod
    async def send_results(
        self, 
        chat_id: int, 
        session: Session,
        transcription_preview: str
    ) -> Message:
        """
        Send transcription results with action buttons.
        
        Args:
            chat_id: Telegram chat ID
            session: Completed session
            transcription_preview: First N characters of transcription
            
        Returns:
            Results message
        """
        ...
    
    @abstractmethod
    async def send_paginated_text(
        self, 
        chat_id: int, 
        text: str,
        page: int = 1,
        title: str = ""
    ) -> Message:
        """
        Send long text with pagination controls.
        
        Args:
            chat_id: Telegram chat ID
            text: Full text to paginate
            page: Current page (1-indexed)
            title: Optional title for message
            
        Returns:
            Paginated message
        """
        ...
    
    @abstractmethod
    async def send_contextual_help(
        self, 
        chat_id: int, 
        context: KeyboardType,
        preferences: UIPreferences
    ) -> Message:
        """
        Send help text relevant to current context.
        
        Args:
            chat_id: Telegram chat ID
            context: Current UI context
            preferences: User UI preferences
            
        Returns:
            Help message
        """
        ...
    
    @abstractmethod
    def build_keyboard(
        self, 
        keyboard_type: KeyboardType,
        context: dict | None = None
    ) -> InlineKeyboardMarkup:
        """
        Build inline keyboard for given type.
        
        Args:
            keyboard_type: Type of keyboard to build
            context: Optional context for dynamic keyboards
            
        Returns:
            Configured InlineKeyboardMarkup
        """
        ...
```

## Callback Data Format

All inline keyboard buttons use structured callback data:

```
{namespace}:{action}[:{param}]

Examples:
- action:finalize
- action:status
- action:help
- confirm:session_conflict:finalize_new
- confirm:session_conflict:cancel
- page:transcription:2
- retry:save_audio
- pref:simplified_ui:toggle
```

## Dependencies

- `telegram.Bot` for sending/editing messages
- `Session` model (read-only)
- `UIPreferences`, `ProgressState` from data-model
- Message templates from `src/lib/messages.py`

## Error Handling

UIService does not handle business logic errors. It receives already-formatted `UserFacingError` from `ErrorPresentationLayer` and renders them.

## Thread Safety

UIService methods are async and stateless. UIState is managed by the caller (bot handlers).

## Testing Contract

```python
# tests/contract/test_ui_service.py

async def test_send_session_created_includes_keyboard():
    """Session creation message must include inline keyboard."""
    
async def test_send_session_created_respects_preferences():
    """Simplified UI preference removes decorative emojis."""

async def test_build_keyboard_session_active():
    """SESSION_ACTIVE keyboard has finalize, status, help buttons."""

async def test_build_keyboard_error_recovery():
    """ERROR_RECOVERY keyboard has retry and cancel buttons."""

async def test_update_progress_throttled():
    """Progress updates respect minimum interval."""

async def test_send_paginated_text_respects_limit():
    """Paginated messages stay within Telegram character limit."""
```
