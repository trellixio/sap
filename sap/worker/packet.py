"""
Packet.

Packets are messages sent through RabbitMQ to run lambdas on remote servers, whatever runs them.
A signal packet goes to the `packet.signal` topic exchange, as a JSON body `{"identifier": ..., "kwargs": {...}}`
routed by a topic such as `stem.card_1.credit.created`: every service whose queue subscribes to the topic gets it.

It needs the `amqp` extra, which the `taskiq` and `celery` extras include.
"""

import asyncio
import json
import re
import uuid
from typing import Any, ClassVar, Optional

try:
    import aio_pika
except ImportError as exc:
    raise ImportError("sap.worker.packet needs the amqp extra: pip install 'sapx[amqp]'") from exc

import aio_pika.abc
import aio_pika.exceptions
from pamqp.constants import DOMAIN_REGEX

from sap.loggers import logger
from sap.settings import SapSettings
from sap.worker.topics import match_amqp_topics

# Queues are named after the topics they subscribe to, such as `signal:stem.*.credit.created->trellis.LambdaWorker`.
# RabbitMQ accepts these names, but pamqp refuses the characters that are not in the AMQP spec.
DOMAIN_REGEX["queue-name"] = re.compile(r"^[a-zA-Z0-9-_.:@#*,/><]*$")

SIGNAL_EXCHANGE = "packet.signal"

PUBLISH_ERRORS = (aio_pika.exceptions.AMQPError, aio_pika.exceptions.ChannelInvalidStateError, ConnectionError)


class EventPublisher:
    """
    Publish packets on the signal exchange over one robust connection.

    The connection opens on the first publish and is reused afterwards; aio-pika restores it when the broker drops it.
    Every publish waits for the broker to confirm it, and gets a message id that consumers can recognize it by.
    A connection opened by an event loop that has since closed is replaced,
    so scripts and Celery tasks that call `asyncio.run` several times keep working.
    """

    url: Optional[str]
    exchange_name: str

    def __init__(self, url: Optional[str] = None, exchange_name: str = SIGNAL_EXCHANGE) -> None:
        """Initialize the publisher; nothing is opened before the first publish."""
        self.url = url
        self.exchange_name = exchange_name
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._lock: Optional[asyncio.Lock] = None
        self._connection: Optional[aio_pika.abc.AbstractRobustConnection] = None
        self._exchange: Optional[aio_pika.abc.AbstractExchange] = None

    async def connect(self) -> aio_pika.abc.AbstractExchange:
        """Open the connection and declare the exchange, unless it is already done on this event loop."""
        loop = asyncio.get_running_loop()
        if self._loop is not loop:
            # The previous loop is gone and its connection with it: the socket is released on garbage collection.
            self._loop, self._lock = loop, asyncio.Lock()
            self._connection = self._exchange = None
        assert self._lock
        async with self._lock:
            if self._connection is None or self._exchange is None:
                assert self.url, "Set the EventPublisher url before publishing."
                self._connection = await aio_pika.connect_robust(self.url)
                channel = await self._connection.channel(publisher_confirms=True)
                self._exchange = await channel.declare_exchange(
                    self.exchange_name, aio_pika.ExchangeType.TOPIC, durable=True
                )
            return self._exchange

    async def close(self) -> None:
        """Close the connection, if this event loop opened one."""
        connection, self._connection, self._exchange = self._connection, None, None
        if connection is not None and self._loop is asyncio.get_running_loop():
            await connection.close()

    async def publish(self, topic: str, body: bytes) -> None:
        """Publish the body with the topic as routing key; retry once on a new connection if the broker fails."""
        message = aio_pika.Message(
            body,
            content_type="application/json",
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            message_id=uuid.uuid4().hex,
        )
        exchange = await self.connect()
        try:
            await self._publish(exchange, topic, message)
        except PUBLISH_ERRORS as exc:
            logger.warning("Lambda Packet publish failed, reconnecting: topic=%s error=%r", topic, exc)
            await self._discard(exchange)
            await self._publish(await self.connect(), topic, message)

    @staticmethod
    async def _publish(exchange: aio_pika.abc.AbstractExchange, topic: str, message: aio_pika.Message) -> None:
        """Publish the message on the exchange."""
        # Not mandatory: a topic that no service listens to is dropped, as with any topic exchange.
        await exchange.publish(message, routing_key=topic, mandatory=False)

    async def _discard(self, exchange: aio_pika.abc.AbstractExchange) -> None:
        """
        Close the connection of an exchange that failed to publish, so the next publish opens a new one.

        Publishes that fail together all discard the same exchange: only the first one closes its connection,
        the others find it replaced and keep the new one.
        """
        assert self._lock
        async with self._lock:
            if self._exchange is not exchange:
                return
            connection, self._connection, self._exchange = self._connection, None, None
        if connection is not None:
            await connection.close()


class SignalPacket:
    """
    A SignalPacket is a message sent to the messaging queue broker, to run lambdas on remote servers.

    Multiple applications can subscribe to the topic to receive the packets.
    Lambdas declare the topic pattern they react to, such as `stem.*.credit.created`;
    senders use a full topic, such as `stem.card_1.credit.created`.
    Point the publisher to the broker once at startup: `SignalPacket.publisher.url = ...`.
    """

    publisher: ClassVar[EventPublisher] = EventPublisher()
    event_type: ClassVar[str] = "signal"
    topic: str
    namespace: str
    providing_args: list[str]
    extra_queue_arguments: dict[str, Any] = {}

    def __init__(self, topic: str, providing_args: list[str]) -> None:
        """
        Initialize the packet. The topic contains the namespace.

        :providing_args: A list of arguments used for documentation purposes.
        """
        self.topic = topic
        self.namespace = topic.split(".")[0]
        self.providing_args = providing_args

    def matches(self, topic: str) -> bool:
        """Check that a received topic matches the topic pattern of this packet."""
        return match_amqp_topics(self.topic, topic)

    async def send(self, identifier: str, **kwargs: Any) -> None:
        """Send the packet to the exchange."""
        if SapSettings.is_env_dev:
            logger.debug("Lambda Packet sending disabled: %s", self.topic)
            return

        if "*" in self.topic or "#" in self.topic:
            raise ValueError(f"Cannot send a packet to the topic pattern {self.topic}, use a full topic.")

        body = json.dumps({"identifier": identifier, "kwargs": kwargs}).encode("utf-8")
        await self.publisher.publish(self.topic, body)

    def exchange_get_name(self, is_fallback: bool = False) -> str:
        """
        Get exchange name.

        :is_fallback: if True, get exchange where dead packets are transferred to.
        """
        suffix: str = ".retry" if is_fallback else ""
        return f"packet.{self.event_type}{suffix}"

    def queue_get_name(self, task_name: str, is_fallback: bool = False) -> str:
        """
        Get queue name.

        :is_fallback: if True, get queue where dead packets are transferred to.
        """
        suffix: str = "@retry" if is_fallback else ""
        return f"{self.event_type}:{self.topic}->{task_name}{suffix}"

    def queue_get_args(self, is_fallback: bool) -> dict[str, Any]:
        """Get arguments for primary queue."""
        args: dict[str, Any] = {
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

    def queue_get_params(self, task_name: str, is_fallback: bool = False) -> dict[str, Any]:
        """Retrieve params used to declare the queue."""
        return {
            "name": self.queue_get_name(task_name=task_name, is_fallback=is_fallback),
            "exchange": self.exchange_get_name(is_fallback=is_fallback),
            "routing_key": self.topic,
            "durable": True,
            "queue_arguments": self.queue_get_args(is_fallback=is_fallback),
        }

    async def queue_declare(self, channel: aio_pika.abc.AbstractChannel, task_name: str) -> aio_pika.abc.AbstractQueue:
        """
        Declare the queues of a consumer and bind them to their exchange.

        The primary queue receives the packets; packets that it dead-letters wait in the fallback queue,
        which sends them back to the exchange after a while. Return the primary queue, to consume it.
        """
        queue: Optional[aio_pika.abc.AbstractQueue] = None
        for is_fallback in (True, False):
            params = self.queue_get_params(task_name, is_fallback=is_fallback)
            exchange = await channel.declare_exchange(params["exchange"], aio_pika.ExchangeType.TOPIC, durable=True)
            queue = await channel.declare_queue(params["name"], durable=True, arguments=params["queue_arguments"])
            await queue.bind(exchange, routing_key=self.topic)
        assert queue
        return queue
