"""
Test Dispatcher.

Test that events kick the lambda tasks whose topic matches, and are acknowledged only once kicked.
"""

import asyncio
import typing
from unittest import mock

import aio_pika
import aio_pika.abc
import pytest
import pytest_asyncio
from taskiq import AsyncBroker

from sap.worker.taskiq import EventDispatcher, LambdaHandler, LambdaResponse, SignalPacket, make_broker, register_lambda
from sap.worker.taskiq.dispatcher import load_dispatcher
from sap.worker.taskiq.lambdas import RegisteredLambda
from tests.worker.conftest import AMQP_URL

PACKET_DISPATCHED = SignalPacket("sap_tests.dispatch.#", providing_args=["identifier"])
DISPATCHER_NAME = "sap_tests.EventDispatcher"

events_received: list[tuple[str, str, str, dict[str, typing.Any]]] = []


class CreditHandler(LambdaHandler):
    """Record credits."""

    packet = SignalPacket("sap_tests.dispatch.*.credit.created", providing_args=["identifier"])

    async def handle_process(self, *args: str, **kwargs: typing.Any) -> LambdaResponse:
        """Record the event."""
        events_received.append(("credit", self.packet.topic, args[0], kwargs))
        return {"result": True}


class DebitHandler(CreditHandler):
    """Record debits."""

    packet = SignalPacket("sap_tests.dispatch.*.debit.created", providing_args=["identifier"])


class AnyEventHandler(CreditHandler):
    """Record every event of the namespace."""

    packet = SignalPacket("sap_tests.dispatch.#", providing_args=["identifier"])


@pytest_asyncio.fixture(name="broker")
async def fixture_broker() -> typing.AsyncIterator[AsyncBroker]:
    """Run lambdas in memory."""
    broker = make_broker(AMQP_URL, name="sap_tests.dispatch", in_memory=True)
    await broker.startup()
    events_received.clear()
    yield broker
    await broker.shutdown()


@pytest.fixture(name="dispatcher")
def fixture_dispatcher(broker: AsyncBroker) -> EventDispatcher:
    """Dispatch the events of the test namespace to the handlers."""
    handlers: list[RegisteredLambda] = [
        register_lambda(broker, handler_class) for handler_class in (CreditHandler, DebitHandler, AnyEventHandler)
    ]
    return EventDispatcher(
        AMQP_URL,
        name=DISPATCHER_NAME,
        packets=[PACKET_DISPATCHED],
        handlers=handlers,
        blocked_identifiers=["card_blocked"],
    )


def make_message(body: bytes) -> mock.Mock:
    """Build an incoming message whose acknowledgements are recorded."""
    message = mock.Mock(spec=aio_pika.abc.AbstractIncomingMessage)
    message.routing_key = "sap_tests.dispatch.card_1.credit.created"
    message.body = body
    message.message_id = "message_1"
    return message


async def test_dispatch_kicks_matching_handlers(dispatcher: EventDispatcher) -> None:
    """Kick every handler whose topic matches the event, with the identifier and kwargs of the event."""
    body = {"identifier": "card_1", "kwargs": {"amount": 10}}

    assert await dispatcher.dispatch("sap_tests.dispatch.card_1.credit.created", body) == 2

    assert sorted(events_received) == [
        ("credit", "sap_tests.dispatch.#", "card_1", {"amount": 10}),
        ("credit", "sap_tests.dispatch.*.credit.created", "card_1", {"amount": 10}),
    ]


@pytest.mark.parametrize("identifier_key", ["identifier", "card_pid", "clover_id"])
async def test_dispatch_reads_legacy_identifiers(dispatcher: EventDispatcher, identifier_key: str) -> None:
    """Read the identifier of older events too."""
    await dispatcher.dispatch("sap_tests.dispatch.card_1.user.created", {identifier_key: "card_1", "kwargs": {}})
    assert events_received == [("credit", "sap_tests.dispatch.#", "card_1", {})]


@pytest.mark.parametrize(
    "identifier, kicked_count", [("card_blocked", 0), ("card_blocked_2", 2), ("card_blocked10", 2)]
)
async def test_dispatch_drops_blocked_identifiers(
    dispatcher: EventDispatcher, identifier: str, kicked_count: int
) -> None:
    """Drop the events of blocked identifiers only, not of the identifiers that contain one."""
    body = {"identifier": identifier, "kwargs": {}}
    assert await dispatcher.dispatch(f"sap_tests.dispatch.{identifier}.credit.created", body) == kicked_count
    assert len(events_received) == kicked_count


async def test_dispatch_skips_handlers_kicked_before_a_failure(dispatcher: EventDispatcher) -> None:
    """Kick only the handlers left when an event comes back after a kick failed, so none runs twice."""
    topic, body = "sap_tests.dispatch.card_1.credit.created", {"identifier": "card_1", "kwargs": {}}
    any_event_handler = dispatcher.handlers[2]  # kicked after the credit handler

    with mock.patch.object(any_event_handler, "kiq", side_effect=ConnectionError("broker unreachable")):
        with pytest.raises(ConnectionError):
            await dispatcher.dispatch(topic, body, message_id="message_1")
    assert events_received == [("credit", "sap_tests.dispatch.*.credit.created", "card_1", {})]

    assert await dispatcher.dispatch(topic, body, message_id="message_1") == 1
    assert sorted(events_received) == [
        ("credit", "sap_tests.dispatch.#", "card_1", {}),
        ("credit", "sap_tests.dispatch.*.credit.created", "card_1", {}),
    ]

    # Once dispatched, the event is forgotten: a new delivery of it kicks every handler again.
    assert await dispatcher.dispatch(topic, body, message_id="message_1") == 2


@pytest.mark.parametrize(
    "raw_body, body", [(b'{"identifier": "card_1"}', {"identifier": "card_1"}), (b"[1, 2]", None), (b"{", None)]
)
def test_parse_body(raw_body: bytes, body: typing.Optional[dict[str, typing.Any]]) -> None:
    """Accept JSON objects only."""
    assert EventDispatcher.parse_body(raw_body) == body


async def test_on_message_acknowledges_dispatched_events(dispatcher: EventDispatcher) -> None:
    """Acknowledge an event once its tasks are kicked."""
    message = make_message(b'{"identifier": "card_1", "kwargs": {}}')
    await dispatcher.on_message(message)
    message.ack.assert_awaited_once_with()
    assert len(events_received) == 2


async def test_on_message_rejects_malformed_events(dispatcher: EventDispatcher) -> None:
    """Reject an event that is not a JSON object, without requeuing it."""
    message = make_message(b"not json")
    await dispatcher.on_message(message)
    message.reject.assert_awaited_once_with(requeue=False)
    assert not events_received


async def test_on_message_requeues_events_that_fail_to_dispatch(dispatcher: EventDispatcher) -> None:
    """Requeue an event whose tasks could not be kicked, so it is dispatched again."""
    message = make_message(b'{"identifier": "card_1", "kwargs": {}}')
    with mock.patch.object(EventDispatcher, "dispatch", side_effect=ConnectionError("broker unreachable")):
        await dispatcher.on_message(message)
    message.nack.assert_awaited_once_with(requeue=True)
    message.ack.assert_not_awaited()


@pytest_asyncio.fixture(name="queues_deleted")
async def fixture_queues_deleted(amqp_channel: aio_pika.abc.AbstractChannel) -> typing.AsyncIterator[None]:
    """Delete the queues of the test dispatcher after the test."""
    yield
    for is_fallback in (False, True):
        await amqp_channel.queue_delete(PACKET_DISPATCHED.queue_get_name(DISPATCHER_NAME, is_fallback=is_fallback))


@pytest.mark.usefixtures("packet_sending", "publisher", "queues_deleted")
async def test_dispatcher_runs_until_stopped(
    dispatcher: EventDispatcher, amqp_channel: aio_pika.abc.AbstractChannel
) -> None:
    """Dispatch the packets that waited in the queue before the dispatcher started, until it is stopped."""
    await PACKET_DISPATCHED.queue_declare(amqp_channel, task_name=DISPATCHER_NAME)
    await SignalPacket("sap_tests.dispatch.card_1.debit.created", ["identifier"]).send("card_1", amount=5)

    stop_event = asyncio.Event()
    running = asyncio.create_task(dispatcher.run(stop_event))
    await _wait_for_events(count=2)
    stop_event.set()
    await asyncio.wait_for(running, timeout=10)

    assert sorted(events_received) == [
        ("credit", "sap_tests.dispatch.#", "card_1", {"amount": 5}),
        ("credit", "sap_tests.dispatch.*.debit.created", "card_1", {"amount": 5}),
    ]
    queue = await amqp_channel.declare_queue(PACKET_DISPATCHED.queue_get_name(DISPATCHER_NAME), passive=True)
    assert queue.declaration_result.message_count == 0


async def _wait_for_events(count: int) -> None:
    """Wait up to 10 seconds until the handlers recorded `count` events."""
    for _ in range(200):
        if len(events_received) >= count:
            return
        await asyncio.sleep(0.05)


DISPATCHER_LOADED = EventDispatcher(AMQP_URL, name=DISPATCHER_NAME, packets=[PACKET_DISPATCHED], handlers=[])


def test_load_dispatcher() -> None:
    """Load the dispatcher to run from its import path, and refuse anything else."""
    assert load_dispatcher("tests.worker.taskiq.test_dispatcher:DISPATCHER_LOADED") is DISPATCHER_LOADED
    with pytest.raises(TypeError):
        load_dispatcher("tests.worker.taskiq.test_dispatcher:PACKET_DISPATCHED")
