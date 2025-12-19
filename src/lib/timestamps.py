"""Timestamp and ID generation utilities."""

from datetime import datetime, timezone
from uuid import uuid4


def generate_id() -> str:
    """
    Generate a unique identifier for entities based on human-readable timestamp.

    Returns:
        str: Timestamp-based ID (e.g., "2025-12-18_14-30-00")
    """
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%d_%H-%M-%S")


def generate_uuid() -> str:
    """
    Generate a UUID4 identifier for cases requiring guaranteed uniqueness.

    Returns:
        str: UUID4 string (e.g., "550e8400-e29b-41d4-a716-446655440000")
    """
    return str(uuid4())


def generate_timestamp() -> datetime:
    """
    Generate a timezone-aware UTC timestamp.

    Returns:
        datetime: Current UTC time with timezone info
    """
    return datetime.now(timezone.utc)


def format_timestamp(dt: datetime) -> str:
    """
    Format a datetime as ISO 8601 string.

    Args:
        dt: Datetime to format

    Returns:
        str: ISO 8601 formatted string (e.g., "2024-01-15T10:30:00+00:00")
    """
    return dt.isoformat()


def parse_timestamp(iso_string: str) -> datetime:
    """
    Parse an ISO 8601 timestamp string.

    Args:
        iso_string: ISO 8601 formatted string

    Returns:
        datetime: Parsed datetime with timezone info
    """
    return datetime.fromisoformat(iso_string)
