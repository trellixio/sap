"""
FastAPI.

This package regroups all common helpers exclusively for FastAPI.
Learn more about FastAPI: https://github.com/tiangolo/fastapi
"""

from .utils import Flash, FlashLevel, pydantic_format_errors
from .serializers import ObjectSerializer

__all__ = [
    "Flash",
    "FlashLevel",
    "pydantic_format_errors",
    "ObjectSerializer",
]
