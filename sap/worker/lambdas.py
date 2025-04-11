"""
Lambdas refers to async background tasks.

They run code in response to events which are typically messages sent to a queue.
"""

# mypy: disable-error-code="import-untyped"

import asyncio
from typing import Any, ClassVar, TypedDict

import celery
import celery.bootsteps
import httpx
import kombu
from kombu.transport.base import StdChannel  # Channel

from fastapi import status as rest_status

from sap.loggers import logger

from .packet import SignalPacket
from .utils import match_amqp_topics


class LambdaResponse(TypedDict, total=False):
    """Normal LambdaTask result format."""

    result: bool
    error: str
    data: Any


class LambdaTask(celery.Task):  # type: ignore
    """
    A lambda task is a task that run on a specific event, usually after receiving a packet (message).

    The Lambda will be connected to an AMQP Queue and will listen
    to packets sent to that queue that matches the packet's topic pattern.
    """

    time_limit: int = 60 * 1  # 1 minutes
    packet: SignalPacket

    def __init__(self, **kwargs: Any) -> None:
        """Initialize lambda arguments."""
        self.name = self.get_name()

    def get_name(self) -> str:
        """Return a human-readable name for this lambda."""
        return self.__module__.split(".lambdas", maxsplit=1)[0] + "." + str(self.__name__)

    async def handle_process(self, *args: Any, **kwargs: Any) -> LambdaResponse:
        """Perform pre-check such as authentication and run the task."""
        raise NotImplementedError

    async def test_process(self, *args: Any, **kwargs: Any) -> LambdaResponse:
        """Call this method to launch the task in test cases."""
        return await self.handle_process(*args, **kwargs)

    def run(self, *args: Any, **kwargs: Any) -> Any:
        """Run the task."""
        logger.debug("Running task=%s args=%s kwargs=%s", self.get_name(), str(args), str(kwargs))
        return asyncio.run(self.handle_process(*args, **kwargs))


def register_lambda(lambda_task_class: type[LambdaTask]) -> LambdaTask:
    """Register the Lambda Task to make it discoverable by task runner (celery)."""
    return lambda_task_class()


class LambdaWorker(celery.bootsteps.ConsumerStep):
    """Celery worker that consumes packets (messages) sent to lambda queues."""

    packets: list[SignalPacket] = []
    name: ClassVar[str] = ""
    is_async: ClassVar[bool] = True

    def _get_queues(self, channel: StdChannel) -> list[kombu.Queue]:
        """Retrieve the list of AMQP queues associated to each packet signal."""
        queue_list: list[kombu.Queue] = []
        for packet in self.packets:
            # declare fallback queue
            params = packet.queue_get_params(task_name=self.name, is_fallback=True)
            params["exchange"] = kombu.Exchange(name=params["exchange"], type="topic", channel=channel, durable=True)
            queue_fallback = kombu.Queue(**params, channel=channel)
            queue_fallback.declare()  # type: ignore

            # declare primary queue
            params = packet.queue_get_params(task_name=self.name, is_fallback=False)
            params["exchange"] = kombu.Exchange(name=params["exchange"], type="topic", channel=channel, durable=True)
            queue_primary = kombu.Queue(**params, channel=channel)
            queue_primary.declare()  # type: ignore

            # only listen to primary queue
            queue_list.append(queue_primary)

        return queue_list

    def get_consumers(self, channel: StdChannel) -> list[kombu.Consumer]:
        """
        Create packet consumers.

        The consumers are the entrypoint of
        the application once celery starts receiving messages.
        """
        return [
            kombu.Consumer(
                channel,
                queues=self._get_queues(channel),
                callbacks=[self.consume],
                accept=["json"],
                prefetch_count=10,
            )
        ]

    def consume(self, body: dict[str, Any], message: kombu.Message) -> None:
        """
        Run the celery worker and consume messages.

        This is the entrypoint of the application once celery starts receiving messages.
        All packets received are sent to this function that will acknowledge reception and dispatch
        to registered Lambda tasks.
        """
        topic = message.delivery_info["routing_key"]
        headers = message.headers
        is_retry = headers and headers.get("x-death")
        if is_retry:
            logger.debug(
                "Consuming worker name=%s topic=%s body=%s headers=%s", self.name, topic, str(body), str(headers)
            )
        try:
            self._propagate_signal(body, message)
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception(exc)
            message.reject()
        else:
            message.ack()

    def _propagate_signal(self, body: dict[str, Any], message: kombu.Message) -> None:
        """
        Execute each lambda task that registered to that packet signal.

        Lambda tasks are all executed asynchronously and simultaneously through other background celery workers.
        Sometimes this can leads to duplicate key errors or integrity errors.
        """
        topic = message.delivery_info["routing_key"]
        for task in self.get_task_list():
            if match_amqp_topics(task.packet.topic, topic):
                # logger.debug(f"Matching task.packet.topic={task.packet.topic} topic={topic} task={task.get_name()}")
                identifier = body.get("identifier") or body.get("card_pid") or body.get("clover_id")
                if self.is_async:
                    task.apply_async(args=(identifier,), kwargs=body["kwargs"], time_limit=60)
                else:
                    task.apply(args=(identifier,), kwargs=body["kwargs"])

    def get_task_list(self) -> list[LambdaTask]:
        """Retrieve the list of lambda tasks to execute."""
        raise NotImplementedError


packet_heartbeat = SignalPacket("sap.heartbeat.created", providing_args=["heartbeat_url"])
packet_heartbeat.extra_exchange_arguments = {"x-delay": 5 * 60 * 1000}  # 5 minutes delay in-between checks


class HealthCheckLambda(LambdaTask):
    """Send a heartbeat signal to better stack to notify that the cron has finished processing."""

    packet: SignalPacket = packet_heartbeat
    # heartbeat_url: pydantic.HttpUrl = pydantic.HttpUrl()

    async def handle_process(self, *args: str, **kwargs: Any) -> LambdaResponse:
        """Perform heartbeat."""
        await self.heartbeat(heartbeat_url=args[0])
        return {"result": True}

    async def heartbeat(self, heartbeat_url: str) -> None:
        """Use heartbeat url to notify that everything is up and running as expected."""
        assert self.packet

        async with httpx.AsyncClient() as client:
            response: httpx.Response = await client.head(heartbeat_url)
        assert response.status_code == rest_status.HTTP_200_OK

        # await self.packet.send(heartbeat_url)
