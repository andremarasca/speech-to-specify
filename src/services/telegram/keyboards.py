"""Keyboard builder module for Telegram inline keyboards.

Per plan.md for 005-telegram-ux-overhaul.

This module provides builders for all inline keyboard types used
in the Telegram UX. All button labels are sourced from messages.py
to comply with Constitution Principle V (Externalized Configuration).
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from src.models.ui_state import (
    KeyboardType,
    ConfirmationContext,
    ConfirmationOption,
)
from src.models.search_result import SearchResult
from src.lib.messages import (
    get_button_label,
    BUTTON_FINALIZE,
    BUTTON_FINALIZE_SIMPLIFIED,
    BUTTON_STATUS,
    BUTTON_STATUS_SIMPLIFIED,
    BUTTON_HELP,
    BUTTON_HELP_SIMPLIFIED,
    BUTTON_CANCEL,
    BUTTON_CANCEL_SIMPLIFIED,
    BUTTON_RETRY,
    BUTTON_RETRY_SIMPLIFIED,
    BUTTON_VIEW_FULL,
    BUTTON_VIEW_FULL_SIMPLIFIED,
    BUTTON_SEARCH,
    BUTTON_SEARCH_SIMPLIFIED,
    BUTTON_PIPELINE,
    BUTTON_PIPELINE_SIMPLIFIED,
    BUTTON_PREVIOUS,
    BUTTON_PREVIOUS_SIMPLIFIED,
    BUTTON_NEXT,
    BUTTON_NEXT_SIMPLIFIED,
    BUTTON_CLOSE,
    BUTTON_CLOSE_SIMPLIFIED,
    BUTTON_CONTINUE_WAIT,
    BUTTON_CONTINUE_WAIT_SIMPLIFIED,
    BUTTON_FINALIZE_CURRENT,
    BUTTON_FINALIZE_CURRENT_SIMPLIFIED,
    BUTTON_START_NEW,
    BUTTON_START_NEW_SIMPLIFIED,
    BUTTON_RETURN_CURRENT,
    BUTTON_RETURN_CURRENT_SIMPLIFIED,
    BUTTON_RESUME,
    BUTTON_RESUME_SIMPLIFIED,
    BUTTON_DISCARD,
    BUTTON_DISCARD_SIMPLIFIED,
    BUTTON_NEW_SEARCH,
    BUTTON_NEW_SEARCH_SIMPLIFIED,
    BUTTON_TRY_AGAIN,
    BUTTON_TRY_AGAIN_SIMPLIFIED,
    BUTTON_SESSIONS_LIST,
    BUTTON_SESSIONS_LIST_SIMPLIFIED,
    BUTTON_FILES_LIST,
    BUTTON_FILES_LIST_SIMPLIFIED,
    BUTTON_TRANSCRIPTS,
    BUTTON_TRANSCRIPTS_SIMPLIFIED,
    BUTTON_PREF_SIMPLE,
    BUTTON_PREF_SIMPLE_SIMPLIFIED,
    BUTTON_PREF_NORMAL,
    BUTTON_PREF_NORMAL_SIMPLIFIED,
    BUTTON_PREF_TOGGLE,
    BUTTON_PREF_TOGGLE_SIMPLIFIED,
    BUTTON_REOPEN_SESSION_PREFIX,
    BUTTON_REOPEN_MENU,
    BUTTON_REOPEN_MENU_SIMPLIFIED,
    BUTTON_FINALIZE,
    BUTTON_FINALIZE_SIMPLIFIED,
    BUTTON_VIEW_FULL,
    BUTTON_VIEW_FULL_SIMPLIFIED,
)


def build_keyboard(
    keyboard_type: KeyboardType,
    simplified: bool = False,
    **kwargs,
) -> InlineKeyboardMarkup:
    """Build an inline keyboard for the specified type.
    
    Args:
        keyboard_type: Type of keyboard to build
        simplified: Use simplified button labels (no emojis)
        **kwargs: Additional arguments for specific keyboard types
            - confirmation_context: ConfirmationContext for CONFIRMATION type
            - current_page: Current page for PAGINATION type
            - total_pages: Total pages for PAGINATION type
            
    Returns:
        InlineKeyboardMarkup for use with Telegram API
    """
    builders = {
        KeyboardType.SESSION_ACTIVE: _build_session_active,
        KeyboardType.SESSION_EMPTY: _build_session_empty,
        KeyboardType.PROCESSING: _build_processing,
        KeyboardType.RESULTS: _build_results,
        KeyboardType.CONFIRMATION: _build_confirmation,
        KeyboardType.SESSION_CONFLICT: _build_session_conflict,
        KeyboardType.ERROR_RECOVERY: _build_error_recovery,
        KeyboardType.PAGINATION: _build_pagination,
        KeyboardType.HELP_CONTEXT: _build_help_context,
        KeyboardType.TIMEOUT: _build_timeout,
        KeyboardType.SEARCH_RESULTS: _build_search_results,
        KeyboardType.SEARCH_NO_RESULTS: _build_search_no_results,
    }
    
    builder = builders.get(keyboard_type)
    if builder is None:
        raise ValueError(f"Unknown keyboard type: {keyboard_type}")
    
    return builder(simplified=simplified, **kwargs)


def _build_session_active(simplified: bool = False, **kwargs) -> InlineKeyboardMarkup:
    """Build keyboard for active session (Finalize, Status, Help)."""
    finalize = BUTTON_FINALIZE_SIMPLIFIED if simplified else BUTTON_FINALIZE
    status = BUTTON_STATUS_SIMPLIFIED if simplified else BUTTON_STATUS
    help_btn = BUTTON_HELP_SIMPLIFIED if simplified else BUTTON_HELP
    
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(finalize, callback_data="action:finalize"),
            InlineKeyboardButton(status, callback_data="action:status"),
        ],
        [
            InlineKeyboardButton(help_btn, callback_data="action:help"),
        ],
    ])


def _build_session_empty(simplified: bool = False, **kwargs) -> InlineKeyboardMarkup:
    """Build keyboard for empty session (Help only)."""
    help_btn = BUTTON_HELP_SIMPLIFIED if simplified else BUTTON_HELP
    
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(help_btn, callback_data="action:help")],
    ])


def _build_processing(simplified: bool = False, **kwargs) -> InlineKeyboardMarkup:
    """Build keyboard for processing (Cancel only)."""
    cancel = BUTTON_CANCEL_SIMPLIFIED if simplified else BUTTON_CANCEL
    
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(cancel, callback_data="action:cancel_operation")],
    ])


def _build_results(simplified: bool = False, **kwargs) -> InlineKeyboardMarkup:
    """Build keyboard for results (View Full, Search, Pipeline)."""
    view_full = BUTTON_VIEW_FULL_SIMPLIFIED if simplified else BUTTON_VIEW_FULL
    search = BUTTON_SEARCH_SIMPLIFIED if simplified else BUTTON_SEARCH
    pipeline = BUTTON_PIPELINE_SIMPLIFIED if simplified else BUTTON_PIPELINE
    help_btn = BUTTON_HELP_SIMPLIFIED if simplified else BUTTON_HELP
    
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(view_full, callback_data="action:view_full"),
            InlineKeyboardButton(search, callback_data="action:search"),
        ],
        [
            InlineKeyboardButton(pipeline, callback_data="action:pipeline"),
            InlineKeyboardButton(help_btn, callback_data="action:help"),
        ],
    ])


def _build_confirmation(
    simplified: bool = False,
    confirmation_context: ConfirmationContext | None = None,
    **kwargs,
) -> InlineKeyboardMarkup:
    """Build keyboard for confirmation dialog (dynamic options)."""
    if confirmation_context is None:
        # Return a simple dismiss button if no context
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("OK", callback_data="action:dismiss")],
        ])
    
    # Build buttons from confirmation options
    buttons = []
    row = []
    for i, option in enumerate(confirmation_context.options):
        button = InlineKeyboardButton(
            option.label,
            callback_data=option.callback_data,
        )
        row.append(button)
        
        # Create rows of 2 buttons
        if len(row) == 2:
            buttons.append(row)
            row = []
    
    # Add remaining button if odd number
    if row:
        buttons.append(row)
    
    return InlineKeyboardMarkup(buttons)


def _build_session_conflict(simplified: bool = False, **kwargs) -> InlineKeyboardMarkup:
    """Build keyboard for session conflict (Finalize Current, Start New, Return)."""
    finalize_current = BUTTON_FINALIZE_CURRENT_SIMPLIFIED if simplified else BUTTON_FINALIZE_CURRENT
    start_new = BUTTON_START_NEW_SIMPLIFIED if simplified else BUTTON_START_NEW
    return_current = BUTTON_RETURN_CURRENT_SIMPLIFIED if simplified else BUTTON_RETURN_CURRENT
    help_btn = BUTTON_HELP_SIMPLIFIED if simplified else BUTTON_HELP
    
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(finalize_current, callback_data="confirm:session_conflict:finalize"),
            InlineKeyboardButton(start_new, callback_data="confirm:session_conflict:new"),
        ],
        [
            InlineKeyboardButton(return_current, callback_data="confirm:session_conflict:return"),
            InlineKeyboardButton(help_btn, callback_data="action:help"),
        ],
    ])


def _build_error_recovery(simplified: bool = False, **kwargs) -> InlineKeyboardMarkup:
    """Build keyboard for error recovery (Retry, Cancel, Help)."""
    retry = BUTTON_RETRY_SIMPLIFIED if simplified else BUTTON_RETRY
    cancel = BUTTON_CANCEL_SIMPLIFIED if simplified else BUTTON_CANCEL
    help_btn = BUTTON_HELP_SIMPLIFIED if simplified else BUTTON_HELP
    
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(retry, callback_data="retry:last_action"),
            InlineKeyboardButton(cancel, callback_data="action:cancel"),
        ],
        [
            InlineKeyboardButton(help_btn, callback_data="action:help"),
        ],
    ])


def _build_pagination(
    simplified: bool = False,
    current_page: int = 1,
    total_pages: int = 1,
    **kwargs,
) -> InlineKeyboardMarkup:
    """Build keyboard for pagination (Previous, Next, Close)."""
    previous = BUTTON_PREVIOUS_SIMPLIFIED if simplified else BUTTON_PREVIOUS
    next_btn = BUTTON_NEXT_SIMPLIFIED if simplified else BUTTON_NEXT
    close = BUTTON_CLOSE_SIMPLIFIED if simplified else BUTTON_CLOSE
    
    buttons = []
    nav_row = []
    
    # Add Previous button if not on first page
    if current_page > 1:
        nav_row.append(
            InlineKeyboardButton(previous, callback_data=f"page:{current_page - 1}")
        )
    
    # Add page indicator
    nav_row.append(
        InlineKeyboardButton(f"{current_page}/{total_pages}", callback_data="page:current")
    )
    
    # Add Next button if not on last page
    if current_page < total_pages:
        nav_row.append(
            InlineKeyboardButton(next_btn, callback_data=f"page:{current_page + 1}")
        )
    
    buttons.append(nav_row)
    buttons.append([InlineKeyboardButton(close, callback_data="action:close")])
    
    return InlineKeyboardMarkup(buttons)


def _build_help_context(simplified: bool = False, **kwargs) -> InlineKeyboardMarkup:
    """Build keyboard for help context (Back)."""
    close = BUTTON_CLOSE_SIMPLIFIED if simplified else BUTTON_CLOSE
    
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(close, callback_data="action:close_help")],
    ])


def _build_timeout(simplified: bool = False, **kwargs) -> InlineKeyboardMarkup:
    """Build keyboard for timeout warning (Continue, Cancel)."""
    continue_wait = BUTTON_CONTINUE_WAIT_SIMPLIFIED if simplified else BUTTON_CONTINUE_WAIT
    cancel = BUTTON_CANCEL_SIMPLIFIED if simplified else BUTTON_CANCEL
    help_btn = BUTTON_HELP_SIMPLIFIED if simplified else BUTTON_HELP
    
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(continue_wait, callback_data="action:continue_wait"),
            InlineKeyboardButton(cancel, callback_data="action:cancel_operation"),
        ],
        [
            InlineKeyboardButton(help_btn, callback_data="action:help"),
        ],
    ])


def build_recovery_keyboard(simplified: bool = False) -> InlineKeyboardMarkup:
    """Build keyboard for orphaned session recovery prompt.
    
    Args:
        simplified: Use simplified button labels (no emojis)
        
    Returns:
        InlineKeyboardMarkup with Resume/Finalize/Discard options
    """
    resume = BUTTON_RESUME_SIMPLIFIED if simplified else BUTTON_RESUME
    finalize = BUTTON_FINALIZE_SIMPLIFIED if simplified else BUTTON_FINALIZE
    discard = BUTTON_DISCARD_SIMPLIFIED if simplified else BUTTON_DISCARD
    help_btn = BUTTON_HELP_SIMPLIFIED if simplified else BUTTON_HELP
    
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(resume, callback_data="recover:resume_session"),
            InlineKeyboardButton(finalize, callback_data="recover:finalize_orphan"),
        ],
        [
            InlineKeyboardButton(discard, callback_data="recover:discard_orphan"),
            InlineKeyboardButton(help_btn, callback_data="action:help"),
        ],
    ])


def keyboard_has_help_button(keyboard: InlineKeyboardMarkup) -> bool:
    """Check if a keyboard includes a help button.
    
    Per FR-008: All inline keyboard interactions must include contextual help option.
    
    Args:
        keyboard: The keyboard to check
        
    Returns:
        True if help button is present
    """
    for row in keyboard.inline_keyboard:
        for button in row:
            if button.callback_data == "action:help":
                return True
    return False


# =============================================================================
# Search Keyboard Builders (006-semantic-session-search)
# =============================================================================


def _build_search_results(
    simplified: bool = False,
    results: list[SearchResult] | None = None,
    **kwargs,
) -> InlineKeyboardMarkup:
    """Build keyboard for search results with dynamic session buttons.
    
    Per plan.md for 006-semantic-session-search.
    
    Args:
        simplified: Use simplified button labels (no emojis)
        results: List of SearchResult objects to display as buttons
        
    Returns:
        InlineKeyboardMarkup with session buttons and footer actions
    """
    return build_search_results_keyboard(results or [], simplified)


def _build_search_no_results(simplified: bool = False, **kwargs) -> InlineKeyboardMarkup:
    """Build keyboard for no search results."""
    return build_no_results_keyboard(simplified)


def build_search_results_keyboard(
    results: list[SearchResult],
    simplified: bool = False,
) -> InlineKeyboardMarkup:
    """Build keyboard for search results with dynamic session buttons.
    
    Per data-model.md for 006-semantic-session-search.
    
    Args:
        results: List of SearchResult objects to display
        simplified: Use simplified button labels (no emojis)
        
    Returns:
        InlineKeyboardMarkup with session buttons and footer actions
    """
    buttons = []
    
    for result in results:
        if simplified:
            label = f"{result.session_name} ({result.relevance_score:.0%})"
        else:
            label = f"📁 {result.session_name} ({result.relevance_score:.0%})"
        
        # Truncate label if too long for Telegram (64 char max for callback_data)
        if len(label) > 40:
            label = label[:37] + "..."
        
        callback_data = f"search:select:{result.session_id}"
        buttons.append([InlineKeyboardButton(label, callback_data=callback_data)])
    
    # Footer row with New Search and Close buttons
    new_search = BUTTON_NEW_SEARCH_SIMPLIFIED if simplified else BUTTON_NEW_SEARCH
    close = BUTTON_CLOSE_SIMPLIFIED if simplified else BUTTON_CLOSE
    buttons.append([
        InlineKeyboardButton(new_search, callback_data="action:search"),
        InlineKeyboardButton(close, callback_data="action:close"),
    ])
    
    return InlineKeyboardMarkup(buttons)


def build_no_results_keyboard(simplified: bool = False) -> InlineKeyboardMarkup:
    """Build keyboard for no search results.
    
    Per data-model.md for 006-semantic-session-search.
    
    Args:
        simplified: Use simplified button labels (no emojis)
        
    Returns:
        InlineKeyboardMarkup with New Search and Close buttons
    """
    new_search = BUTTON_NEW_SEARCH_SIMPLIFIED if simplified else BUTTON_NEW_SEARCH
    close = BUTTON_CLOSE_SIMPLIFIED if simplified else BUTTON_CLOSE
    
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(new_search, callback_data="action:search"),
            InlineKeyboardButton(close, callback_data="action:close"),
        ]
    ])


def build_session_load_error_keyboard(simplified: bool = False) -> InlineKeyboardMarkup:
    """Build keyboard for session load error during search restoration.
    
    Per data-model.md for 006-semantic-session-search.
    
    Args:
        simplified: Use simplified button labels (no emojis)
        
    Returns:
        InlineKeyboardMarkup with Try Again and Close buttons
    """
    try_again = BUTTON_TRY_AGAIN_SIMPLIFIED if simplified else BUTTON_TRY_AGAIN
    close = BUTTON_CLOSE_SIMPLIFIED if simplified else BUTTON_CLOSE
    
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(try_again, callback_data="action:search"),
            InlineKeyboardButton(close, callback_data="action:close"),
        ]
    ])


def build_sessions_list_keyboard(simplified: bool = False) -> InlineKeyboardMarkup:
    """Constrói teclado com link para listar sessões."""
    label = BUTTON_SESSIONS_LIST_SIMPLIFIED if simplified else BUTTON_SESSIONS_LIST
    
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(label, callback_data="action:list_sessions")]
    ])


def build_files_list_keyboard(simplified: bool = False) -> InlineKeyboardMarkup:
    """Constrói teclado com link para listar arquivos."""
    label = BUTTON_FILES_LIST_SIMPLIFIED if simplified else BUTTON_FILES_LIST
    
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(label, callback_data="action:list_files")]
    ])


def build_session_actions_keyboard(simplified: bool = False) -> InlineKeyboardMarkup:
    """Constrói teclado com ações de sessão (Listar Arquivos, Ver Transcrições)."""
    files_label = BUTTON_FILES_LIST_SIMPLIFIED if simplified else BUTTON_FILES_LIST
    transcripts_label = BUTTON_TRANSCRIPTS_SIMPLIFIED if simplified else BUTTON_TRANSCRIPTS
    
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(files_label, callback_data="action:list_files"),
            InlineKeyboardButton(transcripts_label, callback_data="action:view_full"),
        ]
    ])


def build_finalize_keyboard(simplified: bool = False) -> InlineKeyboardMarkup:
    """Constrói teclado apenas com botão de finalizar."""
    label = BUTTON_FINALIZE_SIMPLIFIED if simplified else BUTTON_FINALIZE
    
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(label, callback_data="action:finalize")]
    ])


def build_transcripts_keyboard(simplified: bool = False) -> InlineKeyboardMarkup:
    """Constrói teclado com botão de ver transcrições."""
    label = BUTTON_TRANSCRIPTS_SIMPLIFIED if simplified else BUTTON_TRANSCRIPTS
    
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(label, callback_data="action:view_full")]
    ])


def build_preferences_keyboard(simplified: bool = False) -> InlineKeyboardMarkup:
    """Constrói teclado de preferências."""
    simple = BUTTON_PREF_SIMPLE_SIMPLIFIED if simplified else BUTTON_PREF_SIMPLE
    normal = BUTTON_PREF_NORMAL_SIMPLIFIED if simplified else BUTTON_PREF_NORMAL
    toggle = BUTTON_PREF_TOGGLE_SIMPLIFIED if simplified else BUTTON_PREF_TOGGLE
    
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(simple, callback_data="pref:simple"),
            InlineKeyboardButton(normal, callback_data="pref:normal"),
        ],
        [InlineKeyboardButton(toggle, callback_data="pref:toggle")]
    ])


def build_sessions_list_actions_keyboard(simplified: bool = False) -> InlineKeyboardMarkup:
    """Constrói teclado de ações gerais para lista de sessões."""
    transcripts = BUTTON_TRANSCRIPTS_SIMPLIFIED if simplified else BUTTON_TRANSCRIPTS
    files = BUTTON_FILES_LIST_SIMPLIFIED if simplified else BUTTON_FILES_LIST
    reopen = BUTTON_REOPEN_MENU_SIMPLIFIED if simplified else BUTTON_REOPEN_MENU
    
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(transcripts, callback_data="action:view_full"),
            InlineKeyboardButton(files, callback_data="action:list_files"),
        ],
        [
            InlineKeyboardButton(reopen, callback_data="action:reopen_menu"),
        ]
    ])


def build_reopen_sessions_keyboard(sessions: list) -> InlineKeyboardMarkup:
    """
    Builds an inline keyboard where each button represents a session to reopen.
    """
    buttons = []
    for session in sessions:
        name = session.intelligible_name if session.intelligible_name else session.id
        label = f"{BUTTON_REOPEN_SESSION_PREFIX} {name} | {session.audio_count} áudios"
        buttons.append([
            InlineKeyboardButton(label, callback_data=f"action:reopen_session:{session.id}")
        ])
    
    return InlineKeyboardMarkup(buttons)


def build_file_list_keyboard(files: list[tuple[str, str, int]]) -> InlineKeyboardMarkup:
    """
    Builds an inline keyboard where each button represents a file to download.
    
    Args:
        files: List of tuples (emoji, relative_path, size_bytes)
    """
    buttons = []
    for emoji, path, size in files:
        # Truncate path if too long for button
        display_name = path.split('/')[-1]
        label = f"{emoji} {display_name}"
        
        # Callback data limit is 64 bytes. We need to be careful.
        # We'll use a prefix 'get:' and the path.
        # If path is too long, we might need a different strategy (e.g. index),
        # but for now let's try direct path.
        callback_data = f"action:get_file:{path}"
        
        # Telegram callback_data limit check (64 bytes)
        if len(callback_data.encode('utf-8')) > 64:
            # Fallback: just show name, user has to type /get
            # Or implement a file ID mapping system (too complex for now)
            continue
            
        buttons.append([
            InlineKeyboardButton(label, callback_data=callback_data)
        ])
    
    return InlineKeyboardMarkup(buttons)
