"""
Beanie.

This package regroups all common helpers exclusively for Beanie.
Learn more about https://github.com/roman-right/beanie
"""
from .models import DocMeta, Link
from .document import Document

__all__ = [
    "DocMeta",
    "Link",
    "Document",
]
