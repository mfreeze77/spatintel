from __future__ import annotations

from datetime import UTC, datetime


def db_now() -> datetime:
    """Return an aware UTC timestamp suitable for persisted evidence."""
    return datetime.now(UTC)
