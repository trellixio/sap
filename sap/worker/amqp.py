"""
AMQP.

Establish connection to an AMQP server such as RabbitMQ.
"""

import asyncio

import aioamqp
import aioamqp.channel
import aioamqp.exceptions
import aioamqp.protocol

from sap.settings import DatabaseParams


class AMQPClient:
    """Set up a connection to the AMQP server."""

    transport: asyncio.Transport
    protocol: aioamqp.AmqpProtocol
    channel: aioamqp.channel.Channel
    loop: asyncio.AbstractEventLoop
    db_params: DatabaseParams

    async def connect(self) -> None:
        """
        Establish connect to the AMQP server.

        An `__init__` method can't be a coroutine.
        """
        self.loop = asyncio.get_running_loop()
        self.transport, self.protocol = await aioamqp.connect(
            host=self.db_params.host,
            port=self.db_params.port,
            login=self.db_params.username,
            password=self.db_params.password,
            virtualhost=self.db_params.db,
            ssl=self.db_params.protocol.endswith("s"),
        )
        self.channel = await self.protocol.channel()

    def is_usable(self) -> bool:
        """
        Check that the connection can serve the running event loop.

        The connection is bound to the event loop that opened it: it stops working once that loop closes,
        e.g. after a Celery task's `asyncio.run`, or when the broker drops it.
        """
        return (
            self.loop is asyncio.get_running_loop()
            and self.protocol.state == aioamqp.protocol.OPEN
            and self.channel.is_open
        )

    async def close(self) -> None:
        """Close the channel and the connection, skipping whatever the broker already closed."""
        if self.loop is not asyncio.get_running_loop():
            # The loop that opened the connection is gone: nothing can run on it anymore.
            # Its socket is released when the transport is garbage collected.
            return
        try:
            await asyncio.wait_for(self._close_gracefully(), timeout=5)
        except (aioamqp.exceptions.AioamqpException, TimeoutError):
            pass
        finally:
            self.transport.close()

    async def _close_gracefully(self) -> None:
        """Ask the broker to close the channel, then the connection."""
        if self.channel.is_open:
            await self.channel.close()
        if self.protocol.state == aioamqp.protocol.OPEN:
            await self.protocol.close()
