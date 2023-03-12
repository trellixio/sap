"""
Beanie.

This package regroups all common helpers exclusively for Beanie.
Learn more about https://github.com/roman-right/beanie
"""
from .document import Document
from .models import DocMeta, Link

__all__ = [
    "DocMeta",
    "Link",
    "Document",
]
