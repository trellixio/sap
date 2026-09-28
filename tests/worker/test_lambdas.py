import asyncio
import time
import typing
from unittest import mock

import celery
import celery.worker
import pytest

from AppMain.settings import AppSettings
from sap.beanie.client import BeanieClient
from sap.settings import SapSettings
from sap.worker import AMQPClient, LambdaTask, LambdaWorker, SignalPacket, register_lambda
from sap.worker.lambdas import HealthCheckLambda, LambdaResponse
from tests.samples import DummyDoc

AMQPClient.db_params = AppSettings.RABBITMQ


class DummyLambdaTask(LambdaTask):
    """Create dummy lambda task class to ensure that LambdaTask class is functioning."""

    results: list[int] = []

    packet = SignalPacket("sap_tests.app.*.user.created", providing_args=["identifier", "timestamp"])

    async def handle_process(self, *args: str, **kwargs: typing.Any) -> LambdaResponse:
        await BeanieClient.init(mongo_params=AppSettings.MONGO, document_models=[DummyDoc])
        doc = await DummyDoc(num=kwargs["timestamp"], name="lambda task run").create()
        assert doc.id, "DummyDoc has not been created"
        await doc.delete()
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
    name = "tests.DummyLambdaWorker"

    def get_task_list(self) -> list[LambdaTask]:
        """Register dummy task."""
        return [register_lambda(DummyLambdaTask)]


@pytest.fixture(name="setup_celery_app")
def fixture_setup_celery_app(celery_app: celery.Celery) -> bool:
    """Setting up Celery worker"""
    celery_app.register_task(register_lambda(DummyLambdaTask))
    celery_app.steps["consumer"].add(DummyLambdaWorker)
    return True


@pytest.mark.asyncio
async def test_lambda_worker(setup_celery_app: bool, celery_worker: celery.worker.WorkController) -> None:  # type: ignore
    """Create dummy lambda worker to ensure that LambdaWorker class is functioning."""
    assert setup_celery_app and celery_worker

    identifier = "card_12345"
    timestamp = int(time.time())

    SapSettings.is_env_dev = False

    # Send packet
    packet_yes = SignalPacket(f"sap_tests.app.{identifier}.user.created", providing_args=["identifier", "timestamp"])
    packet_no = SignalPacket(f"sap_tests.app.{identifier}.merchant.updated", providing_args=["identifier", "timestamp"])
    # print(f"---> Sending packet {identifier=} {timestamp=}")
    await packet_yes.send(identifier, timestamp=timestamp + 1)
    await packet_no.send(identifier, timestamp=timestamp + 2)
    await packet_yes.send(identifier, timestamp=timestamp + 3)
    await packet_no.send(identifier, timestamp=timestamp + 4)

    await packet_yes.connection_close()
    await packet_no.connection_close()

    await asyncio.sleep(3)

    assert timestamp + 1 in DummyLambdaTask.results
    assert timestamp + 2 not in DummyLambdaTask.results
    assert timestamp + 3 in DummyLambdaTask.results
    assert timestamp + 4 not in DummyLambdaTask.results

    SapSettings.is_env_dev = True


class RecordingLambda(LambdaTask):
    """Lambda task that records it was handled."""

    packet = SignalPacket("sap.test.created", providing_args=["identifier"])
    handled: list[str] = []

    async def handle_process(self, *args: str, **kwargs: typing.Any) -> LambdaResponse:
        """Record the identifier and return success."""
        self.handled.append(str(args[0]) if args else "")
        return {"result": True}


class ConsumeWorker(LambdaWorker):
    """Worker whose signal propagation can be forced to fail."""

    packets = [SignalPacket("sap.#", providing_args=["identifier"])]
    name = "tests.ConsumeWorker"
    fail = False

    def get_task_list(self) -> list[LambdaTask]:
        """Return no tasks; consume is tested through a stub."""
        return []

    def _propagate_signal(self, body: dict[str, typing.Any], message: typing.Any) -> None:
        """Raise when the test asks for a failure."""
        if self.fail:
            raise RuntimeError("propagation failed")


class SyncLambdaWorker(DummyLambdaWorker):
    """Lambda worker that executes tasks in process."""

    is_async = False


def http_client(status_code: int) -> mock.Mock:
    """Build an async HTTP client stub that returns one status code."""
    entered = mock.AsyncMock()
    entered.head.return_value = mock.Mock(status_code=status_code)
    client = mock.MagicMock()
    client.__aenter__ = mock.AsyncMock(return_value=entered)
    client.__aexit__ = mock.AsyncMock(return_value=None)
    return client


@pytest.mark.asyncio
async def test_lambda_test_process() -> None:
    """Delegate test_process to the task handler."""
    task = RecordingLambda()
    result = await task.test_process("card")
    assert result == {"result": True}
    assert task.handled == ["card"]


def test_lambda_consume_ack_and_reject() -> None:
    """Ack a consumed packet, and reject it when propagation fails."""
    worker = ConsumeWorker.__new__(ConsumeWorker)
    worker.fail = False
    success = mock.Mock()
    success.delivery_info = {"routing_key": "sap.app.card.user.created"}
    success.headers = {"x-death": [{"count": 1}]}
    worker.consume({"identifier": "card", "kwargs": {}}, success)
    success.ack.assert_called_once()

    worker.fail = True
    failure = mock.Mock()
    failure.delivery_info = {"routing_key": "sap.app.card.user.created"}
    failure.headers = {}
    worker.consume({"identifier": "card", "kwargs": {}}, failure)
    failure.reject.assert_called_once()


def test_lambda_worker_runs_sync_tasks() -> None:
    """Call apply when the worker is not async."""
    message = mock.Mock()
    message.delivery_info = {"routing_key": "sap_tests.app.card.user.created"}
    worker = SyncLambdaWorker.__new__(SyncLambdaWorker)
    with mock.patch.object(DummyLambdaTask, "apply") as apply:
        worker._propagate_signal(  # pylint: disable=protected-access
            {"identifier": "card", "kwargs": {"timestamp": 1}}, message
        )
    apply.assert_called_once_with(args=("card",), kwargs={"timestamp": 1})


@pytest.mark.asyncio
async def test_health_check_lambda_heartbeat() -> None:
    """Head the heartbeat URL and reject any status other than 200."""
    task = HealthCheckLambda()
    with mock.patch("sap.worker.lambdas.httpx.AsyncClient", return_value=http_client(200)):
        await task.heartbeat("https://example.com/heartbeat")

    with mock.patch("sap.worker.lambdas.httpx.AsyncClient", return_value=http_client(500)):
        with pytest.raises(AssertionError):
            await task.heartbeat("https://example.com/heartbeat")
