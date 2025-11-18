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
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

import beanie

from sap.loggers import logger
from sap.settings import DatabaseParams


@dataclass
class MongoConnection:
    """Define a standard cron task response."""

    client: AsyncIOMotorClient
    database: AsyncIOMotorDatabase
    pid: int  # Track which process created this connection


class BeanieClient:
    """Set up a connection to the MongoDB server."""

    connections: typing.ClassVar[dict[str, MongoConnection]] = {}

    @classmethod
    async def get_db_default(cls) -> AsyncIOMotorDatabase:
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

        CRITICAL: Detects forked processes (Gunicorn workers) and automatically
        reinitializes connections since Motor's AsyncIOMotorClient is NOT fork-safe.
        """
        current_pid = os.getpid()
        connection_name = f"default_{current_pid}"

        if connection_name in cls.connections and not force:
            # Check if we're in a forked process (different PID)
            # Same process, check if connection is still healthy
            database: AsyncIOMotorDatabase = cls.connections[connection_name].database

            try:
                # Use a timeout for ping to avoid hanging
                await asyncio.wait_for(database.command("ping"), timeout=2.0)
            except (pymongo.errors.ConnectionFailure, asyncio.TimeoutError) as exc:
                logger.debug("--> MongoDB connection %s ping failed: %s, reinitializing", connection_name, str(exc))
                # Close the old client before creating a new one
                try:
                    cls.connections[connection_name].client.close()
                except pymongo.errors.PyMongoError:
                    pass
                del cls.connections[connection_name]
            else:
                # Connection is healthy, no need to reinitialize
                return

        # Configure connection pool settings for production stability
        client = AsyncIOMotorClient(
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
        # if hijack_motor_loop:
        client.get_io_loop = asyncio.get_running_loop  # type: ignore
        database = client[mongo_params.db]
        cls.connections[connection_name] = MongoConnection(client=client, database=database, pid=current_pid)
        await beanie.init_beanie(database, document_models=document_models, allow_index_dropping=True)
        logger.debug("--> Establishing new MongoDB connection (PID: %s)", current_pid)
