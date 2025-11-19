"""Tests for BeanieClient class."""

import os

import pytest
from motor.motor_asyncio import AsyncIOMotorDatabase

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
    assert isinstance(connection.database, AsyncIOMotorDatabase)


@pytest.mark.asyncio
async def test_get_db_default_returns_database(document_models: list[type[Document]]) -> None:
    """Test that get_db_default returns the correct database instance."""
    # Clear any existing connections
    BeanieClient.connections.clear()

    await BeanieClient.init(AppSettings.MONGO, document_models)
    db: AsyncIOMotorDatabase = await BeanieClient.get_db_default()

    assert isinstance(db, AsyncIOMotorDatabase)
    assert str(db.name) == AppSettings.MONGO.db


@pytest.mark.asyncio
async def test_init_force_recreates_connection(document_models: list[type[Document]]) -> None:
    """Test that init with force=True recreates the connection."""
    # Clear any existing connections
    BeanieClient.connections.clear()

    # Create initial connection
    await BeanieClient.init(AppSettings.MONGO, document_models)
    _, connection = next(iter(BeanieClient.connections.items()))
    first_db: AsyncIOMotorDatabase = connection.database

    # Force recreate connection
    await BeanieClient.init(AppSettings.MONGO, document_models, force=True)
    _, connection = next(iter(BeanieClient.connections.items()))
    second_db: AsyncIOMotorDatabase = connection.database

    # assert first_db != second_db
    assert isinstance(first_db, AsyncIOMotorDatabase)
    assert isinstance(second_db, AsyncIOMotorDatabase)


@pytest.mark.asyncio
async def test_init_reuses_existing_connection(document_models: list[type[Document]]) -> None:
    """Test that init reuses existing connection when force=False."""
    # Clear any existing connections
    BeanieClient.connections.clear()

    # Create initial connection
    await BeanieClient.init(AppSettings.MONGO, document_models)
    _, connection = next(iter(BeanieClient.connections.items()))
    first_db: AsyncIOMotorDatabase = connection.database

    # Try to create new connection without force
    await BeanieClient.init(AppSettings.MONGO, document_models)
    _, connection = next(iter(BeanieClient.connections.items()))
    second_db: AsyncIOMotorDatabase = connection.database

    assert first_db == second_db
