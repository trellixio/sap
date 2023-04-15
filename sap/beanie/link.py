"""
Link.

Update beanie link with better object mapping.
"""
from __future__ import annotations

from typing import Type, TypeVar, Optional
from .document import DocT

import bson

import beanie

# if TYPE_CHECKING:


# else:
#     from beanie import Link

# T = TypeVar("T")


class DBRef(bson.DBRef):
    id: beanie.PydanticObjectId


class Link(beanie.Link[DocT]):
    """Fix typing issue mypy when querying related fields."""

    id: beanie.PydanticObjectId
    ref: DBRef
    model_class: Type[DocT]
    doc: Optional[DocT]  # This is the prefetched T document

    async def fetch(self, fetch_links: bool = False) -> DocT:
        return await self.model_class.get_or_404(self.ref.id, with_children=True, fetch_links=fetch_links)
