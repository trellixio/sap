from typing import Any, Generic, Optional, TypedDict, TypeVar, Union

from fastapi import Request
from pydantic import BaseModel

from . import utils

PageDataT = TypeVar("PageDataT")


class CursorInfo:
    """Contains information on how the list should paginated."""

    offset: int = 0
    limit: int = 10
    sort: str = "-doc_meta.created"

    def __init__(self, request: Request) -> None:
        """Initialize the cursor info."""
        cursor_str = request.query_params.get("cursor", "")
        try:
            limit, offset = utils.base64_url_decode(cursor_str).split(",")
        except ValueError:
            return
        self.limit, self.offset = int(limit), int(offset)

    def get_beanie_query_params(self) -> dict[str, Union[int, str]]:
        """Return params to apply to the database query when using beanie."""
        return {
            "limit": self.limit,
            "skip": self.offset,
            "sort": self.sort,
        }

    def get_next(self) -> Optional[str]:
        """Get the cursor to paginate forward."""
        offset = self.offset + self.limit
        return utils.base64_url_encode(f"{self.limit},{offset}")

    def get_previous(self) -> Optional[str]:
        """Get the cursor to paginate backward."""
        offset = self.offset - self.limit
        if offset <= 0:
            return None
        return utils.base64_url_encode(f"{self.limit},{offset}")


class PaginatedData(Generic[PageDataT], BaseModel):
    """Represent the structure of an API paginated list response."""

    object: str = "list"
    count: int
    next: Optional[str]
    previous: Optional[str]
    data: list[Any]


class PaginatedResponse(TypedDict):
    """
    Define a standard paginated response.

    PaginatedResponse has same structure as PaginatedData.
    """

    object: str
    count: int
    next: Optional[str]
    previous: Optional[str]
    data: list[dict[str, Any]]
