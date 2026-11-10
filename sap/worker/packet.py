"""
Packet.

Packets are messages sent through a queue service to run a task on a remote server.
"""

import json
import re
import typing

import aioamqp
import aioamqp.channel
import aioamqp.exceptions
from pamqp.constants import DOMAIN_REGEX

from sap.loggers import logger
from sap.settings import SapSettings

from .amqp import AMQPClient

# from . import exceptions

DOMAIN_REGEX["queue-name"] = re.compile(r"^[a-zA-Z0-9-_.:@#,/><]*$")


class _Packet:
    """
    Define common attributes of packets.

    A Packet represents a message that has been sent to a queue
    in order to execute a task on a remote server.
    """

    namespace: str
    topic: str
    exchange: aioamqp.channel
    _is_durable: bool = True
    _exchange_type: str
    _event_type: str
    connections: dict[str, AMQPClient] = {}
    providing_args: list[str]
    extra_exchange_arguments: dict[str, typing.Any] = {}
    extra_queue_arguments: dict[str, typing.Any] = {}

    def __init__(self, topic: str, providing_args: list[str]):
        """
        Initialize the packet. The topic contains the namespace.

        :providing_args: A list of arguments used for documentation purposes.
        """
        self.topic = topic
        self.namespace = topic.split(".")[0]
        self.providing_args = providing_args

    @classmethod
    async def connection_retrieve(cls) -> AMQPClient:
        """
        Initialize connection to AMQP and save in cache for future use.

        A cached connection that was closed, or opened by another event loop, is replaced by a new one.
        """
        client = cls.connections.get("default")
        if client is not None and not client.is_usable():
            await cls.connection_close()
            client = None
        if client is None:
            client = AMQPClient()
            await client.connect()
            cls.connections["default"] = client
        return client

    @classmethod
    async def connection_close(cls) -> None:
        """Close the cached connection, if any."""
        client = cls.connections.pop("default", None)
        if client is not None:
            await client.close()

    @classmethod
    async def get_default_channel(cls) -> aioamqp.channel.Channel:
        """Return the default channel for the opened connection."""
        connection: AMQPClient = await cls.connection_retrieve()
        return connection.channel

    def exchange_get_name(self, is_fallback: bool = False) -> str:
        """
        Get exchange name.

        :is_fallback: if True, get exchange where dead packets are transferred to.
        """
        suffix: str = ".retry" if is_fallback else ""
        return f"packet.{self._event_type}{suffix}"

    async def exchange_declare(self, is_fallback: bool = False) -> None:
        """
        Declare the exchange on the AMQP server.

        :is_fallback: if True, create a fallback exchange where dead packets are transferred to.
        """
        channel = await self.get_default_channel()
        await channel.exchange_declare(
            exchange_name=self.exchange_get_name(),
            type_name=self._exchange_type,
            durable=self._is_durable,
            arguments=self.extra_exchange_arguments,
        )
        if is_fallback:
            await channel.exchange_declare(
                exchange_name=self.exchange_get_name(is_fallback=True),
                type_name=self._exchange_type,
                durable=self._is_durable,
            )


class SignalPacket(_Packet):
    """
    A SignalPacket is a message sent to the messaging queue broker.

    to run a task asynchronously on remote server.
    Multiple applications can subscribe to the queue to receive the packets.
    """

    _is_durable: bool = True
    _exchange_type: str = "topic"
    _event_type: str = "signal"

    async def send(self, identifier: str, **kwargs: typing.Any) -> None:
        """Send the packet to the exchange."""
        if SapSettings.is_env_dev:
            logger.debug("Lambda Packet sending disabled: %s", self.topic)
            return

        assert (
            "*" not in self.topic and "#" not in self.topic
        ), "Cannot use special matching character in topic to send packet"

        payload = json.dumps({"identifier": identifier, "kwargs": kwargs}).encode("utf-8")

        try:
            await self._publish(payload)
        except aioamqp.exceptions.AioamqpException as exc:
            # The connection was lost after it was checked: publish once more on a new connection.
            logger.warning("Lambda Packet publish failed, reconnecting: topic=%s error=%r", self.topic, exc)
            await self.connection_close()
            await self._publish(payload)

    async def _publish(self, payload: bytes) -> None:
        """Declare the exchange and publish the payload to it."""
        await self.exchange_declare()

        channel = await self.get_default_channel()

        await channel.basic_publish(
            payload=payload,
            exchange_name=self.exchange_get_name(),
            routing_key=self.topic,
            properties={"content_type": "application/json"},
        )

    def queue_get_name(self, task_name: str, is_fallback: bool = False) -> str:
        """
        Get queue name.

        :is_fallback: if True, get queue where dead packets are transferred to.
        """
        suffix: str = "@retry" if is_fallback else ""
        return f"{self._event_type}:{self.topic}->{task_name}{suffix}"

    def queue_get_args(self, is_fallback: bool) -> dict[str, typing.Any]:
        """Get arguments for primary queue."""
        args: dict[str, typing.Any] = {
            "x-dead-letter-exchange": self.exchange_get_name(is_fallback=not is_fallback),  # This is the opposite
        }
        if is_fallback:
            args |= {"x-message-ttl": 1000 * 60 * 60 * 6}  # 6 hours
        else:
            args |= {
                "x-queue-type": "quorum",
                "x-delivery-limit": 5,
            } | self.extra_queue_arguments
        return args

    def queue_get_params(self, task_name: str, is_fallback: bool = False) -> dict[str, typing.Any]:
        """Retrieve params used to declare the queue."""
        return {
            "name": self.queue_get_name(task_name=task_name, is_fallback=is_fallback),
            "exchange": self.exchange_get_name(is_fallback=is_fallback),
            "routing_key": self.topic,
            "durable": True,
            "queue_arguments": self.queue_get_args(is_fallback=is_fallback),
        }

    async def queue_declare(self, task_name: str) -> None:
        """Declare queues and bind them to the exchange."""
        await self.exchange_declare(is_fallback=True)

        channel = await self.get_default_channel()

        # A. Setup queue for dead packets
        params = self.queue_get_params(task_name, is_fallback=True)
        await channel.queue_declare(params["name"], durable=True, arguments=params["queue_arguments"])
        await channel.queue_bind(params["name"], exchange_name=params["exchange"], routing_key=self.topic)

        # B. Setup queue for packets
        params = self.queue_get_params(task_name, is_fallback=False)
        await channel.queue_declare(params["name"], durable=True, arguments=params["queue_arguments"])
        await channel.queue_bind(params["name"], exchange_name=params["exchange"], routing_key=self.topic)
