# pylint: disable=no-self-use
"""Tests for query utility functions."""

import typing

import pytest
import pytest_asyncio

from sap.beanie.query import prefetch_related, prefetch_related_children, prepare_search_string
from sap.tests.apm_pymongo import apm
from tests.samples import CategoryDoc, ProductDoc


class TestPrefetchRelated:
    """Test suite for prefetch_related utility."""

    @pytest_asyncio.fixture(autouse=True)
    async def setup(self) -> typing.AsyncGenerator[tuple[list[ProductDoc], list[CategoryDoc]], None]:
        """Setup resources for the TestPrefetchRelated test class."""

        # Create test categories.
        cat1 = await CategoryDoc(name="Electronics", description="Electronic devices").create()
        cat2 = await CategoryDoc(name="Books", description="Various books").create()
        cat3 = await CategoryDoc(name="Clothing", description="Apparel and accessories").create()

        # Create test products.
        products = [
            await ProductDoc(name="Electronics - Laptop", price=99, category=cat1).create(),
            await ProductDoc(name="Electronics - Mouse", price=29, category=cat1).create(),
            await ProductDoc(name="Books - Python Guide", price=49, category=cat2).create(),
            await ProductDoc(name="Clothing - T-Shirt", price=19, category=cat3).create(),
            await ProductDoc(name="Clothing - Jeans", price=34, category=cat3).create(),
        ]

        yield products, [cat1, cat2, cat3]

        # Delete all ProductDoc and CategoryDoc items after test
        await ProductDoc.find_all().delete()
        await CategoryDoc.find_all().delete()

    @pytest.mark.asyncio
    async def test_query(self) -> None:
        """Test prefetch_related fetches and caches related documents efficiently."""
        # Get fresh products from DB without links fetched
        product_list = await ProductDoc.find_all().to_list()

        # Verify categories are not fetched yet
        assert all(p.category.doc is None for p in product_list)

        # Prefetch categories
        apm.clear()
        assert apm.get_events_count() == 0
        await prefetch_related(product_list, "category")
        assert apm.get_events_count() == 1

        # Verify categories are now fetched
        assert all(p.category.doc is not None for p in product_list)

        # Verify correct categories are linked
        for p in product_list:
            assert (p_category := p.category.doc)
            assert p.name.startswith(
                p_category.name
            ), f"Product {p.name} does not start with category {p_category.name}"


class TestPrefetchRelatedChildren:
    """Test cases for prefetch_related_children function."""

    @pytest_asyncio.fixture(autouse=True)
    async def setup(self) -> typing.AsyncGenerator[tuple[list[ProductDoc], list[CategoryDoc]], None]:
        """Setup resources for the TestPrefetchRelatedChildren test class."""
        cat1 = await CategoryDoc(name="Electronics", description="Electronic devices").create()
        cat2 = await CategoryDoc(name="Books", description="Various books").create()
        categories = [cat1, cat2]

        products = []
        for i in range(3):
            products.append(await ProductDoc(name=f"Electronics {i}", price=120 + i * 50, category=cat1).create())
            products.append(await ProductDoc(name=f"Books {i}", price=60 + i * 10, category=cat2).create())

        yield products, categories

        # Cleanup after test
        await ProductDoc.find_all().delete()
        await CategoryDoc.find_all().delete()

    @pytest.mark.asyncio
    async def test_prefetch(self) -> None:
        """Test prefetch_related_children fetches child documents efficiently."""
        # Get fresh categories from DB
        category_list = await CategoryDoc.find_all().to_list()

        # Prefetch products for each category
        apm.clear()
        assert apm.get_events_count() == 0
        await prefetch_related_children(
            category_list, to_attribute="products", related_model=ProductDoc, related_attribute="category"
        )
        assert apm.get_events_count() == 1

        # Verify products are attached
        for cat in category_list:
            assert hasattr(cat, "products")
            assert len(cat.products) == 3
            assert all(cat.name in p.name for p in cat.products)

    @pytest.mark.asyncio
    async def test_prefetch_with_filter(self) -> None:
        """Test prefetch_related_children with custom filter function."""

        def filter_expensive(related_items: list[ProductDoc], item: CategoryDoc) -> list[ProductDoc]:
            """Filter only products with price > 100."""
            return [p for p in related_items if p.price > 100]

        # Get fresh categories from DB
        category_list = await CategoryDoc.find_all().to_list()

        # Prefetch with filter
        apm.clear()
        assert apm.get_events_count() == 0
        await prefetch_related_children(
            category_list,
            to_attribute="products_expensive",
            related_model=ProductDoc,
            related_attribute="category",
            filter_func=filter_expensive,
        )
        assert apm.get_events_count() == 1

        # Verify filtered products
        for cat in category_list:
            assert hasattr(cat, "products_expensive")
            products_expensive_count = 3 if cat.name == "Electronics" else 0
            assert (
                len(cat.products_expensive) == products_expensive_count
            ), f"Category {cat.name} has {len(cat.products_expensive)} products, expected {products_expensive_count}"


class TestPrepareSearchString:
    """Test cases for prepare_search_string function."""

    def test_prepare_search_string_basic(self) -> None:
        """Test basic string preparation strips whitespace."""
        assert prepare_search_string("  hello  ") == "hello"
        assert prepare_search_string("world") == "world"
        assert prepare_search_string("  test string  ") == "test string"
        assert prepare_search_string("hello!world") == "hello!world"
        assert prepare_search_string('"already quoted"') == '"already quoted"'

    def test_prepare_search_string_with_email(self) -> None:
        """Test that email addresses get quoted."""
        assert prepare_search_string("user@example.com") == '"user@example.com"'
        assert prepare_search_string("  admin@site.com  ") == '"admin@site.com"'
        assert prepare_search_string('"user@example.com"') == '"user@example.com"'
