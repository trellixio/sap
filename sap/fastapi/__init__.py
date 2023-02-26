"""
FastAPI.

This package regroups all common helpers exclusively for FastAPI.
"""

from .utils import Flash, FlashLevel, pydantic_format_errors

__all__ = [
    "Flash",
    "FlashLevel",
    "pydantic_format_errors",
]
