# pylint: disable=no-self-use
"""Tests for Document class."""

import asyncio
import typing
from datetime import timezone

import pytest
import pytest_asyncio

from beanie import PydanticObjectId

from sap.beanie.document import DocSourceEnum
from sap.exceptions import Object404Error
from tests.samples import DummyDoc


class TestDocument:
    """Test cases for Document class."""

    @pytest_asyncio.fixture
    async def doc_1(self) -> typing.AsyncGenerator[DummyDoc, None]:
        """Return test document models."""
        doc = await DummyDoc(num=12, name="Test Doc Beanie", description="Test description", is_positive=True).create()
        yield doc
        await doc.delete()

    @pytest.mark.asyncio
    async def test_validate_doc_meta(self, doc_1: DummyDoc) -> None:
        """Test that doc_meta is validated and updated on document creation and update."""

        # Check that created and updated are set
        assert doc_1.doc_meta.created is not None
        assert doc_1.doc_meta.updated is not None
        assert doc_1.doc_meta.version is not None
        assert doc_1.doc_meta.source is None
        assert doc_1.doc_meta.deleted is None

        # Check timestamps are in UTC
        assert doc_1.doc_meta.created.tzinfo == timezone.utc
        assert doc_1.doc_meta.updated.tzinfo == timezone.utc

        # Check that created and updated are approximately the same
        time_diff = abs((doc_1.doc_meta.updated - doc_1.doc_meta.created).total_seconds())
        assert time_diff < 1, "created and updated should be within 1 second on creation"

        # Store original created time
        original_created = doc_1.doc_meta.created
        original_updated = doc_1.doc_meta.updated

        # Update document
        doc_1.name = "Updated Test Doc"
        doc_1.num = 2
        doc_1.doc_meta.version = 2
        doc_1.doc_meta.source = DocSourceEnum.WEBHOOK

        await doc_1.save()
        await asyncio.sleep(1)
        await doc_1.refresh_from_db()

        # Check that created remains the same but updated changes
        # Note: MongoDB stores datetime with millisecond precision, so we need to compare with tolerance
        created_diff = abs((doc_1.doc_meta.created.replace(tzinfo=timezone.utc) - original_created).total_seconds())
        assert created_diff < 0.001, "created should remain approximately the same"
        assert doc_1.doc_meta.updated > original_updated
        assert doc_1.doc_meta.version == 2
        assert doc_1.doc_meta.source == DocSourceEnum.WEBHOOK

    @pytest.mark.asyncio
    async def test_get_or_404(self, doc_1: DummyDoc) -> None:
        """Test get_or_404 returns document when it exists and raises error otherwise."""
        assert doc_1.id is not None

        # Test get_or_404 with PydanticObjectId
        result = await DummyDoc.get_or_404(doc_1.id)
        assert result.id == doc_1.id

        # Test get_or_404 with string id
        result_str = await DummyDoc.get_or_404(str(doc_1.id))
        assert result_str.id == doc_1.id

        # Test that Object404Error is raised
        with pytest.raises(Object404Error):
            await DummyDoc.get_or_404(PydanticObjectId())

    @pytest.mark.asyncio
    async def test_find_one_or_404(self, doc_1: DummyDoc) -> None:
        """Test find_one_or_404 returns document when it exists."""
        # Create a document with unique attributes
        assert doc_1.id is not None

        # Test find_one_or_404 with simple query
        result = await DummyDoc.find_one_or_404({"name": doc_1.name})
        assert result.id == doc_1.id

        # Test with multiple conditions
        result_multi = await DummyDoc.find_one_or_404({"name": doc_1.name, "num": doc_1.num})
        assert result_multi.id == doc_1.id

        # Test with Beanie query operators
        result_name = await DummyDoc.find_one_or_404(DummyDoc.name == doc_1.name)
        assert result_name.id == doc_1.id

        # Test with non-existent query
        with pytest.raises(Object404Error):
            await DummyDoc.find_one_or_404({"name": "Test Find One 404"})

    @pytest.mark.asyncio
    async def test_refresh_from_db(self, doc_1: DummyDoc) -> None:
        """Test refresh_from_db reloads document from database."""

        # Modify the document in the database using a different instance
        db_doc = await DummyDoc.get(doc_1.id)
        assert db_doc is not None
        db_doc.name = "Updated Name"
        db_doc.description = "Updated description"
        db_doc.num = 3001
        await db_doc.save()

        # Original doc instance should still have old values
        assert doc_1.name == "Test Doc Beanie"
        assert doc_1.description == "Test description"
        assert doc_1.num == 12

        # Refresh the original document
        await doc_1.refresh_from_db()

        # Now it should have updated values
        assert doc_1.name == "Updated Name"
        assert doc_1.description == "Updated description"
        assert doc_1.num == 3001
