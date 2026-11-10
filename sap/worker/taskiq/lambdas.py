"""
Lambdas refers to async background tasks.

They run code in response to events which are typically messages sent to a queue.
The lambda logic lives in `sap.worker.lambdas`; this module registers it as a Taskiq task,
that the `EventDispatcher` kicks when an event matches the topic of its packet.
"""

from typing import Any, Coroutine, TypeAlias

from taskiq import AsyncBroker, AsyncTaskiqDecoratedTask, SmartRetryMiddleware
from taskiq.acks import AcknowledgeType

from sap.loggers import logger
from sap.worker.lambdas import LambdaHandler, LambdaResponse

RegisteredLambda: TypeAlias = AsyncTaskiqDecoratedTask[..., Coroutine[Any, Any, LambdaResponse]]


def register_lambda(broker: AsyncBroker, handler_class: type[LambdaHandler]) -> RegisteredLambda:
    """
    Register the lambda handler as a task of the broker.

    A new instance of the handler handles each event, so it can keep the state of the event on `self`.
    The task is acknowledged once it has run, so a worker that dies while running it hands it over to another one.
    """

    async def run_handler(identifier: str, **kwargs: Any) -> LambdaResponse:
        """Handle the event with a new instance of the handler."""
        logger.debug("Running lambda=%s identifier=%s kwargs=%s", handler_class.get_name(), identifier, kwargs)
        return await handler_class().handle_process(identifier, **kwargs)

    labels: dict[str, Any] = {"topic": handler_class.packet.topic, "ack_type": AcknowledgeType.WHEN_EXECUTED.value}
    if handler_class.time_limit is not None:
        labels["timeout"] = handler_class.time_limit
    if handler_class.autoretry_for:
        if not any(isinstance(middleware, SmartRetryMiddleware) for middleware in broker.middlewares):
            raise ValueError(f"{handler_class.get_name()} retries on error: build its broker with retries.")
        if handler_class.max_retries is None:
            raise ValueError(f"{handler_class.get_name()} retries on error: give it a `max_retries`.")
        labels |= {
            "retry_on_error": True,
            "types_of_exceptions": handler_class.autoretry_for,
            "max_retries": handler_class.max_retries + 1,  # the middleware counts the first run as well
        }

    return broker.register_task(run_handler, task_name=handler_class.get_name(), **labels)
