"""
Beanie Client.

Initialize connection to the Mongo Database.
"""

from __future__ import annotations

import asyncio
import os
import typing
from dataclasses import dataclass
from typing import List, Type

import pymongo.errors
from pymongo import AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase

import beanie

from sap.loggers import logger
from sap.settings import DatabaseParams


@dataclass
class MongoConnection:
    """Mongo client bound to the process and event loop that created it."""

    client: AsyncMongoClient[typing.Any]
    database: AsyncDatabase[typing.Any]
    pid: int  # Track which process created this connection
    loop_id: int
    mongo_params: DatabaseParams
    document_models: list[typing.Any]


class BeanieClient:
    """Set up a connection to the MongoDB server."""

    connections: typing.ClassVar[dict[str, MongoConnection]] = {}

    @classmethod
    async def get_db_default(cls) -> AsyncDatabase[typing.Any]:
        """Return the default db connection."""
        return cls.connections[f"default_{os.getpid()}"].database

    @classmethod
    async def init(
        cls,
        mongo_params: DatabaseParams,
        # document_models: List[Type[beanie.Document] | Type[beanie.View] | str],
        document_models: List[Type[beanie.Document]] | List[Type[beanie.View]] | List[str],
        force: bool = False,
    ) -> None:
        """Open and maintain a connection to the database.

        :force bool: Use it for force a connection initialization

        Detects forked processes and reinitializes connections because the async
        Mongo client is not fork-safe.
        """
        current_pid = os.getpid()
        connection_name = f"default_{current_pid}"
        running_loop_id = id(asyncio.get_running_loop())
        existing = cls.connections.get(connection_name)
        if existing is not None and existing.loop_id != running_loop_id:
            # AsyncMongoClient cannot run on a loop other than the one that created it.
            await cls._discard(connection_name)
            existing = None

        if existing is not None and not force:
            # Check if we're in a forked process (different PID)
            # Same process, check if connection is still healthy
            database: AsyncDatabase[typing.Any] = existing.database

            try:
                # Use a timeout for ping to avoid hanging
                await asyncio.wait_for(database.command("ping"), timeout=2.0)
            except (pymongo.errors.ConnectionFailure, asyncio.TimeoutError, RuntimeError) as exc:
                logger.debug("--> MongoDB connection %s ping failed: %s, reinitializing", connection_name, str(exc))
                await cls._discard(connection_name)
            else:
                logger.debug("--> MongoDB connection %s is healthy", connection_name)
                # await beanie.init_beanie(database, document_models=document_models, allow_index_dropping=False)
                # Connection is healthy, no need to reinitialize
                return

        # Configure connection pool settings for production stability
        client: AsyncMongoClient[typing.Any] = AsyncMongoClient(
            mongo_params.get_dns(),
            maxPoolSize=50,  # Reasonable pool size for multiple workers
            minPoolSize=5,  # Keep some connections warm
            maxIdleTimeMS=45000,  # Close idle connections after 45s
            serverSelectionTimeoutMS=5000,  # Fail fast if server unavailable
            connectTimeoutMS=10000,  # 10s connection timeout
            socketTimeoutMS=30000,  # 30s socket timeout
            retryWrites=True,  # Retry writes on network errors
            retryReads=True,  # Retry reads on network errors
        )
        database = client[mongo_params.db]
        cls.connections[connection_name] = MongoConnection(
            client=client,
            database=database,
            pid=current_pid,
            loop_id=running_loop_id,
            mongo_params=mongo_params,
            document_models=list(document_models),
        )
        await beanie.init_beanie(database, document_models=document_models, allow_index_dropping=False)
        logger.debug("--> Establishing new MongoDB connection (PID: %s)", current_pid)

    @classmethod
    async def reopen_for_current_loop(cls) -> None:
        """Recreate the process client when Celery starts a new event loop."""
        connection_name = f"default_{os.getpid()}"
        existing = cls.connections.get(connection_name)
        if existing is None or existing.loop_id == id(asyncio.get_running_loop()):
            return
        await cls.init(
            mongo_params=existing.mongo_params,
            document_models=existing.document_models,
            force=True,
        )

    @classmethod
    async def _discard(cls, connection_name: str) -> None:
        """Drop a client that can no longer be used."""
        connection = cls.connections.pop(connection_name, None)
        if connection is None:
            return
        try:
            await connection.client.close()
        except (pymongo.errors.PyMongoError, RuntimeError):
            pass
