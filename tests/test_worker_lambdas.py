import asyncio
import time
import typing

import celery
import celery.worker
import pytest

from AppMain.settings import AppSettings
from sap.worker import AMQPClient, LambdaTask, LambdaWorker, SignalPacket, register_lambda

AMQPClient.db_params = AppSettings.RABBITMQ


class DummyLambdaTask(LambdaTask):
    """Create dummy lambda task class to ensure that LambdaTask class is functioning."""

    results: list[int] = []

    packet = SignalPacket("sap_tests.app.*.user.created", providing_args=["identifier", "timestamp"])

    async def handle_receive(self, *args: str, **kwargs: typing.Any) -> dict[str, typing.Any]:
        self.results.append(kwargs["timestamp"])
        return {"result": True}


def test_lambda_task() -> None:
    """Create dummy lambda task to ensure that LambdaTask class is functioning."""
    task = register_lambda(DummyLambdaTask)
    result = task.run(timestamp=1)
    assert "result" in result


class DummyLambdaWorker(LambdaWorker):
    """Create a dummy Lambda worker for testing."""

    packets = [SignalPacket("sap_tests.#", providing_args=["identifier", "kwargs"])]
    name = "tests.LambdaWorker"

    def get_task_list(self) -> list[LambdaTask]:
        """Register dummy task."""
        return [register_lambda(DummyLambdaTask)]


@pytest.fixture
def setup_celery_app(celery_app: celery.Celery) -> None:
    """Setting up Celery worker"""
    celery_app.register_task(register_lambda(DummyLambdaTask))
    celery_app.steps["consumer"].add(DummyLambdaWorker)


@pytest.mark.asyncio
async def test_lambda_worker(setup_celery_app: None, celery_worker: celery.worker.WorkController) -> None:
    """Create dummy lambda worker to ensure that LambdaWorker class is functioning."""
    identifier = "card_12345"
    timestamp = int(time.time())

    # Send packet
    packet_yes = SignalPacket(f"sap_tests.app.{identifier}.user.created", providing_args=["identifier", "timestamp"])
    packet_no = SignalPacket(f"sap_tests.app.{identifier}.merchant.updated", providing_args=["identifier", "timestamp"])
    # print(f"---> Sending packet {identifier=} {timestamp=}")
    await packet_yes.send(identifier, timestamp=timestamp + 1)
    await packet_no.send(identifier, timestamp=timestamp + 2)
    await packet_yes.send(identifier, timestamp=timestamp + 3)
    await packet_no.send(identifier, timestamp=timestamp + 4)

    await asyncio.sleep(3)

    assert timestamp + 1 in DummyLambdaTask.results
    assert timestamp + 2 not in DummyLambdaTask.results
    assert timestamp + 3 in DummyLambdaTask.results
    assert timestamp + 4 not in DummyLambdaTask.results
