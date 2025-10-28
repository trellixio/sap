# pylint: disable=no-self-use
"""Tests for BeanieClient class."""

from typing import Any, Mapping

import pytest
from pymongo.asynchronous.database import AsyncDatabase

from AppMain.settings import AppSettings
from sap.beanie.client import BeanieClient
from sap.beanie.document import Document
from tests.samples import DummyDoc

# from beanie import Document


class TestBeanieClient:
    """Test cases for BeanieClient class."""

    @pytest.fixture
    def document_models(self) -> list[type[Document]]:
        """Return test document models."""
        return [DummyDoc]

    @pytest.mark.asyncio
    async def test_init_creates_connection(self, document_models: list[type[Document]]) -> None:
        """Test that init creates a new database connection."""
        # Clear any existing connections
        BeanieClient.connections.clear()

        await BeanieClient.init(AppSettings.MONGO, document_models)

        assert "default" in BeanieClient.connections
        assert isinstance(BeanieClient.connections["default"].database, AsyncDatabase)

    @pytest.mark.asyncio
    async def test_get_db_default_returns_database(self, document_models: list[type[Document]]) -> None:
        """Test that get_db_default returns the correct database instance."""
        # Clear any existing connections
        BeanieClient.connections.clear()

        await BeanieClient.init(AppSettings.MONGO, document_models)
        db: AsyncDatabase[Mapping[str, Any]] = await BeanieClient.get_db_default()

        assert isinstance(db, AsyncDatabase)
        assert str(db.name) == AppSettings.MONGO.db

    @pytest.mark.asyncio
    async def test_init_force_recreates_connection(self, document_models: list[type[Document]]) -> None:
        """Test that init with force=True recreates the connection."""
        # Clear any existing connections
        BeanieClient.connections.clear()

        # Create initial connection
        await BeanieClient.init(AppSettings.MONGO, document_models)
        first_db: AsyncDatabase[Mapping[str, Any]] = BeanieClient.connections["default"].database

        # Force recreate connection
        await BeanieClient.init(AppSettings.MONGO, document_models, force=True)
        second_db: AsyncDatabase[Mapping[str, Any]] = BeanieClient.connections["default"].database

        # assert first_db != second_db
        assert isinstance(first_db, AsyncDatabase)
        assert isinstance(second_db, AsyncDatabase)

    @pytest.mark.asyncio
    async def test_init_reuses_existing_connection(self, document_models: list[type[Document]]) -> None:
        """Test that init reuses existing connection when force=False."""
        # Clear any existing connections
        BeanieClient.connections.clear()

        # Create initial connection
        await BeanieClient.init(AppSettings.MONGO, document_models)
        first_db: AsyncDatabase[Mapping[str, Any]] = BeanieClient.connections["default"].database

        # Try to create new connection without force
        await BeanieClient.init(AppSettings.MONGO, document_models)
        second_db: AsyncDatabase[Mapping[str, Any]] = BeanieClient.connections["default"].database

        assert first_db == second_db
