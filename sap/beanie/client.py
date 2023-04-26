"""
Beanie Client.

Initialize connection to the Mongo Database.
"""
import typing
import asyncio
from dataclasses import dataclass

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


class BeanieClient:
    """Set up a connection to the MongoDB server."""

    connections: typing.ClassVar[dict[str, MongoConnection]] = {}

    @classmethod
    async def get_db_default(cls) -> AsyncIOMotorDatabase:
        """Return the default db connection."""
        return cls.connections["default"].database

    @classmethod
    async def init(
        cls,
        mongo_params: DatabaseParams,
        document_models: list[typing.Union[typing.Type[beanie.Document], typing.Type[beanie.View], str]],
        force: bool = False,
        hijack_motor_loop = True,  # TODO: remove this option, only used for backward compatibility
    ) -> None:
        """Open and maintain a connection to the database.

        :force bool: Use it for force a connection initialization
        """

        if "default" in cls.connections and not force:
            database: AsyncIOMotorDatabase = cls.connections["default"].database

            try:
                await database.command("ping")
            except pymongo.errors.ConnectionFailure:
                logger.debug("--> Invalidate existing MongoDB connection")
            else:
                logger.debug("--> Using existing MongoDB connection")
                return

        client = AsyncIOMotorClient(mongo_params.get_dns())
        if hijack_motor_loop:
            client.get_io_loop = asyncio.get_running_loop
        database = client[mongo_params.db]
        cls.connections["default"] = MongoConnection(client=client, database=database)
        await beanie.init_beanie(database, document_models=document_models, allow_index_dropping=True)
        logger.info("--> Establishing new MongoDB connection")
