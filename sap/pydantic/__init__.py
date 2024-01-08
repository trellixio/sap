"""
Pydantic.

This package regroups all common helpers to work with Pydantic
"""
from datetime import datetime, timezone


def datetime_utcnow() -> datetime:
    """Replace deprecated datetime.utcnow."""
    return datetime.now(timezone.utc)
