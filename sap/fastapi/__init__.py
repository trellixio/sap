"""
FastAPI.

This package regroups all common helpers exclusively for FastAPI.
Learn more about FastAPI: https://github.com/tiangolo/fastapi
"""

from .serializers import ObjectSerializer
from .utils import Flash, FlashLevel, pydantic_format_errors

__all__ = [
    "Flash",
    "FlashLevel",
    "pydantic_format_errors",
    "ObjectSerializer",
]
