import datetime
from typing import TYPE_CHECKING, Any, Mapping, Optional, Type, Union

from pymongo.client_session import ClientSession

import beanie
import pydantic
from beanie import PydanticObjectId

from .exceptions import Object404Error
from .models import _DocMeta

if TYPE_CHECKING:
    from beanie.odm.documents import DocType
    from beanie.odm.interfaces.find import DocumentProjectionType


class Document(beanie.Document):
    """Subclass beanie.Document that add handy methods."""

    doc_meta: _DocMeta = _DocMeta()

    @pydantic.root_validator
    @classmethod
    def validate_doc_meta(cls, values: dict[str, Any]) -> dict[str, Any]:
        """Validate doc meta on each model update."""
        doc_meta: _DocMeta = values["doc_meta"]
        doc_meta.updated = datetime.datetime.now()
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
