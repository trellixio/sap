"""
Beanie.

This package regroups all common helpers exclusively for Beanie.
Learn more about https://github.com/roman-right/beanie
"""
from .document import Document
from .models import DocMeta, Link
from .query import prefetch_related, prefetch_related_children, prepare_search_string

__all__ = [
    "DocMeta",
    "Link",
    "Document",
    "prefetch_related",
    "prefetch_related_children",
    "prepare_search_string",
]
