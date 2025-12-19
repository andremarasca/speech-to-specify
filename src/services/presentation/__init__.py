"""Presentation layer services for Telegram UX.

This package contains services for UI presentation, error handling,
and progress reporting. All services in this layer are adapters that
transform business logic output into Telegram-compatible formats.

Per plan.md for 005-telegram-ux-overhaul:
- error_handler.py: ErrorPresentationLayer for humanized error messages
- progress.py: ProgressReporter for real-time progress feedback
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.services.presentation.error_handler import ErrorPresentationLayer
    from src.services.presentation.progress import ProgressReporter

__all__ = [
    "ErrorPresentationLayer",
    "ProgressReporter",
]
