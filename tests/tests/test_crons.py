"""Tests for sap/tests/crons.py."""

import pytest

from beanie import PydanticObjectId
from beanie.odm.queries.find import FindMany

from sap.tests.crons import get_filter_queryset_dummy, get_filter_queryset_for_merchant
from tests.samples import CategoryDoc, MerchantDoc, ProductDoc


@pytest.mark.asyncio
async def test_get_filter_queryset_dummy() -> None:
    """Test get_filter_queryset_dummy returns unfiltered queryset."""

    category = await CategoryDoc(name="Category1", description="Category1 description").create()
    doc1 = await ProductDoc(name="Doc1", price=100, category=category).create()

    initial_count = await ProductDoc.find().count()
    filtered_count = await get_filter_queryset_dummy()(ProductDoc.find()).count()
    assert initial_count == filtered_count

    await doc1.delete()


@pytest.mark.asyncio
async def test_get_filter_queryset_for_merchant_with_beans_card_id() -> None:
    """Test get_filter_queryset_for_merchant returns filter for models with beans_card_id."""
    # Create test documents

    merchant = await MerchantDoc(beans_card_id="1234567890").create()
    category = await CategoryDoc(name="Category1", description="Category1 description").create()
    doc1 = await ProductDoc(name="Doc1", price=100, merchant=merchant, category=category).create()
    doc2 = await ProductDoc(name="Doc2", price=200, category=category).create()
    assert merchant.id is not None

    filter_func = get_filter_queryset_for_merchant(ProductDoc, merchant.id)
    assert callable(filter_func)

    # Actually call the filter function to cover line 34
    queryset = ProductDoc.find()
    filtered_queryset = filter_func(queryset)
    results = await filtered_queryset.to_list()
    assert len(results) == 1
    assert results[0].id == doc1.id

    await doc1.delete()
    await doc2.delete()
    await merchant.delete()


@pytest.mark.asyncio
async def test_get_filter_queryset_for_merchant_with_merchant_attr() -> None:
    """Test get_filter_queryset_for_merchant returns filter for models with merchant attribute."""
    merchant = await MerchantDoc(beans_card_id="1234567890").create()
    assert merchant.id is not None

    filter_func = get_filter_queryset_for_merchant(MerchantDoc, merchant.id)
    assert callable(filter_func)

    # Call the filter function to cover lines 38-39
    queryset = MerchantDoc.find()
    filtered_queryset = filter_func(queryset)
    # Just verify it executes without error
    assert isinstance(filtered_queryset, FindMany)

    await merchant.delete()
