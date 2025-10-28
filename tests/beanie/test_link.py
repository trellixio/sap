# pylint: disable=no-self-use
"""Tests for Link class."""

import typing

import pytest
import pytest_asyncio

from sap.beanie import Link
from tests.samples import CategoryDoc, ProductDoc


class TestLink:
    """Test cases for Link class."""

    @pytest_asyncio.fixture(autouse=True)
    async def category(self) -> typing.AsyncGenerator[CategoryDoc, None]:
        """Create a test category."""
        category = await CategoryDoc(name="Animals", description="Animals with descriptions").create()
        yield category
        await category.delete()

    @pytest_asyncio.fixture(autouse=True)
    async def product(self, category: CategoryDoc) -> typing.AsyncGenerator[ProductDoc, None]:
        """Create a test product with category link."""
        product = await ProductDoc(name="Animals - Elephant", price=999.99, category=category).create()
        assert product.id is not None
        yield await ProductDoc.get_or_404(product.id, fetch_links=False)
        await product.delete()

    @pytest.mark.asyncio
    async def test_init(self, product: ProductDoc, category: CategoryDoc) -> None:
        """Test Link initialization sets attributes correctly."""
        link = product.category
        assert isinstance(link, Link)
        assert link.id == category.id
        assert link.document_class == CategoryDoc
        assert link.doc is None

        category_fetched = await link.fetch()

        assert isinstance(category_fetched, CategoryDoc)
        assert category_fetched.id == category.id
        assert link.doc is category_fetched

        # Check redundant fetch returns the same object
        assert await category_fetched.fetch() is category_fetched  # type: ignore
        assert category_fetched.doc is category_fetched
