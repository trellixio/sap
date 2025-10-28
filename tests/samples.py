# pylint: disable=too-many-ancestors

"""
Samples.

Populate the database with dummy data for testing purposes.
"""

import typing

import pydantic

from sap.beanie import Document
from sap.beanie.link import Link
from sap.beanie.mixins import PasswordMixin
from sap.fastapi.serializers import ObjectSerializer


class EmbeddedDummyDoc(pydantic.BaseModel):
    """Dummy embedded document model used to populate the db for testing."""

    num: int
    name: str
    limit: int


class DummyDocSchema(pydantic.BaseModel):
    """Dummy document models used to populate the db for testing."""

    num: int
    name: str
    hash: typing.Optional[bytes] = None
    is_positive: bool = True
    description: str = ""
    listing: list[int] = []
    data: dict[str, str] = {}
    info: typing.Optional[EmbeddedDummyDoc] = None


class DummyDoc(DummyDocSchema, Document):
    """Dummy document models used to populate the db for testing."""

    class Settings:
        """Settings for the database collection."""

        name = "sap_test_dummy"


class DummyDocSerializer(DummyDocSchema, ObjectSerializer[DummyDoc]):
    """Dummy document serializer used to populate the db for testing."""


data_dummy_sample = {
    "num": -10,
    "name": "Document N-10",
    "hash": b"\x1b\x0f\xd9\xef\xa5'\x9cB\x03\xb7\xc7\x023\xf8m\xbf",
    "is_positive": False,
    "description": "xxxxxx",
    "listing": [-30, -50, -70, -90],
    "data": {"attr-10": "kdlejdedle"},
    "info": {"num": -50, "name": "EmbeddedDocument N-10", "limit": -150},
}


# Models for testing Link relationships and query functions
class CategoryDoc(Document):
    """Category document for testing Link relationships."""

    model_config = {"extra": "allow"}

    name: str
    description: str = ""

    class Settings:
        """Settings for the database collection."""

        name = "sap_test_category"


class ProductDoc(Document):
    """Product document for testing Link relationships."""

    name: str
    price: float
    category: Link[CategoryDoc]

    class Settings:
        """Settings for the database collection."""

        name = "sap_test_product"


class UserDoc(Document, PasswordMixin):
    """User document for testing PasswordMixin."""

    username: str
    email: str
    auth_key: typing.Optional[str] = None

    class Settings:
        """Settings for the database collection."""

        name = "sap_test_user"
