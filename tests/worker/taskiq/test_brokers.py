"""
Test Brokers.

Test that tasks go through RabbitMQ, and that failed tasks come back through the delay queue to be retried.
"""

import asyncio
import typing

import aio_pika.abc
import pytest
import pytest_asyncio
from taskiq import InMemoryBroker, SmartRetryMiddleware
from taskiq.receiver import Receiver
from taskiq_aio_pika import AioPikaBroker

from sap.worker.taskiq import make_broker
from tests.worker.conftest import AMQP_URL

BROKER_NAME = "sap_tests.brokers"
QUEUE_NAMES = [f"taskiq.{BROKER_NAME}", f"taskiq.{BROKER_NAME}.dead_letter", f"taskiq.{BROKER_NAME}.delay"]


@pytest_asyncio.fixture(name="worker_broker")
async def fixture_worker_broker(amqp_channel: aio_pika.abc.AbstractChannel) -> typing.AsyncIterator[AioPikaBroker]:
    """Start the broker of a worker that retries tasks after a short delay, on fresh queues deleted after the test."""
    for queue_name in QUEUE_NAMES:
        await amqp_channel.queue_delete(queue_name)
    broker = make_broker(AMQP_URL, name=BROKER_NAME, with_retries=True, retry_delay=0.2)
    assert isinstance(broker, AioPikaBroker)
    broker.is_worker_process = True
    await broker.startup()
    yield broker
    await broker.shutdown()
    for queue_name in QUEUE_NAMES:
        await amqp_channel.queue_delete(queue_name)
    await amqp_channel.exchange_delete(f"taskiq.{BROKER_NAME}")


@pytest.mark.parametrize("with_retries", [False, True])
def test_make_broker_in_memory(with_retries: bool) -> None:
    """Run tasks in memory for test cases, and retry them only when asked to."""
    broker = make_broker(AMQP_URL, name=BROKER_NAME, with_retries=with_retries, in_memory=True)
    assert isinstance(broker, InMemoryBroker)
    assert any(isinstance(middleware, SmartRetryMiddleware) for middleware in broker.middlewares) is with_retries


async def test_make_broker_retries_through_the_delay_queue(
    worker_broker: AioPikaBroker, amqp_channel: aio_pika.abc.AbstractChannel
) -> None:
    """Send a failed task to the delay queue, which hands it back to the task queue once the delay is over."""
    attempts: list[str] = []

    async def fail_once(identifier: str) -> None:
        attempts.append(identifier)
        if len(attempts) == 1:
            raise ConnectionError("service unreachable")

    task = worker_broker.register_task(fail_once, task_name=f"{BROKER_NAME}.fail_once", retry_on_error=True)
    receiver = Receiver(worker_broker)
    messages = worker_broker.listen()

    await task.kiq("card_1")
    await receiver.callback(await asyncio.wait_for(anext(messages), timeout=10))  # fails, retried after the delay
    await receiver.callback(await asyncio.wait_for(anext(messages), timeout=10))
    await messages.aclose()

    assert attempts == ["card_1", "card_1"]
    for queue_name in QUEUE_NAMES:  # declared by the broker, and left empty
        queue = await amqp_channel.declare_queue(queue_name, passive=True)
        assert queue.declaration_result.message_count == 0
