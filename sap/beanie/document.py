"""
Documents.

Override beanie Documents to useful methods.
Most of the methods are inspired from Django behavior on querying data.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Any, Mapping, Optional, Type, TypeVar, Union

from pymongo.client_session import ClientSession

import beanie
import pydantic
from beanie import PydanticObjectId

from .exceptions import Object404Error

if TYPE_CHECKING:
    from beanie.odm.documents import DocType
    from beanie.odm.interfaces.find import DocumentProjectionType


class _DocMeta(pydantic.BaseModel):
    """Meta Data allowing to keep trace of Documents versioning and updates."""

    version: int = 0  # version of the document being imported
    source: Optional[str] = ""  # where the data is coming from: webhook, cron
    created: Optional[datetime] = None  # when the document was first imported
    updated: Optional[datetime] = None  # when the document was last updated
    deleted: Optional[datetime] = None # when the document was deleted, (deleted document may be retained for logging)


class DocMeta(pydantic.BaseModel):
    """Manage meta data and ensure that it's correctly set."""

    doc_meta: _DocMeta = _DocMeta()

    @pydantic.root_validator
    @classmethod
    def validate_doc_meta(cls, values: dict[str, Any]) -> dict[str, Any]:
        """Validate doc meta on each model update."""
        doc_meta: _DocMeta = values["doc_meta"]
        doc_meta.updated = datetime.now()
        doc_meta.created = doc_meta.created or doc_meta.updated
        return values


class Document(beanie.Document):
    """Subclass beanie.Document that add handy methods."""

    doc_meta: _DocMeta = _DocMeta()

    @pydantic.root_validator
    @classmethod
    def validate_doc_meta(cls, values: dict[str, Any]) -> dict[str, Any]:
        """Validate doc meta on each model update."""
        doc_meta: _DocMeta = values["doc_meta"]
        doc_meta.updated = datetime.now()
        doc_meta.created = doc_meta.created or doc_meta.updated
        return values

    @classmethod
    async def get_or_404(
        cls: Type["DocType"],
        document_id: Union[PydanticObjectId, str],
        session: Optional[ClientSession] = None,
        ignore_cache: bool = False,
        fetch_links: bool = False,
        with_children: bool = False,
        **pymongo_kwargs: Any,
    ) -> "DocType":
        """Get document by id or raise 404 error if document does not exist."""
        doc_id = document_id if isinstance(document_id, PydanticObjectId) else PydanticObjectId(document_id)
        result = await super().get(
            document_id=doc_id,
            session=session,
            ignore_cache=ignore_cache,
            fetch_links=fetch_links,
            with_children=with_children,
            **pymongo_kwargs,
        )
        if not result:
            raise Object404Error
        return result

    @classmethod
    async def find_one_or_404(
        cls: Type["DocType"],
        *args: Union[Mapping[str, Any], bool],
        projection_model: Optional[Type["DocumentProjectionType"]] = None,
        session: Optional[ClientSession] = None,
        ignore_cache: bool = False,
        fetch_links: bool = False,
        with_children: bool = False,
        **pymongo_kwargs: Any,
    ) -> "DocType":
        """Find document from query or raise 404 error if document does not exist."""
        result: Optional["DocType"] = await super().find_one(
            *args,
            projection_model=projection_model,
            session=session,
            ignore_cache=ignore_cache,
            fetch_links=fetch_links,
            with_children=with_children,
            **pymongo_kwargs,
        )
        if not result:
            raise Object404Error
        return result


DocT = TypeVar("DocT", bound=Document)
