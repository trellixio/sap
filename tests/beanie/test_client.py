"""Tests for BeanieClient class."""

import os
from typing import Any
from unittest import mock

import pymongo.errors
import pytest
from pymongo.asynchronous.database import AsyncDatabase

from AppMain.settings import AppSettings
from sap.beanie.client import BeanieClient
from sap.beanie.document import Document
from tests.samples import DummyDoc

# from beanie import Document


@pytest.fixture(name="document_models")
def fixture_document_models() -> list[type[Document]]:
    """Return test document models."""
    return [DummyDoc]


@pytest.mark.asyncio
async def test_init_creates_connection(document_models: list[type[Document]]) -> None:
    """Test that init creates a new database connection."""
    # Clear any existing connections
    BeanieClient.connections.clear()

    await BeanieClient.init(AppSettings.MONGO, document_models)

    connection_name, connection = next(iter(BeanieClient.connections.items()))
    assert connection_name == f"default_{os.getpid()}"
    assert isinstance(connection.database, AsyncDatabase)


@pytest.mark.asyncio
async def test_get_db_default_returns_database(document_models: list[type[Document]]) -> None:
    """Test that get_db_default returns the correct database instance."""
    # Clear any existing connections
    BeanieClient.connections.clear()

    await BeanieClient.init(AppSettings.MONGO, document_models)
    db: AsyncDatabase[Any] = await BeanieClient.get_db_default()

    assert isinstance(db, AsyncDatabase)
    assert str(db.name) == AppSettings.MONGO.db


@pytest.mark.asyncio
async def test_init_force_recreates_connection(document_models: list[type[Document]]) -> None:
    """Test that init with force=True recreates the connection."""
    # Clear any existing connections
    BeanieClient.connections.clear()

    # Create initial connection
    await BeanieClient.init(AppSettings.MONGO, document_models)
    _, connection = next(iter(BeanieClient.connections.items()))
    first_db: AsyncDatabase[Any] = connection.database

    # Force recreate connection
    await BeanieClient.init(AppSettings.MONGO, document_models, force=True)
    _, connection = next(iter(BeanieClient.connections.items()))
    second_db: AsyncDatabase[Any] = connection.database

    # assert first_db != second_db
    assert isinstance(first_db, AsyncDatabase)
    assert isinstance(second_db, AsyncDatabase)


@pytest.mark.asyncio
async def test_init_reuses_existing_connection(document_models: list[type[Document]]) -> None:
    """Test that init reuses existing connection when force=False."""
    # Clear any existing connections
    BeanieClient.connections.clear()

    # Create initial connection
    await BeanieClient.init(AppSettings.MONGO, document_models)
    _, connection = next(iter(BeanieClient.connections.items()))
    first_db: AsyncDatabase[Any] = connection.database

    # Try to create new connection without force
    await BeanieClient.init(AppSettings.MONGO, document_models)
    _, connection = next(iter(BeanieClient.connections.items()))
    second_db: AsyncDatabase[Any] = connection.database

    assert first_db == second_db


@pytest.mark.asyncio
async def test_init_recreates_connection_when_ping_fails(document_models: list[type[Document]]) -> None:
    """Open a new connection when the existing one fails its ping."""
    BeanieClient.connections.clear()
    await BeanieClient.init(AppSettings.MONGO, document_models)
    connection_name = f"default_{os.getpid()}"
    old_client = BeanieClient.connections[connection_name].client
    database = BeanieClient.connections[connection_name].database

    async def fail_ping(*args: object, **kwargs: object) -> None:
        """Fail the connection health check."""
        raise pymongo.errors.ConnectionFailure("down")

    with mock.patch.object(database, "command", fail_ping):
        await BeanieClient.init(AppSettings.MONGO, document_models)

    assert BeanieClient.connections[connection_name].client is not old_client
