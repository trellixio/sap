# pylint: disable=too-many-positional-arguments

"""
Documents.

Override beanie Documents to useful methods.
Most of the methods are inspired from Django behavior on querying data.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any, Mapping, Optional, Type, TypeVar, Union

from pymongo.client_session import ClientSession

import beanie
import pydantic
from beanie import PydanticObjectId

from sap.exceptions import Object404Error

if TYPE_CHECKING:
    from beanie.odm.documents import DocType
    from beanie.odm.interfaces.find import DocumentProjectionType


class DocSourceEnum(Enum):
    """Source where a document has been fetched from."""

    WEBHOOK = "webhook"
    RETRIEVE = "retrieve"
    CRON = "cron"
    PARENT = "parent"


class DocMeta(pydantic.BaseModel):
    """Meta Data allowing to keep trace of Documents versioning and updates."""

    version: int = 0  # version of the document being imported
    source: Optional[DocSourceEnum] = None  # where the data is coming from: webhook, cron
    created: Optional[datetime] = None  # when the document was first imported
    updated: Optional[datetime] = None  # when the document was last updated
    deleted: Optional[datetime] = None  # when the document was deleted, (deleted document may be retained for logging)


class Document(beanie.Document):
    """Subclass beanie.Document that add handy methods."""

    doc_meta: DocMeta = DocMeta()

    def __init__(self, *args: Any, **kwargs: Any) -> None:  # pylint: disable=useless-parent-delegation
        """Silent mypy."""
        super().__init__(*args, **kwargs)

    @pydantic.model_validator(mode="after")
    def validate_doc_meta(self) -> "Document":
        """Validate doc meta on each model update."""
        self.doc_meta.updated = datetime.now(timezone.utc)
        self.doc_meta.created = self.doc_meta.created or self.doc_meta.updated
        return self

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
    ) -> Union["DocumentProjectionType", "DocType"]:
        """Find document from query or raise 404 error if document does not exist."""
        result = await super().find_one(
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

    async def fetch(self) -> "Document":
        """Simulate the fetch method available on Link class."""
        return self

    @property
    def doc(self) -> "Document":
        """Simulate the doc attribute available on Link class."""
        return self

    async def refresh_from_db(self) -> None:
        """Reset all attributes using values from database."""
        assert self.id
        new_doc = await self.get(self.id)
        self.__dict__.update(new_doc.__dict__)


DocT = TypeVar("DocT", bound=Document)
