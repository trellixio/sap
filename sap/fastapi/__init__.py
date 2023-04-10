"""
FastAPI.

This package regroups all common helpers exclusively for FastAPI.
Learn more about FastAPI: https://github.com/tiangolo/fastapi
"""

from .exceptions import Object404Error, Validation422Error
from .serializers import ObjectSerializer, WriteObjectSerializer
from .utils import Flash, FlashLevel, pydantic_format_errors
from .forms import validate_form, FormData

__all__ = [
    "Flash",
    "FlashLevel",
    "pydantic_format_errors",
    # Serializers
    "ObjectSerializer",
    "WriteObjectSerializer",
    # Exceptions
    "Validation422Error",
    "Object404Error",
    # Forms
    "validate_form",
    "FormData",
]
