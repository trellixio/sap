"""
Beanie Client.

Initialize connection to the Mongo Database.
"""

from __future__ import annotations

import asyncio
import typing
from dataclasses import dataclass
from typing import Any, List, Mapping, Type

import pymongo.errors
from pymongo import AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase

import beanie

from sap.loggers import logger
from sap.settings import DatabaseParams


@dataclass
class MongoConnection:
    """Define a standard cron task response."""

    client: AsyncMongoClient[Mapping[str, Any]]
    database: AsyncDatabase[Mapping[str, Any]]


class BeanieClient:
    """Set up a connection to the MongoDB server."""

    connections: typing.ClassVar[dict[str, MongoConnection]] = {}

    @classmethod
    async def get_db_default(cls) -> AsyncDatabase[Mapping[str, Any]]:
        """Return the default db connection."""
        return cls.connections["default"].database

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
        """

        if "default" in cls.connections and not force:
            database: AsyncDatabase[Mapping[str, Any]] = cls.connections["default"].database

            try:
                await database.command("ping")
            except (pymongo.errors.ConnectionFailure, RuntimeError):
                logger.debug("--> Invalidate existing MongoDB connection")
            else:
                logger.debug("--> Using existing MongoDB connection")
                return

        client: AsyncMongoClient[Mapping[str, Any]] = AsyncMongoClient(mongo_params.get_dns())
        # if hijack_motor_loop:
        client.get_io_loop = asyncio.get_running_loop  # type: ignore
        database = client[mongo_params.db]
        cls.connections["default"] = MongoConnection(client=client, database=database)
        await beanie.init_beanie(database, document_models=document_models, allow_index_dropping=True)
        logger.info("--> Establishing new MongoDB connection")
