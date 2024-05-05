"""
Samples.

Populate the database with dummy data for testing purposes.
"""

import typing
import pydantic
from sap.beanie import Document


class EmbeddedDummyDoc(Document):
    """Dummy embedded document model used to populate the db for testing."""

    num: int
    name: str
    limit: int


class DummyDoc(Document):
    """Dummy document models used to populate the db for testing."""

    num: int
    name: str
    hash: typing.Optional[bytes] = None
    is_positive: bool = True
    description: str = ""
    listing: list[int] = []
    data: dict[str, str] = {}
    info: typing.Optional[EmbeddedDummyDoc] = None

    class Settings:
        """Settings for the database collection."""

        name = "xlib_dummy"
