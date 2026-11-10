"""
Beanie.

This package regroups all common helpers exclusively for Beanie.
Learn more about https://github.com/roman-right/beanie

It needs the `beanie` extra: `pip install sapx[beanie]`.
"""

try:
    import beanie
except ImportError as exc:
    raise ImportError("sap.beanie needs the beanie extra: pip install 'sapx[beanie]'") from exc

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
