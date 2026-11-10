"""
Test Lambdas.

Test that lambda handlers run as Taskiq tasks: one instance per event, opt-in retries and a time limit.
"""

import asyncio
import typing

import pytest
import pytest_asyncio
from taskiq import AsyncBroker

from sap.worker.taskiq import LambdaHandler, LambdaResponse, SignalPacket, make_broker, register_lambda
from tests.worker.conftest import AMQP_URL


class RecordingHandler(LambdaHandler):
    """Record the instance and the arguments of every event handled."""

    packet = SignalPacket("sap_tests.taskiq.*.user.created", providing_args=["identifier", "timestamp"])
    calls: typing.ClassVar[list[tuple[LambdaHandler, str, dict[str, typing.Any]]]] = []

    async def handle_process(self, *args: str, **kwargs: typing.Any) -> LambdaResponse:
        """Record the call."""
        self.calls.append((self, args[0], kwargs))
        return {"result": True}


class FailingHandler(LambdaHandler):
    """Always fail with a transient error."""

    packet = SignalPacket("sap_tests.taskiq.*.user.failed", providing_args=["identifier"])
    attempts: typing.ClassVar[list[str]] = []
    error_class: typing.ClassVar[type[Exception]] = ConnectionError

    async def handle_process(self, *args: str, **kwargs: typing.Any) -> LambdaResponse:
        """Record the attempt and fail."""
        self.attempts.append(args[0])
        raise self.error_class("service unreachable")


class FlakyHandler(FailingHandler):
    """Opt in to retries for transient errors."""

    autoretry_for = (ConnectionError,)
    max_retries = 2


class BrokenHandler(FlakyHandler):
    """Fail with an error that is not worth retrying."""

    error_class = ValueError


class SlowHandler(LambdaHandler):
    """Take longer than its time limit."""

    packet = SignalPacket("sap_tests.taskiq.*.user.slow", providing_args=["identifier"])
    time_limit = 1

    async def handle_process(self, *args: str, **kwargs: typing.Any) -> LambdaResponse:
        """Sleep past the time limit."""
        await asyncio.sleep(5)
        return {"result": True}


@pytest_asyncio.fixture(name="broker")
async def fixture_broker() -> typing.AsyncIterator[AsyncBroker]:
    """Run lambdas in memory, with retries."""
    broker = make_broker(AMQP_URL, name="sap_tests.lambdas", with_retries=True, in_memory=True)
    await broker.startup()
    yield broker
    await broker.shutdown()


def test_lambda_handler_name() -> None:
    """Name the handler after its module, without the `lambdas` module."""
    assert RecordingHandler.get_name() == "tests.worker.taskiq.test_lambdas.RecordingHandler"


async def test_lambda_handler_test_process() -> None:
    """Run the handler directly in test cases."""
    assert await RecordingHandler().test_process("card_1", timestamp=1) == {"result": True}


def test_register_lambda_labels() -> None:
    """Acknowledge lambdas once run, limit their time and leave retries off unless they opt in."""
    broker = make_broker(AMQP_URL, name="sap_tests.lambdas", with_retries=True, in_memory=True)

    task = register_lambda(broker, RecordingHandler)
    assert task.task_name == RecordingHandler.get_name()
    assert task.labels == {"topic": "sap_tests.taskiq.*.user.created", "ack_type": "when_executed", "timeout": 60}

    task = register_lambda(broker, FlakyHandler)
    assert task.labels["retry_on_error"] is True
    assert task.labels["types_of_exceptions"] == (ConnectionError,)
    assert task.labels["max_retries"] == 3  # the first run and 2 retries


class EndlessHandler(FailingHandler):
    """Retry forever, which Taskiq does not support."""

    autoretry_for = (ConnectionError,)
    max_retries = None


@pytest.mark.parametrize(
    "handler_class, with_retries, error",
    [(FlakyHandler, False, "build its broker with retries"), (EndlessHandler, True, "give it a `max_retries`")],
)
def test_register_lambda_refuses_retries_it_cannot_run(
    handler_class: type[LambdaHandler], with_retries: bool, error: str
) -> None:
    """Refuse a handler that retries on a broker that cannot retry, or that retries forever."""
    broker = make_broker(AMQP_URL, name="sap_tests.lambdas", with_retries=with_retries, in_memory=True)
    with pytest.raises(ValueError, match=error):
        register_lambda(broker, handler_class)


async def test_lambda_runs_a_new_handler_per_event(broker: AsyncBroker) -> None:
    """Handle each event with a new instance, so state on `self` never leaks to the next event."""
    task = register_lambda(broker, RecordingHandler)
    RecordingHandler.calls.clear()

    await task.kiq("card_1", timestamp=1)
    await task.kiq("card_2", timestamp=2)

    instances = [instance for instance, _, _ in RecordingHandler.calls]
    assert len(instances) == 2 and instances[0] is not instances[1]
    assert [call[1:] for call in RecordingHandler.calls] == [("card_1", {"timestamp": 1}), ("card_2", {"timestamp": 2})]


@pytest.mark.parametrize(
    "handler_class, attempts",
    [
        (FailingHandler, 1),  # retries are opt-in
        (FlakyHandler, 3),  # the first run and 2 retries
        (BrokenHandler, 1),  # only the listed exceptions are retried
    ],
)
async def test_lambda_retries_are_opt_in_and_bounded(
    broker: AsyncBroker, handler_class: type[FailingHandler], attempts: int
) -> None:
    """Retry only the handlers that opt in, for the errors they list, up to `max_retries` times."""
    task = register_lambda(broker, handler_class)
    FailingHandler.attempts.clear()

    await task.kiq("card_12345")

    assert FailingHandler.attempts == ["card_12345"] * attempts


async def test_lambda_time_limit(broker: AsyncBroker) -> None:
    """Stop a handler that runs past its time limit."""
    task = register_lambda(broker, SlowHandler)

    result = await (await task.kiq("card_1")).wait_result(timeout=10)

    assert result.is_err
    assert isinstance(result.error, TimeoutError)
