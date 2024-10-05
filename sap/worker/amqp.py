"""
AMQP.

Establish connection to an AMQP server such as RabbitMQ.
"""

import asyncio

import aioamqp
import aioamqp.channel

from sap.settings import DatabaseParams


class AMQPClient:
    """Set up a connection to the AMQP server."""

    transport: asyncio.Transport
    protocol: aioamqp.AmqpProtocol
    channel: aioamqp.channel.Channel
    db_params: DatabaseParams

    async def connect(self) -> None:
        """
        Establish connect to the AMQP server.

        An `__init__` method can't be a coroutine.
        """
        self.transport, self.protocol = await aioamqp.connect(
            host=self.db_params.host,
            port=self.db_params.port,
            login=self.db_params.username,
            password=self.db_params.password,
            virtualhost=self.db_params.db,
            ssl=self.db_params.protocol.endswith("s"),
        )
        self.channel = await self.protocol.channel()
