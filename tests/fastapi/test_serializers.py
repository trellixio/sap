"""Test serializers."""

import json
from datetime import date, datetime, time
from decimal import Decimal

import pydantic_core
import pytest

from fastapi import Request
from pydantic import BaseModel
from starlette.datastructures import URL

from sap.fastapi.pagination import CursorInfo, PaginatedData
from sap.fastapi.serializers import CustomJSONEncoder
from tests.samples import DummyDoc, DummyDocSerializer, DummyDocWriteSerializer


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
        qs = DummyDoc.find(**cursor_info.get_beanie_query_params())
        docs = await qs.to_list()
        cursor_info.set_count(await qs.count())
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
