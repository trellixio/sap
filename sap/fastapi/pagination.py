"""Utils for pagination."""

from typing import Any, Generic, Optional, TypedDict, TypeVar

from fastapi import Request
from pydantic import BaseModel

from . import utils

PageDataT = TypeVar("PageDataT")


class BeanieQueryParams(TypedDict):
    """Attribute of beanie query params."""

    limit: int
    skip: int
    sort: str


class CursorInfo:
    """
    Contains information on how the list should paginated.

    This is a fake cursor paginator.
    """

    count: int = -1
    offset: int = 0
    limit: int = 10
    limit_max: int = 250
    sort: str = "-doc_meta.created"

    def __init__(self, request: Request, sort: str = "-doc_meta.created") -> None:
        """Initialize the cursor info."""
        self.sort = request.query_params.get("sort", sort)
        self.limit = int(request.query_params.get("limit", self.limit))
        cursor_str = request.query_params.get("cursor", "")
        try:
            limit, offset = utils.base64_url_decode(cursor_str).split(",")
        except ValueError:
            pass
        else:
            self.limit, self.offset = int(limit), int(offset)

        self.limit = min(self.limit, self.limit_max)

    def get_beanie_query_params(self) -> BeanieQueryParams:
        """Return params to apply to the database query when using beanie."""
        return {
            "limit": self.limit,
            "skip": self.offset,
            "sort": self.sort,
        }

    def set_count(self, value: int) -> None:
        """Set the total count of the query."""
        self.count = value

    def get_count(self) -> int:
        """Return the total count of the query."""
        return self.count

    def get_next(self) -> Optional[str]:
        """Get the cursor to paginate forward."""
        offset = self.offset + self.limit
        if offset >= self.get_count() >= 0:
            return None
        return utils.base64_url_encode(f"{self.limit},{offset}")

    def get_previous(self) -> Optional[str]:
        """Get the cursor to paginate backward."""
        offset = self.offset - self.limit
        if offset < 0:
            return None
        return utils.base64_url_encode(f"{self.limit},{offset}")


class PaginatedData(BaseModel, Generic[PageDataT]):
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
