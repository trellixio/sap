"""
Test Packets.

Test that signal packets reach the queues of the workers that subscribe to them, whatever runs the workers.
"""

import asyncio
import json
import typing
from unittest import mock

import aio_pika
import aio_pika.abc
import aio_pika.exceptions
import pytest

from sap.settings import SapSettings
from sap.worker.packet import EventPublisher, SignalPacket
from tests.worker.conftest import AMQP_URL

CONSUMER_NAME = "sap_tests.PacketConsumer"


def test_signal_packet_matches_received_topics() -> None:
    """Match received topics against the topic pattern of the packet."""
    packet = SignalPacket("sap_tests.*.user.created", providing_args=["identifier"])
    assert packet.namespace == "sap_tests"
    assert packet.matches("sap_tests.card_1.user.created")
    assert not packet.matches("sap_tests.card_1.user.deleted")


def test_signal_packet_queue_params() -> None:
    """Name and configure the queues of a consumer after the topic: a primary queue, and a fallback for dead packets."""
    packet = SignalPacket("stem.#", providing_args=["identifier"])

    assert packet.queue_get_params("trellis.LambdaWorker") == {
        "name": "signal:stem.#->trellis.LambdaWorker",
        "exchange": "packet.signal",
        "routing_key": "stem.#",
        "durable": True,
        "queue_arguments": {
            "x-dead-letter-exchange": "packet.signal.retry",
            "x-queue-type": "quorum",
            "x-delivery-limit": 5,
        },
    }
    assert packet.queue_get_params("trellis.LambdaWorker", is_fallback=True) == {
        "name": "signal:stem.#->trellis.LambdaWorker@retry",
        "exchange": "packet.signal.retry",
        "routing_key": "stem.#",
        "durable": True,
        "queue_arguments": {"x-dead-letter-exchange": "packet.signal", "x-message-ttl": 1000 * 60 * 60 * 6},
    }


@pytest.mark.usefixtures("packet_sending", "publisher")
async def test_signal_packet_reaches_the_queue_of_its_consumers(amqp_channel: aio_pika.abc.AbstractChannel) -> None:
    """Deliver a JSON body with the identifier and kwargs to the queue of every consumer of the topic."""
    packet_consumed = SignalPacket("sap_tests.packet.*.user.created", providing_args=["identifier"])
    queue = await packet_consumed.queue_declare(amqp_channel, task_name=CONSUMER_NAME)
    queue_fallback_name = packet_consumed.queue_get_name(CONSUMER_NAME, is_fallback=True)
    await amqp_channel.declare_queue(queue_fallback_name, passive=True)  # declared along with the primary queue

    await SignalPacket("sap_tests.packet.card_1.user.created", ["identifier"]).send("card_1", timestamp=1)

    message = await queue.get(timeout=5)  # the broker confirmed the publish, the message is already queued
    await message.ack()
    await amqp_channel.queue_delete(queue.name)
    await amqp_channel.queue_delete(queue_fallback_name)
    assert json.loads(message.body) == {"identifier": "card_1", "kwargs": {"timestamp": 1}}
    assert message.content_type == "application/json"
    assert message.routing_key == "sap_tests.packet.card_1.user.created"
    assert message.message_id  # the dispatcher recognizes the packet by its id when it comes back


async def test_signal_packet_send_is_disabled_in_dev(publisher: EventPublisher) -> None:
    """Do not publish anything in the dev environment."""
    with mock.patch.object(SapSettings, "is_env_dev", True), mock.patch.object(publisher, "publish") as publish:
        await SignalPacket("sap_tests.packet.card_1.user.created", ["identifier"]).send("card_1")
    publish.assert_not_called()


@pytest.mark.usefixtures("packet_sending", "publisher")
async def test_signal_packet_send_refuses_topic_patterns() -> None:
    """Refuse to send to a topic pattern, which only makes sense to subscribe."""
    with pytest.raises(ValueError):
        await SignalPacket("sap_tests.packet.*.user.created", ["identifier"]).send("card_1")


async def test_event_publisher_retries_once_on_a_new_connection(publisher: EventPublisher) -> None:
    """Reconnect and publish again once when the broker fails; a second failure is raised."""
    exchange_before = await publisher.connect()
    error = aio_pika.exceptions.AMQPConnectionError("connection lost")

    with mock.patch.object(EventPublisher, "_publish", side_effect=[error, None]) as publish:
        await publisher.publish("sap_tests.packet.card_1.retry.created", b"{}")
    assert publish.await_count == 2
    assert await publisher.connect() is not exchange_before

    with mock.patch.object(EventPublisher, "_publish", side_effect=[error, error]):
        with pytest.raises(aio_pika.exceptions.AMQPConnectionError):
            await publisher.publish("sap_tests.packet.card_1.retry.created", b"{}")


async def test_event_publisher_reconnects_once_when_publishes_fail_together(publisher: EventPublisher) -> None:
    """Keep the new connection of a publish that failed when another publish fails later on the old connection."""
    exchange_failing = await publisher.connect()
    both_published = asyncio.Barrier(2)
    reconnected = asyncio.Event()
    exchanges_retried: list[aio_pika.abc.AbstractExchange] = []

    async def publish_once(exchange: aio_pika.abc.AbstractExchange, *args: typing.Any) -> None:
        if exchange is exchange_failing:
            if await both_published.wait():  # the second publish fails once the first one has reconnected
                await reconnected.wait()
            raise aio_pika.exceptions.AMQPConnectionError("connection lost")
        exchanges_retried.append(exchange)
        reconnected.set()

    with mock.patch.object(EventPublisher, "_publish", side_effect=publish_once):
        await asyncio.gather(
            publisher.publish("sap_tests.packet.card_1.retry.created", b"{}"),
            publisher.publish("sap_tests.packet.card_2.retry.created", b"{}"),
        )
    exchange_new = await publisher.connect()
    assert exchanges_retried == [exchange_new, exchange_new]


def test_event_publisher_reconnects_on_each_event_loop() -> None:
    """Open a new connection when the one cached by the publisher belongs to an event loop that has closed."""
    publisher = EventPublisher(AMQP_URL)

    async def publish(is_last: bool) -> aio_pika.abc.AbstractExchange:
        await publisher.publish("sap_tests.packet.card_1.loop.created", b"{}")
        exchange = await publisher.connect()
        if is_last:
            await publisher.close()
        return exchange

    exchange_first = asyncio.run(asyncio.wait_for(publish(is_last=False), timeout=10))
    exchange_second = asyncio.run(asyncio.wait_for(publish(is_last=True), timeout=10))
    assert exchange_second is not exchange_first


async def test_event_publisher_requires_a_url() -> None:
    """Fail clearly when the publisher was never pointed to a broker."""
    with pytest.raises(AssertionError, match="url"):
        await EventPublisher().publish("sap_tests.packet.card_1.user.created", b"{}")
