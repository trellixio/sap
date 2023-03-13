import typing

from motor.motor_asyncio import AsyncIOMotorClient

import beanie

from sap.settings import DatabaseParams


class BeanieClient:
    """Set up a connection to the MongoDB server."""

    connections: typing.ClassVar[dict[str, AsyncIOMotorClient]] = {}

    @classmethod
    async def init(
        cls,
        mongo_params: DatabaseParams,
        document_models: list[typing.Union[typing.Type[beanie.Document], typing.Type[beanie.View], str]],
    ) -> None:
        """Open and maintain a connection to the database.

        :force bool: Use it for force a connection initialization
        """
        # TODO: Check if connection exist, return existing connection
        if "connection" in cls.connections:
            # connection = cls.connections["connection"]
            return

        client = AsyncIOMotorClient(mongo_params.get_dns())
        connection = client[mongo_params.db]
        cls.connections["default"] = connection
        await beanie.init_beanie(connection, document_models=document_models)
        print("--> Initialized beanie")
