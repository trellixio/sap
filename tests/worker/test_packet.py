import asyncio
import json
import time

import aioamqp.channel
import aioamqp.envelope
import aioamqp.exceptions
import aioamqp.properties
import pytest

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
    await packet.connection_reset()
    channel = await packet.get_default_channel()
    await check_queue_exits(channel, queue_primary_name, result=True)
    await check_queue_exits(channel, queue_fallback_name, result=True)

    # Other: Test that reset connection works when channel is already closed
    await channel.close()
    await packet.connection_reset()


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
