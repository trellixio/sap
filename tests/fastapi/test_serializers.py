"""Test serializers."""

import pytest

from fastapi import Request
from starlette.datastructures import URL

from sap.fastapi.pagination import CursorInfo, PaginatedData
from tests.samples import DummyDoc, DummyDocSerializer, data_dummy_sample


@pytest.mark.asyncio
async def test_serialize() -> None:
    """Serialize dummy documents."""
    doc: DummyDoc = await DummyDoc.find_one_or_404()
    data_serialized = DummyDocSerializer.read(doc).model_dump()
    assert data_dummy_sample.keys() == data_serialized.keys()


@pytest.mark.asyncio
async def test_serialize_page(request_basic: Request) -> None:
    """Serialize dummy documents listing."""

    async def test_page_for_request(request: Request, limit: int = 1) -> PaginatedData[DummyDocSerializer]:
        """Fetch one page and verify if it matches."""
        cursor_info = CursorInfo(request=request)
        # Get total count without limit/skip
        total_count = await DummyDoc.find().count()
        cursor_info.set_count(total_count)
        # Get paginated results with limit/skip
        qs = DummyDoc.find(**cursor_info.get_beanie_query_params())
        docs = await qs.to_list()
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
