# pylint: disable=too-many-ancestors

"""
Samples.

Populate the database with dummy data for testing purposes.
"""

import typing
from datetime import datetime

import pydantic

from sap.beanie import Document
from sap.beanie.link import Link
from sap.beanie.mixins import PasswordMixin
from sap.fastapi.serializers import ObjectSerializer, WriteObjectSerializer
from sap.fastapi.user import UserMixin


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

    id: str
    object: str
    created: datetime
    updated: datetime


class EmbeddedDummyDocWriteSerializer(EmbeddedDummyDoc, WriteObjectSerializer[EmbeddedDummyDoc]):
    """Write serializer for EmbeddedDummyDoc."""

    limit: int = 0


class DummyDocWriteSerializer(WriteObjectSerializer[DummyDoc]):
    """Write serializer for DummyDoc."""

    num: int
    name: str
    is_positive: bool = True
    description: str = ""
    info: EmbeddedDummyDocWriteSerializer


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


class MerchantDoc(Document):
    """Mock merchant document for testing."""

    beans_card_id: str


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
    merchant: typing.Optional[Link[MerchantDoc]] = None

    class Settings:
        """Settings for the database collection."""

        name = "sap_test_product"


class UserDoc(Document, PasswordMixin, UserMixin):
    """User document for testing PasswordMixin."""

    username: str
    email: str
    role: str = "default"
    auth_key: typing.Optional[str] = None

    async def get_auth_key(self) -> str:
        """Get auth key."""
        return self._auth_key or ""

    class Settings:
        """Settings for the database collection."""

        name = "sap_test_user"
