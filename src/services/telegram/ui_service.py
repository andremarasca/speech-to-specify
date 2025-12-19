"""UIService for Telegram presentation layer.

Per contracts/ui-service.md for 005-telegram-ux-overhaul.

UIService is the presentation layer adapter that generates Telegram-specific
UI elements (inline keyboards, formatted messages) while delegating business
logic to existing services. It enforces separation between channel (Telegram)
and processing core.
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Optional

from telegram import Bot, Message, InlineKeyboardMarkup

from src.models.session import Session
from src.models.ui_state import (
    UIState,
    UIPreferences,
    KeyboardType,
    ProgressState,
    ConfirmationContext,
)
from src.services.telegram.keyboards import build_keyboard, build_recovery_keyboard
from src.lib.messages import (
    get_message,
    get_button_label,
    get_help_message,
    SESSION_CREATED,
    SESSION_CREATED_SIMPLIFIED,
    AUDIO_RECEIVED,
    AUDIO_RECEIVED_SIMPLIFIED,
    SESSION_FINALIZED,
    SESSION_FINALIZED_SIMPLIFIED,
    SESSION_STATUS,
    SESSION_STATUS_SIMPLIFIED,
    NO_ACTIVE_SESSION,
    NO_ACTIVE_SESSION_SIMPLIFIED,
    PROGRESS_STARTED,
    PROGRESS_STARTED_SIMPLIFIED,
    PROGRESS_UPDATE,
    PROGRESS_UPDATE_SIMPLIFIED,
    PROGRESS_COMPLETE,
    PROGRESS_COMPLETE_SIMPLIFIED,
    RESULTS_HEADER,
    RESULTS_HEADER_SIMPLIFIED,
    RECOVERY_PROMPT,
    RECOVERY_PROMPT_SIMPLIFIED,
    CONFIRMATION_MESSAGE,
    CONFIRMATION_MESSAGE_SIMPLIFIED,
)
from src.lib.config import get_ui_config


class UIServiceProtocol(ABC):
    """Protocol for Telegram UI presentation layer."""

    @abstractmethod
    async def send_session_created(
        self,
        chat_id: int,
        session: Session,
        audio_count: int,
    ) -> Message:
        """Send session creation confirmation with inline keyboard."""
        ...

    @abstractmethod
    async def send_audio_received(
        self,
        chat_id: int,
        audio_number: int,
        session_name: str,
    ) -> Message:
        """Send brief audio receipt confirmation."""
        ...

    @abstractmethod
    async def update_status_message(
        self,
        message: Message,
        session: Session,
        keyboard_type: KeyboardType,
    ) -> None:
        """Edit existing status message with updated content."""
        ...

    @abstractmethod
    async def send_progress(
        self,
        chat_id: int,
        progress: ProgressState,
        preferences: UIPreferences,
    ) -> Message:
        """Send or update progress message."""
        ...

    @abstractmethod
    async def update_progress(
        self,
        message: Message,
        progress: ProgressState,
        preferences: UIPreferences,
    ) -> None:
        """Edit existing progress message."""
        ...

    @abstractmethod
    async def send_confirmation_dialog(
        self,
        chat_id: int,
        context: ConfirmationContext,
    ) -> Message:
        """Send confirmation dialog with options."""
        ...

    @abstractmethod
    async def send_results(
        self,
        chat_id: int,
        session: Session,
        transcription_preview: str,
    ) -> Message:
        """Send transcription results with action buttons."""
        ...

    @abstractmethod
    async def send_paginated_text(
        self,
        chat_id: int,
        text: str,
        page: int = 1,
        title: str = "",
    ) -> Message:
        """Send long text with pagination controls."""
        ...

    @abstractmethod
    async def send_contextual_help(
        self,
        chat_id: int,
        context: KeyboardType,
        preferences: UIPreferences,
    ) -> Message:
        """Send help text relevant to current context."""
        ...

    @abstractmethod
    async def send_recovery_prompt(
        self,
        chat_id: int,
        session: Session,
    ) -> Message:
        """Send recovery prompt for orphaned session."""
        ...

    @abstractmethod
    def build_keyboard(
        self,
        keyboard_type: KeyboardType,
        context: dict | None = None,
    ) -> InlineKeyboardMarkup:
        """Build inline keyboard for given type."""
        ...


class UIService(UIServiceProtocol):
    """Telegram UI presentation layer implementation.
    
    This service handles all UI rendering for the Telegram bot,
    including inline keyboards, formatted messages, and progress updates.
    
    Args:
        bot: Telegram Bot instance for sending messages
        preferences: Optional user UI preferences (defaults to standard)
    """

    def __init__(
        self,
        bot: Bot,
        preferences: Optional[UIPreferences] = None,
    ):
        self._bot = bot
        self._preferences = preferences or UIPreferences()
        self._config = get_ui_config()

    @property
    def simplified(self) -> bool:
        """Whether to use simplified UI (no emojis)."""
        return self._preferences.simplified_ui

    async def send_session_created(
        self,
        chat_id: int,
        session: Session,
        audio_count: int,
    ) -> Message:
        """Send session creation confirmation with inline keyboard.
        
        Args:
            chat_id: Telegram chat ID
            session: Newly created session
            audio_count: Number of audio files received
            
        Returns:
            Sent message (for tracking message_id)
        """
        # Select message template based on preferences
        template = SESSION_CREATED_SIMPLIFIED if self.simplified else SESSION_CREATED
        
        text = template.format(
            session_name=session.intelligible_name or session.id,
            audio_count=audio_count,
        )
        
        keyboard = self.build_keyboard(KeyboardType.SESSION_ACTIVE)
        
        return await self._bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=keyboard,
            parse_mode="HTML",
        )

    async def send_audio_received(
        self,
        chat_id: int,
        audio_number: int,
        session_name: str,
    ) -> Message:
        """Send brief audio receipt confirmation.
        
        Args:
            chat_id: Telegram chat ID
            audio_number: Sequence number of received audio
            session_name: Current session name for context
            
        Returns:
            Sent message
        """
        template = AUDIO_RECEIVED_SIMPLIFIED if self.simplified else AUDIO_RECEIVED
        
        text = template.format(
            sequence=audio_number,
            session_name=session_name,
        )
        
        return await self._bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode="HTML",
        )

    async def update_status_message(
        self,
        message: Message,
        session: Session,
        keyboard_type: KeyboardType,
    ) -> None:
        """Edit existing status message with updated content.
        
        Args:
            message: Message to edit
            session: Current session state
            keyboard_type: Type of keyboard to display
        """
        template = SESSION_STATUS_SIMPLIFIED if self.simplified else SESSION_STATUS
        
        text = template.format(
            session_name=session.intelligible_name or session.id,
            audio_count=len(session.audio_entries),
            created_at=session.created_at.strftime("%Y-%m-%d %H:%M"),
            state=session.state.value,
        )
        
        keyboard = self.build_keyboard(keyboard_type)
        
        await message.edit_text(
            text=text,
            reply_markup=keyboard,
            parse_mode="HTML",
        )

    async def send_progress(
        self,
        chat_id: int,
        progress: ProgressState,
        preferences: UIPreferences,
    ) -> Message:
        """Send progress message.
        
        Args:
            chat_id: Telegram chat ID
            progress: Current progress state
            preferences: User UI preferences
            
        Returns:
            Progress message (for subsequent updates)
        """
        simplified = preferences.simplified_ui
        template = PROGRESS_UPDATE_SIMPLIFIED if simplified else PROGRESS_UPDATE
        
        # Generate progress bar
        progress_bar = self._generate_progress_bar(progress.percentage)
        
        text = template.format(
            description=progress.step_description,
            progress_bar=progress_bar,
            percentage=progress.percentage,
        )
        
        keyboard = self.build_keyboard(KeyboardType.PROCESSING)
        
        return await self._bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=keyboard,
            parse_mode="HTML",
        )

    async def update_progress(
        self,
        message: Message,
        progress: ProgressState,
        preferences: UIPreferences,
    ) -> None:
        """Edit existing progress message.
        
        Args:
            message: Message to edit
            progress: Updated progress state
            preferences: User UI preferences
        """
        simplified = preferences.simplified_ui
        template = PROGRESS_UPDATE_SIMPLIFIED if simplified else PROGRESS_UPDATE
        
        # Generate progress bar
        progress_bar = self._generate_progress_bar(progress.percentage)
        
        text = template.format(
            description=progress.step_description,
            progress_bar=progress_bar,
            percentage=progress.percentage,
        )
        
        keyboard = self.build_keyboard(KeyboardType.PROCESSING)
        
        await message.edit_text(
            text=text,
            reply_markup=keyboard,
            parse_mode="HTML",
        )

    def _generate_progress_bar(self, percentage: int, width: int = 10) -> str:
        """Generate a text-based progress bar.
        
        Args:
            percentage: Progress percentage (0-100)
            width: Number of characters in bar
            
        Returns:
            Progress bar string like "▓▓▓▓░░░░░░"
        """
        filled = int(width * percentage / 100)
        empty = width - filled
        return "▓" * filled + "░" * empty

    async def send_confirmation_dialog(
        self,
        chat_id: int,
        context: ConfirmationContext,
    ) -> Message:
        """Send confirmation dialog with options.
        
        Args:
            chat_id: Telegram chat ID
            context: Confirmation context with options
            
        Returns:
            Dialog message
        """
        template = CONFIRMATION_MESSAGE_SIMPLIFIED if self.simplified else CONFIRMATION_MESSAGE
        
        # Get message from context_data or use a default
        message = context.context_data.get("message", "Por favor, confirme a ação.")
        text = template.format(message=message)
        
        keyboard = self.build_keyboard(
            KeyboardType.CONFIRMATION,
            context={"confirmation_context": context},
        )
        
        return await self._bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=keyboard,
            parse_mode="HTML",
        )

    async def send_results(
        self,
        chat_id: int,
        session: Session,
        transcription_preview: str,
    ) -> Message:
        """Send transcription results with action buttons.
        
        Args:
            chat_id: Telegram chat ID
            session: Completed session
            transcription_preview: First N characters of transcription
            
        Returns:
            Results message
        """
        template = RESULTS_HEADER_SIMPLIFIED if self.simplified else RESULTS_HEADER
        
        text = template.format(
            session_name=session.intelligible_name or session.id,
            audio_count=len(session.audio_entries),
            preview=transcription_preview,
        )
        
        keyboard = self.build_keyboard(KeyboardType.RESULTS)
        
        return await self._bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=keyboard,
            parse_mode="HTML",
        )

    async def send_paginated_text(
        self,
        chat_id: int,
        text: str,
        page: int = 1,
        title: str = "",
    ) -> Message:
        """Send long text with pagination controls.
        
        Args:
            chat_id: Telegram chat ID
            text: Full text to paginate
            page: Current page (1-indexed)
            title: Optional title for message
            
        Returns:
            Paginated message
        """
        # Calculate pagination
        max_content = self._config.message_limit - 200  # Reserve space for header/footer
        pages = self._split_text(text, max_content)
        total_pages = len(pages)
        
        # Clamp page number
        page = max(1, min(page, total_pages))
        page_content = pages[page - 1] if pages else ""
        
        # Build message text
        if title:
            message_text = f"<b>{title}</b>\n\n{page_content}"
        else:
            message_text = page_content
        
        # Add page indicator if multiple pages
        if total_pages > 1:
            message_text += f"\n\n📄 Página {page}/{total_pages}"
        
        # Build pagination keyboard if needed
        if total_pages > 1:
            keyboard = self.build_keyboard(
                KeyboardType.PAGINATION,
                context={
                    "current_page": page,
                    "total_pages": total_pages,
                },
            )
        else:
            # Single page - just close button
            keyboard = self.build_keyboard(KeyboardType.HELP_CONTEXT)
        
        return await self._bot.send_message(
            chat_id=chat_id,
            text=message_text,
            reply_markup=keyboard,
            parse_mode="HTML",
        )

    async def send_contextual_help(
        self,
        chat_id: int,
        context: KeyboardType,
        preferences: UIPreferences,
    ) -> Message:
        """Send help text relevant to current context.
        
        Args:
            chat_id: Telegram chat ID
            context: Current UI context
            preferences: User UI preferences
            
        Returns:
            Help message
        """
        # Map KeyboardType to help context string
        context_map = {
            KeyboardType.SESSION_ACTIVE: "SESSION_ACTIVE",
            KeyboardType.SESSION_EMPTY: "SESSION_EMPTY",
            KeyboardType.PROCESSING: "PROCESSING",
            KeyboardType.RESULTS: "RESULTS",
            KeyboardType.ERROR_RECOVERY: "ERROR_RECOVERY",
            KeyboardType.CONFIRMATION: "DEFAULT",
            KeyboardType.SESSION_CONFLICT: "DEFAULT",
            KeyboardType.PAGINATION: "DEFAULT",
            KeyboardType.HELP_CONTEXT: "DEFAULT",
            KeyboardType.TIMEOUT: "DEFAULT",
        }
        
        help_key = context_map.get(context, "DEFAULT")
        help_text = get_help_message(help_key, simplified=preferences.simplified_ui)
        
        keyboard = self.build_keyboard(KeyboardType.HELP_CONTEXT)
        
        return await self._bot.send_message(
            chat_id=chat_id,
            text=help_text,
            reply_markup=keyboard,
            parse_mode="HTML",
        )

    async def send_recovery_prompt(
        self,
        chat_id: int,
        session: Session,
    ) -> Message:
        """Send recovery prompt for orphaned session.
        
        Args:
            chat_id: Telegram chat ID
            session: Orphaned session to recover
            
        Returns:
            Recovery prompt message
        """
        template = RECOVERY_PROMPT_SIMPLIFIED if self.simplified else RECOVERY_PROMPT
        
        text = template.format(
            session_name=session.intelligible_name or session.id,
            audio_count=len(session.audio_entries),
            created_at=session.created_at.strftime("%Y-%m-%d %H:%M"),
        )
        
        keyboard = build_recovery_keyboard(simplified=self.simplified)
        
        return await self._bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=keyboard,
            parse_mode="HTML",
        )

    def build_keyboard(
        self,
        keyboard_type: KeyboardType,
        context: dict | None = None,
    ) -> InlineKeyboardMarkup:
        """Build inline keyboard for given type.
        
        Args:
            keyboard_type: Type of keyboard to build
            context: Optional context for dynamic keyboards
            
        Returns:
            Configured InlineKeyboardMarkup
        """
        kwargs = context or {}
        return build_keyboard(
            keyboard_type=keyboard_type,
            simplified=self.simplified,
            **kwargs,
        )

    def _split_text(self, text: str, max_length: int) -> list[str]:
        """Split text into pages of max_length.
        
        Args:
            text: Text to split
            max_length: Maximum length per page
            
        Returns:
            List of text pages
        """
        if len(text) <= max_length:
            return [text]
        
        pages = []
        current = ""
        
        # Split by paragraphs first, then by sentences
        paragraphs = text.split("\n\n")
        
        for para in paragraphs:
            if len(current) + len(para) + 2 <= max_length:
                if current:
                    current += "\n\n"
                current += para
            else:
                if current:
                    pages.append(current)
                
                # If paragraph itself is too long, split it
                if len(para) > max_length:
                    # Try splitting by sentences first
                    sentences = para.replace(". ", ".\n").split("\n")
                    current = ""
                    for sentence in sentences:
                        # If a single sentence is too long, hard split it
                        while len(sentence) > max_length:
                            if current:
                                pages.append(current)
                                current = ""
                            # Hard split at max_length
                            pages.append(sentence[:max_length])
                            sentence = sentence[max_length:]
                        
                        if len(current) + len(sentence) + 1 <= max_length:
                            if current:
                                current += " "
                            current += sentence
                        else:
                            if current:
                                pages.append(current)
                            current = sentence
                else:
                    current = para
        
        if current:
            pages.append(current)
        
        return pages if pages else [""]
