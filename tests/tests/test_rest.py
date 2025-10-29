"""Tests for sap/tests/rest.py - using real FastAPI endpoints."""

import pytest

from sap.tests.rest import (
    assert_rest_can_create,
    assert_rest_can_destroy,
    assert_rest_can_list,
    assert_rest_can_retrieve,
    assert_rest_can_update,
)
from tests.samples import DummyDoc


@pytest.mark.asyncio
async def test_assert_rest_can_list() -> None:
    """Test assert_rest_can_list with real endpoint."""
    sample = {"id": "123", "name": "Test Item"}

    result = await assert_rest_can_list("/test/items/", sample=sample, roles=None)
    assert result is True


@pytest.mark.asyncio
async def test_assert_rest_can_retrieve() -> None:
    """Test assert_rest_can_retrieve with real endpoint."""
    sample = {"id": "123", "name": "Test Item", "value": 100}

    result = await assert_rest_can_retrieve("/test/items/", "123", sample=sample, roles=None)
    assert result is True


@pytest.mark.asyncio
async def test_assert_rest_can_create() -> None:
    """Test assert_rest_can_create with real endpoint."""
    sample = {"name": "Base Item"}
    variant_good = {"status": "active"}
    variant_bad = {"status": 123}

    result = await assert_rest_can_create(
        "/test/items/", sample=sample, variant_good=variant_good, variant_bad=variant_bad, roles=None
    )
    assert result is True


@pytest.mark.asyncio
async def test_assert_rest_can_update() -> None:
    """Test assert_rest_can_update with real endpoint."""
    variant_good = {"name": "Updated Name"}
    variant_bad = {"name": 123}

    result = await assert_rest_can_update(
        "/test/items/", "123", variant_good=variant_good, variant_bad=variant_bad, roles=None
    )
    assert result is True


@pytest.mark.asyncio
async def test_assert_rest_can_destroy() -> None:
    """Test assert_rest_can_destroy with real endpoint."""
    # Create and save a real document, then delete it
    doc = await DummyDoc(num=999, name="ToDelete").create()
    doc_id = str(doc.id)

    result = await assert_rest_can_destroy("/test/items/", doc_id, item=doc, roles=None)
    assert result is True
