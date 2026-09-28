"""Test serializers."""

import json
from datetime import date, datetime, time
from decimal import Decimal
from typing import ClassVar

import pydantic_core
import pytest

from fastapi import Request
from pydantic import BaseModel
from pydantic.fields import FieldInfo
from starlette.datastructures import URL

from sap.fastapi.pagination import CursorInfo, PaginatedData
from sap.fastapi.serializers import CustomJSONEncoder, ObjectSerializer, WriteObjectSerializer
from tests.samples import (
    DummyDoc,
    DummyDocSerializer,
    DummyDocWriteSerializer,
    EmbeddedDummyDoc,
    EmbeddedDummyDocWriteSerializer,
)


@pytest.mark.asyncio
async def test_serialize() -> None:
    """Serialize dummy documents."""
    doc: DummyDoc = await DummyDoc.find_one_or_404()
    data_serialized = DummyDocSerializer.read(doc).model_dump()
    assert "num" in data_serialized
    assert "name" in data_serialized
    assert data_serialized["num"] == doc.num
    assert data_serialized["name"] == doc.name


@pytest.mark.asyncio
async def test_serialize_list() -> None:
    """Serialize a list of documents."""
    docs = await DummyDoc.find().limit(3).to_list()
    serialized_list = DummyDocSerializer.read_list(docs)
    assert len(serialized_list) == 3
    assert all(isinstance(s, DummyDocSerializer) for s in serialized_list)


@pytest.mark.asyncio
async def test_serialize_page(request_basic: Request) -> None:
    """Serialize dummy documents listing."""

    async def test_page_for_request(request: Request, limit: int = 1) -> PaginatedData[DummyDocSerializer]:
        """Fetch one page and verify if it matches."""
        cursor_info = CursorInfo(request=request)
        params = cursor_info.get_beanie_query_params()
        qs = DummyDoc.find(**params)
        docs = await qs.to_list()
        # Beanie 2 count() includes limit and skip, so the total is a separate query.
        cursor_info.set_count(await DummyDoc.find(sort=params["sort"]).count())
        page: PaginatedData[DummyDocSerializer] = DummyDocSerializer.read_page(
            docs, cursor_info=cursor_info, request=request_basic
        )
        assert page.count >= 20
        assert len(page.data) == limit

        return page

    assert (page_0 := await test_page_for_request(request_basic))
    assert not page_0.previous
    assert page_0.next

    request_1 = Request(scope=request_basic.scope | {"query_string": URL(page_0.next).query})  # type: ignore
    assert (page_1 := await test_page_for_request(request_1))
    assert page_1.previous
    assert page_1.next

    request_2 = Request(scope=request_basic.scope | {"query_string": "limit=20"})  # type: ignore
    assert (page_2 := await test_page_for_request(request_2, limit=20))
    assert not page_2.previous
    assert not page_2.next


@pytest.mark.asyncio
async def test_serialize_with_context() -> None:
    """Test serialization with context parameter."""
    doc = await DummyDoc.find_one_or_404()
    context = {"user": "test_user", "extra": "data"}
    data = DummyDocSerializer.read(doc, context=context, exclude={"description"}).model_dump()
    assert data.get("name") == doc.name
    assert data.get("num") == doc.num
    assert not data.get("description")


def test_custom_json_encoder_decimal() -> None:
    """Test CustomJSONEncoder handles Decimal objects."""
    encoder = CustomJSONEncoder()
    result = encoder.default(Decimal("123.45"))
    assert result == 123.45


def test_custom_json_encoder_datetime() -> None:
    """Test CustomJSONEncoder handles datetime objects."""
    encoder = CustomJSONEncoder()
    dt = datetime(2024, 1, 15, 10, 30, 45)
    result = encoder.default(dt)
    assert result == "2024-01-15T10:30:45"


def test_custom_json_encoder_date() -> None:
    """Test CustomJSONEncoder handles date objects."""
    encoder = CustomJSONEncoder()
    d = date(2024, 1, 15)
    result = encoder.default(d)
    assert result == "2024-01-15"


def test_custom_json_encoder_time() -> None:
    """Test CustomJSONEncoder handles time objects."""
    encoder = CustomJSONEncoder()
    t = time(10, 30, 45)
    result = encoder.default(t)
    assert result == "10:30:45"


def test_custom_json_encoder_url() -> None:
    """Test CustomJSONEncoder handles pydantic_core.Url objects."""
    encoder = CustomJSONEncoder()
    url = pydantic_core.Url("https://example.com/path")
    result = encoder.default(url)
    assert result == "https://example.com/path"


def test_custom_json_encoder_base_model() -> None:
    """Test CustomJSONEncoder handles BaseModel objects."""

    class TestModel(BaseModel):
        """Test model."""

        name: str
        value: int

    encoder = CustomJSONEncoder()
    model = TestModel(name="test", value=42)
    result = encoder.default(model)
    assert result == {"name": "test", "value": 42}


def test_custom_json_encoder_integration() -> None:
    """Test CustomJSONEncoder in json.dumps."""
    data = {
        "decimal": Decimal("99.99"),
        "datetime": datetime(2024, 1, 15, 10, 30, 45),
        "date": date(2024, 1, 15),
        "time": time(10, 30, 45),
    }

    json_str = json.dumps(data, cls=CustomJSONEncoder)
    parsed = json.loads(json_str)

    assert parsed["decimal"] == 99.99
    assert parsed["datetime"] == "2024-01-15T10:30:45"
    assert parsed["date"] == "2024-01-15"
    assert parsed["time"] == "10:30:45"


@pytest.mark.asyncio
async def test_write_serializer_init() -> None:
    """Test WriteObjectSerializer initialization."""

    doc = await DummyDoc(num=1, name="Test Doc").create()
    await doc.refresh_from_db()

    assert doc.num == 1
    assert doc.name == "Test Doc"

    serializer = DummyDocWriteSerializer(num=2, name="Test Doc Updated", info={"num": 11, "name": "Test Info"})  # type: ignore
    serializer.instance = doc

    updated_doc = await serializer.update()
    updated_doc_data = serializer.model_dump()

    assert updated_doc.id == doc.id
    assert updated_doc.num == updated_doc_data["num"] == 2
    assert updated_doc.name == updated_doc_data["name"] == "Test Doc Updated"
    assert updated_doc.info is not None
    assert updated_doc.info.num == updated_doc_data["info"]["num"] == 11
    assert updated_doc.info.name == updated_doc_data["info"]["name"] == "Test Info"

    await doc.delete()


class ContextSource(BaseModel):
    """Plain object serialized with a context getter."""

    label: str = ""


class ContextSerializer(ObjectSerializer[ContextSource]):
    """Serializer whose getter accepts context."""

    label: str

    @classmethod
    def get_label(cls, instance: ContextSource, context: dict[str, str]) -> str:  # pylint: disable=unused-argument
        """Return the label supplied in context."""
        return context["label"]


class NamedSerializer(ObjectSerializer[ContextSource]):
    """Serializer with an explicit object name."""

    object: ClassVar[str] = "card"
    title: str = ""


class Timestamped:
    """Plain object that carries created and updated timestamps."""

    created = datetime(2020, 1, 1)
    updated = datetime(2020, 2, 1)


class BareObject:
    """Plain object without timestamps."""


class PublicIdObject:
    """Plain object identified by a public id."""

    public_id = "pub-1"


class NonDocumentWrite(WriteObjectSerializer[EmbeddedDummyDoc]):
    """Write serializer that cannot persist a Beanie document."""

    name: str


NonDocumentWrite.model_fields["instance"] = FieldInfo(annotation=EmbeddedDummyDoc)


def test_serializer_context_public_id_and_object_name() -> None:
    """Read context-aware getters, public ids, and explicit object names."""
    data = ContextSerializer.read(ContextSource(), context={"label": "from-context"}).model_dump()
    assert data["label"] == "from-context"
    assert DummyDocSerializer.get_id(PublicIdObject()) == "pub-1"  # type: ignore[arg-type]
    assert NamedSerializer.get_object(ContextSource()) == "card"


def test_serializer_timestamps_for_plain_objects() -> None:
    """Read timestamps from a plain object and reject one that has none."""
    assert DummyDocSerializer.get_created(Timestamped()) == datetime(2020, 1, 1)  # type: ignore[arg-type]
    assert DummyDocSerializer.get_updated(Timestamped()) == datetime(2020, 2, 1)  # type: ignore[arg-type]
    with pytest.raises(NotImplementedError):
        DummyDocSerializer.get_created(BareObject())  # type: ignore[arg-type]
    with pytest.raises(NotImplementedError):
        DummyDocSerializer.get_updated(BareObject())  # type: ignore[arg-type]


def test_write_serializer_collects_embedded_and_document_fields() -> None:
    """Collect embedded serializers and document fields once the model is built."""

    class DocWrite(WriteObjectSerializer[DummyDoc]):
        """Write serializer with embedded and document fields."""

        related: DummyDoc
        info: EmbeddedDummyDocWriteSerializer
        tags: list[str] = []
        name: str

    collect = WriteObjectSerializer.__dict__["__init_subclass__"].__func__
    collect(DocWrite)
    assert DocWrite._embedded_serializers["info"] is EmbeddedDummyDocWriteSerializer  # pylint: disable=protected-access
    assert "related" in DocWrite._document_fields  # pylint: disable=protected-access


class InfoWrite(WriteObjectSerializer[DummyDoc]):
    """Write serializer with an embedded info field."""

    num: int
    name: str
    info: EmbeddedDummyDocWriteSerializer


InfoWrite._embedded_serializers = {"info": EmbeddedDummyDocWriteSerializer}  # pylint: disable=protected-access


def test_write_serializer_model_dump_embedded() -> None:
    """Dump an embedded field from the instance or from submitted data."""
    info = EmbeddedDummyDoc(num=1, name="emb", limit=2)
    stored = DummyDoc(num=1, name="doc", info=info)
    with_instance = InfoWrite(num=1, name="doc", info={"num": 3, "name": "new", "limit": 4})  # type: ignore[arg-type]
    with_instance.instance = stored  # pylint: disable=attribute-defined-outside-init
    dumped = with_instance.model_dump()
    assert dumped["info"]["name"] == "new"
    assert dumped["info"]["limit"] == 4

    from_payload = InfoWrite(num=1, name="doc", info={"num": 3, "name": "new", "limit": 4})  # type: ignore[arg-type]
    from_payload.instance = DummyDoc(num=1, name="doc")  # pylint: disable=attribute-defined-outside-init
    dumped = from_payload.model_dump()
    assert dumped["info"] == {"num": 3, "name": "new", "limit": 4}


@pytest.mark.asyncio
async def test_write_serializer_embedded_validators() -> None:
    """Run async validators on an embedded serializer that has an instance."""
    info = EmbeddedDummyDoc(num=1, name="emb", limit=2)
    serializer = InfoWrite(num=1, name="doc", info={"num": 1, "name": "emb", "limit": 2})  # type: ignore[arg-type]
    serializer.instance = DummyDoc(num=1, name="doc", info=info)  # pylint: disable=attribute-defined-outside-init
    await serializer.run_async_validators()
    assert serializer.info.instance == info


@pytest.mark.asyncio
async def test_write_serializer_rejects_non_document() -> None:
    """Refuse to create or update when the target is not a Beanie document."""
    serializer = NonDocumentWrite(name="plain")
    with pytest.raises(NotImplementedError):
        await serializer.create()

    write = DummyDocWriteSerializer(num=1, name="doc", info={"num": 1, "name": "emb", "limit": 2})  # type: ignore[arg-type]
    write.instance = EmbeddedDummyDoc(num=1, name="emb", limit=2)  # type: ignore[assignment]
    with pytest.raises(NotImplementedError):
        await write.update()


def test_custom_json_encoder_fallback() -> None:
    """Fall through to the default encoder for an unsupported type."""
    with pytest.raises(TypeError):
        CustomJSONEncoder().default(object())
