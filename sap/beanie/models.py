"""
Models.

Base models that can be sub-classed independently by each Trellis integration.
"""
from __future__ import annotations

import typing
from datetime import datetime

import beanie
import pydantic

if typing.TYPE_CHECKING:
    T = typing.TypeVar("T")

    class Link(beanie.Link[T]):
        """Fix typing issue mypy when querying related fields."""

        id: beanie.PydanticObjectId

else:
    from beanie import Link


class _DocMeta(pydantic.BaseModel):
    """Meta Data allowing to keep trace of Documents versioning and updates."""

    version: int = 0  # version of the document being imported
    source: typing.Optional[str]  # where the data is coming from: webhook, cron
    created: typing.Optional[datetime]  # when the document was first imported
    updated: typing.Optional[datetime]  # when the document was last updated
    deleted: typing.Optional[datetime]  # when the document was deleted, (deleted document may be retained for logging)


class DocMeta(pydantic.BaseModel):
    """Manage meta data and ensure that it's correctly set."""

    doc_meta: _DocMeta = _DocMeta()

    @pydantic.root_validator
    @classmethod
    def validate_doc_meta(cls, values: dict[str, typing.Any]) -> dict[str, typing.Any]:
        """Validate doc meta on each model update."""
        doc_meta: _DocMeta = values["doc_meta"]
        doc_meta.updated = datetime.now()
        doc_meta.created = doc_meta.created or doc_meta.updated
        return values
