"""
Pydantic.

This package regroups all common helpers to work with Pydantic
"""

from datetime import datetime, timezone
from typing import TypeVar

import pydantic


def datetime_utcnow() -> datetime:
    """Replace deprecated datetime.utcnow."""
    return datetime.now(timezone.utc)


ModelT = TypeVar("ModelT", bound=pydantic.BaseModel)
