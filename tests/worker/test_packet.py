import asyncio
import json
import time
import typing
from unittest import mock

# TODO: Replace aioamqp (deprecated) with aio-pika
import aioamqp.channel
import aioamqp.envelope
import aioamqp.exceptions
import aioamqp.properties
import pytest
import pytest_asyncio

from AppMain.settings import AppSettings
from sap.settings import SapSettings
from sap.worker import AMQPClient, SignalPacket

AMQPClient.db_params = AppSettings.RABBITMQ


@pytest.mark.asyncio
async def test_signal_packet_queue_declaration() -> None:
    """Test that queues are declared successfully"""
    packet = SignalPacket("sap.#", providing_args=["identifier"])
    task_name = "tests.LambdaWorker"

    channel = await packet.get_default_channel()

    queue_primary_name = packet.queue_get_name(task_name=task_name)
    queue_fallback_name = packet.queue_get_name(task_name=task_name, is_fallback=True)

    async def check_queue_exits(channel_: aioamqp.channel.Channel, queue_name: str, result: bool) -> None:
        try:
            await channel_.queue_declare(queue_name=queue_name, passive=True)
        except aioamqp.exceptions.ChannelClosed:
            assert not result, "Checking channel existence return `False`, expecting `True`"
            await channel_.open()
        else:
            assert result, "Checking channel existence return `True`, expecting `False`"

    # A. Ensure that all queues have been deleted
    await channel.queue_delete(queue_name=queue_primary_name)
    await check_queue_exits(channel, queue_primary_name, result=False)
    await channel.queue_delete(queue_name=queue_fallback_name)
    await check_queue_exits(channel, queue_fallback_name, result=False)

    # reset connection
    # await channel.close()
    packet.connections.pop("default")

    # B. Run queue declaration
    await packet.queue_declare(task_name=task_name)

    # Ensure that the queues have been created and binding successfully
    await packet.connection_close()
    channel = await packet.get_default_channel()
    await check_queue_exits(channel, queue_primary_name, result=True)
    await check_queue_exits(channel, queue_fallback_name, result=True)

    # Other: Test that closing connection works when channel is already closed
    await channel.close()
    await packet.connection_close()


@pytest.mark.asyncio
async def test_signal_packet_send() -> None:
    """Testing that sending messages is working."""
    SapSettings.is_env_dev = False
    task_name = "tests.LambdaWorker"
    identifier = "card_12345"
    timestamp = int(time.time())
    result = {}

    # Create received queue
    packet_receiver = SignalPacket("sap.#", providing_args=["identifier"])
    await packet_receiver.queue_declare(task_name=task_name)

    # Create queue consumer client
    async def callback_receiver(
        channel: aioamqp.channel.Channel,
        payload: bytes,
        envelop: aioamqp.envelope.Envelope,
        properties: aioamqp.properties.Properties,
    ) -> None:
        # print(f'Message received {payload=} {properties=}')
        await channel.basic_client_ack(envelop.delivery_tag)
        result["receiver"] = json.loads(payload.decode("utf-8"))
        result["properties"] = properties

    channel = await packet_receiver.get_default_channel()
    await channel.basic_consume(callback_receiver, packet_receiver.queue_get_name(task_name=task_name), no_wait=True)

    # Send messages
    packet_sender = SignalPacket(f"sap.app.{identifier}.user.created", providing_args=["identifier"])
    await packet_sender.send(identifier=identifier, timestamp=timestamp)

    await asyncio.sleep(1)

    # Check that messages has been received
    assert "receiver" in result
    assert result["receiver"]["identifier"] == identifier
    assert result["receiver"]["kwargs"]["timestamp"] == timestamp

    # Test that packet are disable by default in dev
    SapSettings.is_env_dev = True
    await packet_sender.send(identifier=identifier, timestamp=timestamp)
    await packet_sender.connection_close()


@pytest.fixture(name="packet_sending")
def fixture_packet_sending() -> typing.Iterator[None]:
    """Enable packet sending, which is disabled in dev."""
    SapSettings.is_env_dev = False
    yield
    SapSettings.is_env_dev = True


@pytest_asyncio.fixture(name="packet_connection_closed")
async def fixture_packet_connection_closed() -> typing.AsyncIterator[None]:
    """Close the connection opened by the test, even when it fails."""
    yield
    await SignalPacket.connection_close()


@pytest.fixture(name="connection_session_aside")
def fixture_connection_session_aside() -> typing.Iterator[None]:
    """Keep the pytest loop's connection aside while the test opens connections on its own event loops."""
    connection_session = SignalPacket.connections.pop("default", None)
    yield
    if connection_session is not None:
        SignalPacket.connections["default"] = connection_session


@pytest.mark.usefixtures("packet_sending", "connection_session_aside")
def test_signal_packet_send_from_successive_event_loops() -> None:
    """Reconnect when the cached connection was opened by an event loop that has since closed.

    Celery tasks run each call in its own `asyncio.run`, so a task that sends a packet hits this on its second run.
    """
    packet = SignalPacket("sap_tests.app.card_12345.loop.created", providing_args=["identifier"])

    async def send_then_close() -> None:
        await packet.send("card_12345")
        await packet.connection_close()

    asyncio.run(asyncio.wait_for(packet.send("card_12345"), timeout=10))
    asyncio.run(asyncio.wait_for(send_then_close(), timeout=10))  # used to wait forever on the stale connection


@pytest.mark.asyncio
@pytest.mark.usefixtures("packet_sending", "packet_connection_closed")
async def test_signal_packet_send_after_connection_lost() -> None:
    """Open a new connection when the broker dropped the cached one."""
    packet = SignalPacket("sap_tests.app.card_12345.lost.created", providing_args=["identifier"])
    connection_lost = await packet.connection_retrieve()
    connection_lost.transport.abort()  # drop the socket like a broker restart would
    await asyncio.sleep(0.1)

    await asyncio.wait_for(packet.send("card_12345"), timeout=10)

    assert packet.connections["default"] is not connection_lost


@pytest.mark.asyncio
@pytest.mark.usefixtures("packet_sending", "packet_connection_closed")
async def test_signal_packet_send_reconnects_once_when_publish_fails() -> None:
    """Retry a publish once on a new connection; a second failure is raised."""
    packet = SignalPacket("sap_tests.app.card_12345.retry.created", providing_args=["identifier"])
    closed = aioamqp.exceptions.AmqpClosedConnection()
    await packet.exchange_declare()  # the declarations below are mocked, make sure the exchange exists
    connection_first = await packet.connection_retrieve()

    with mock.patch.object(SignalPacket, "exchange_declare", side_effect=[closed, None]) as exchange_declare:
        await packet.send("card_12345")
    assert exchange_declare.await_count == 2
    assert packet.connections["default"] is not connection_first

    with mock.patch.object(SignalPacket, "exchange_declare", side_effect=[closed, closed]):
        with pytest.raises(aioamqp.exceptions.AmqpClosedConnection):
            await packet.send("card_12345")
