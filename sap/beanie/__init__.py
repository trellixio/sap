"""
Beanie.

This package regroups all common helpers exclusively for Beanie.
Learn more about https://github.com/roman-right/beanie
"""

from .document import Document
from .link import Link
from .patch import Initializer
from .query import prefetch_related, prefetch_related_children, prepare_search_string

__all__ = [
    "Link",
    "Document",
    "prefetch_related",
    "prefetch_related_children",
    "prepare_search_string",
    # Patching
    "Initializer",
]
