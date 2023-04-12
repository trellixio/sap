"""
Packet.

Packets are messages sent through a queue service to run a task on a remote server.
"""
import json
import re
import typing

import aioamqp
import aioamqp.channel
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
        """Initialize connection to AMQP and save in cache for future use."""
        if "default" not in cls.connections:
            client = AMQPClient()
            await client.connect()
            cls.connections["default"] = client
        return cls.connections["default"]

    @classmethod
    async def connection_reset(cls) -> None:
        channel = await cls.get_default_channel()
        if channel.is_open:
            await channel.close()
        cls.connections.pop("default")

    @classmethod
    async def get_default_channel(cls) -> aioamqp.channel.Channel:
        """Return the default channel for the opened connection."""
        connection: AMQPClient = await cls.connection_retrieve()
        # if not connection.channel.is_open:
        #     cls.connections.pop('default')
        #     connection = await cls.connection_retrieve()
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

        await self.exchange_declare()

        channel = await self.get_default_channel()

        payload = json.dumps({"identifier": identifier, "kwargs": kwargs})

        await channel.basic_publish(
            payload=payload.encode("utf-8"),
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

    def queue_get_params(self, task_name: str, is_fallback: bool = False) -> dict[str, typing.Any]:
        """Retrieve params used to declare the queue."""
        name = self.queue_get_name(task_name=task_name, is_fallback=is_fallback)
        exchange_primary = self.exchange_get_name(is_fallback=False)
        exchange_fallback = self.exchange_get_name(is_fallback=True)
        arguments = {
            "x-delivery-limit": 5,
            "x-dead-letter-exchange": exchange_primary if is_fallback else exchange_fallback,
        }
        if is_fallback:
            arguments["x-message-ttl"] = 1000 * 60 * 60 * 6  # 6 hours
        else:
            arguments["x-queue-type"] = "quorum"
        return {
            "name": name,
            "exchange": exchange_fallback if is_fallback else exchange_primary,
            "routing_key": self.topic,
            "durable": True,
            "queue_arguments": arguments,
        }

    async def queue_declare(self, task_name: str) -> None:
        """Declare queues and bind them to the exchange."""
        await self.exchange_declare(is_fallback=True)

        channel = await self.get_default_channel()

        exchange_name = self.exchange_get_name()
        queue_name = self.queue_get_name(task_name)
        exchange_name_dead = self.exchange_get_name(is_fallback=True)
        queue_name_dead = self.queue_get_name(task_name, is_fallback=True)

        # A. Setup queue for dead packets
        await channel.queue_declare(
            queue_name=queue_name_dead,
            durable=True,
            arguments={
                "x-delivery-limit": 5,
                "x-message-ttl": 1000 * 60 * 60 * 6,  # 6 hours
                "x-dead-letter-exchange": exchange_name,
            },
        )
        await channel.queue_bind(queue_name=queue_name_dead, exchange_name=exchange_name_dead, routing_key=self.topic)

        # B. Setup queue for packets
        await channel.queue_declare(
            queue_name=queue_name,
            durable=True,
            arguments={
                "x-queue-type": "quorum",
                "x-delivery-limit": 5,
                "x-dead-letter-exchange": exchange_name_dead,
            },
        )
        await channel.queue_bind(queue_name=queue_name, exchange_name=exchange_name, routing_key=self.topic)
