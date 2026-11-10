"""
Dispatcher.

The dispatcher consumes the packets that services send to the signal exchange,
and kicks the task of every lambda handler whose topic matches the packet.

It runs in a process of its own, as the `taskiq scheduler` does for crons:
`python -m sap.worker.taskiq AppMain.taskiq.lambdas:dispatcher`.
"""

import asyncio
import importlib
import json
import signal
from collections import OrderedDict
from typing import Any, ClassVar, Optional, Sequence

import aio_pika
import aio_pika.abc

from sap.loggers import logger
from sap.worker.packet import SignalPacket
from sap.worker.topics import match_amqp_topics

from .lambdas import RegisteredLambda


class EventDispatcher:  # pylint: disable=too-many-instance-attributes
    """
    Consume the packets a worker subscribes to, and kick a lambda task per matching handler.

    Each packet gets the queues of `sap.worker.packet`, named after its topic and the worker,
    so the dispatcher takes over the queues of a Celery `LambdaWorker` of the same name.
    A packet is acknowledged once all its tasks are kicked. If kicking fails, the packet goes back to the queue,
    which dead-letters it after a few attempts. A packet that is not a JSON object is dead-lettered right away.

    When a packet comes back after a failure, the tasks already kicked for it are skipped, so they do not run twice.
    The dispatcher remembers them in memory, by the message id that `EventPublisher` gives every packet:
    packets without a message id, or that come back to another dispatcher process, kick all their tasks again.
    """

    kicked_limit: ClassVar[int] = 10_000  # packets whose kicked tasks are remembered, the oldest are forgotten first

    url: str
    name: str
    packets: Sequence[SignalPacket]
    handlers: Sequence[RegisteredLambda]
    blocked_identifiers: Sequence[str]
    prefetch_count: int

    def __init__(
        self,
        url: str,
        *,
        name: str,
        packets: Sequence[SignalPacket],
        handlers: Sequence[RegisteredLambda],
        blocked_identifiers: Sequence[str] = (),
        prefetch_count: int = 10,
    ) -> None:
        """
        Initialize the dispatcher; nothing is opened before it starts.

        :name: name of the worker, such as `trellis.LambdaWorker`, used to name its queues.
        :packets: packets the worker subscribes to, such as `SignalPacket("stem.#", ...)`.
        :handlers: lambda tasks, as returned by `register_lambda`.
        :blocked_identifiers: packets whose topic has one of these identifiers as a word are dropped,
            such as `card_1` in `stem.card_1.credit.created`.
        """
        self.url = url
        self.name = name
        self.packets = packets
        self.handlers = handlers
        self.blocked_identifiers = blocked_identifiers
        self.prefetch_count = prefetch_count
        self._connection: Optional[aio_pika.abc.AbstractRobustConnection] = None
        self._kicked: OrderedDict[str, set[str]] = OrderedDict()  # message id -> tasks kicked before a failure

    async def run(self, stop_event: Optional[asyncio.Event] = None) -> None:
        """
        Dispatch packets until the process gets SIGINT or SIGTERM, or until `stop_event` is set.

        The brokers of the handlers start before the packets are consumed, so every packet received can be kicked.
        """
        stop_event = stop_event or asyncio.Event()
        loop = asyncio.get_running_loop()
        for signal_number in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(signal_number, stop_event.set)

        brokers = list(dict.fromkeys(handler.broker for handler in self.handlers))
        for broker in brokers:
            await broker.startup()
        await self.start()

        await stop_event.wait()

        await self.stop()
        for broker in brokers:
            await broker.shutdown()
        for signal_number in (signal.SIGINT, signal.SIGTERM):
            loop.remove_signal_handler(signal_number)

    async def start(self) -> None:
        """Declare the queues of the packets and start consuming them."""
        self._connection = await aio_pika.connect_robust(self.url)
        channel = await self._connection.channel()
        await channel.set_qos(prefetch_count=self.prefetch_count)
        for packet in self.packets:
            queue = await packet.queue_declare(channel, task_name=self.name)
            await queue.consume(self.on_message)
            logger.info("Dispatching packets from queue=%s", queue.name)

    async def stop(self) -> None:
        """Stop consuming packets; the packets received but not yet acknowledged go back to their queue."""
        if self._connection is not None:
            await self._connection.close()
            self._connection = None

    async def on_message(self, message: aio_pika.abc.AbstractIncomingMessage) -> None:
        """Dispatch an event received from the queue, then acknowledge it."""
        topic = message.routing_key or ""
        body = self.parse_body(message.body)
        if body is None:
            logger.error("Rejecting event that is not a JSON object: topic=%s body=%r", topic, message.body[:200])
            await message.reject(requeue=False)
            return

        try:
            await self.dispatch(topic, body, message_id=message.message_id)
        except Exception:  # pylint: disable=broad-except
            logger.exception("Event dispatch failed, requeuing: topic=%s", topic)
            await message.nack(requeue=True)
        else:
            await message.ack()

    @staticmethod
    def parse_body(raw_body: bytes) -> Optional[dict[str, Any]]:
        """Decode the JSON object of an event, or return None if it is not one."""
        try:
            body = json.loads(raw_body)
        except ValueError:
            return None
        return body if isinstance(body, dict) else None

    async def dispatch(self, topic: str, body: dict[str, Any], message_id: Optional[str] = None) -> int:
        """
        Kick the task of every handler whose topic matches the event, and return how many were kicked.

        If a kick fails, the tasks kicked before it are remembered under the message id,
        and skipped when the event is dispatched again.
        """
        if not set(self.blocked_identifiers).isdisjoint(topic.split(".")):
            logger.info("Dropping event of a blocked identifier: topic=%s", topic)
            return 0

        # `card_pid` and `clover_id` are the identifiers of older events.
        identifier = body.get("identifier") or body.get("card_pid") or body.get("clover_id")
        kwargs = body.get("kwargs") or {}
        handlers = [handler for handler in self.handlers if match_amqp_topics(handler.labels["topic"], topic)]
        kicked = self._kicked.pop(message_id, set()) if message_id else set()
        try:
            return await self._kick(handlers, kicked, identifier, kwargs)
        except Exception:
            if message_id and kicked:
                self._remember_kicked(message_id, kicked)
            raise

    @staticmethod
    async def _kick(handlers: list[RegisteredLambda], kicked: set[str], identifier: Any, kwargs: dict[str, Any]) -> int:
        """Kick the tasks of the handlers that are not in `kicked`, add each to it, and return how many were kicked."""
        kicked_before = len(kicked)
        for handler in handlers:
            if handler.task_name not in kicked:
                await handler.kiq(identifier, **kwargs)
                kicked.add(handler.task_name)
        return len(kicked) - kicked_before

    def _remember_kicked(self, message_id: str, kicked: set[str]) -> None:
        """Remember the tasks kicked for an event that failed to dispatch, forgetting the oldest event over the limit."""
        self._kicked[message_id] = kicked
        if len(self._kicked) > self.kicked_limit:
            self._kicked.popitem(last=False)


def load_dispatcher(path: str) -> EventDispatcher:
    """Import the dispatcher at `module:attribute`, such as `AppMain.taskiq.lambdas:dispatcher`."""
    module_name, _, attribute = path.partition(":")
    dispatcher = getattr(importlib.import_module(module_name), attribute)
    if not isinstance(dispatcher, EventDispatcher):
        raise TypeError(f"{path} is not an EventDispatcher.")
    return dispatcher
