"""
Fixtures.

Point signal packets to the RabbitMQ server of the test settings, and give tests a channel to inspect it.
Workers on Celery and Taskiq send and receive the same packets.
"""

import typing

import aio_pika
import aio_pika.abc
import pytest
import pytest_asyncio

from AppMain.settings import AppSettings
from sap.settings import SapSettings
from sap.worker.packet import EventPublisher, SignalPacket

AMQP_URL = AppSettings.RABBITMQ.get_dns()


@pytest.fixture(name="packet_sending")
def fixture_packet_sending() -> typing.Iterator[None]:
    """Enable packet sending, which is disabled in dev."""
    is_env_dev = SapSettings.is_env_dev
    SapSettings.is_env_dev = False
    yield
    SapSettings.is_env_dev = is_env_dev


@pytest_asyncio.fixture(name="publisher")
async def fixture_publisher() -> typing.AsyncIterator[EventPublisher]:
    """Publish signal packets with a publisher of the test broker, closed after the test."""
    publisher_default = SignalPacket.publisher
    SignalPacket.publisher = EventPublisher(AMQP_URL)
    yield SignalPacket.publisher
    await SignalPacket.publisher.close()
    SignalPacket.publisher = publisher_default


@pytest_asyncio.fixture(name="amqp_channel")
async def fixture_amqp_channel() -> typing.AsyncIterator[aio_pika.abc.AbstractChannel]:
    """Open a channel to inspect the test broker."""
    connection = await aio_pika.connect_robust(AMQP_URL)
    async with connection:
        yield await connection.channel()
