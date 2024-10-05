"""
Link.

Update beanie link with better object mapping.
"""

from __future__ import annotations

from typing import Optional, Type

import bson

import beanie

from .document import DocT

# if TYPE_CHECKING:


# else:
#     from beanie import Link

# T = TypeVar("T")


class DBRef(bson.DBRef):
    """Subclass DBref to add typing for id."""

    id: beanie.PydanticObjectId


class Link(beanie.Link[DocT]):
    """Fix typing issue mypy when querying related fields."""

    # id: beanie.PydanticObjectId
    ref: DBRef
    document_class: Type[DocT]
    doc: Optional[DocT]  # This is the prefetched T document

    def __init__(self, ref: DBRef, document_class: Type[DocT]) -> None:
        """Initialize object."""
        super().__init__(ref=ref, document_class=document_class)
        self.id = ref.id
        self.doc = None

    async def fetch(self, fetch_links: bool = False) -> DocT:
        """Overwrite fetch to force missing doc to raise error."""
        if self.doc:
            return self.doc
        self.doc = await self.document_class.get_or_404(self.ref.id, with_children=True, fetch_links=fetch_links)
        return self.doc


# Link = beanie.Link
# Link.__init__ = MLink.__init__
# Link.fetch = MLink.fetch
# Link = MLink
