"""
Lambdas refers to async background tasks.

They run code in response to events which are typically messages sent to a queue.
This module defines what a lambda handles; `sap.worker.celery` and `sap.worker.taskiq` run it.
"""

from typing import Any, Optional, TypedDict

from .packet import SignalPacket


class LambdaResponse(TypedDict, total=False):
    """Normal LambdaTask result format."""

    result: bool
    error: str
    data: Any


class LambdaHandler:
    """
    A lambda handler runs on a specific event, usually after receiving a packet (message).

    It handles the packets sent to the topics that match the topic pattern of its packet.
    """

    packet: SignalPacket
    time_limit: Optional[int] = 60 * 1  # 1 minutes, None disables the limit

    # Retries are opt-in: list the exceptions worth retrying (e.g. transient network errors).
    # The task is retried up to `max_retries` times with exponential backoff; any other failure is final.
    autoretry_for: tuple[type[Exception], ...] = ()
    max_retries: Optional[int] = 3  # None retries forever, which only Celery supports

    @classmethod
    def get_name(cls) -> str:
        """Return a human-readable name for this lambda."""
        return cls.__module__.split(".lambdas", maxsplit=1)[0] + "." + cls.__name__

    async def handle_process(self, *args: Any, **kwargs: Any) -> LambdaResponse:
        """Perform pre-check such as authentication and run the task."""
        raise NotImplementedError

    async def test_process(self, *args: Any, **kwargs: Any) -> LambdaResponse:
        """Call this method to launch the task in test cases."""
        return await self.handle_process(*args, **kwargs)
