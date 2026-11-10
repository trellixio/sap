"""
Cron Tasks.

Background tasks that run a worker server.
These tasks can run even while the user is not online,
not making any active HTTP requests, or not using the application.

This module defines what a cron fetches and processes; `sap.worker.celery` and `sap.worker.taskiq` run it.
"""

import logging
import time
from dataclasses import dataclass
from enum import Enum, IntEnum
from typing import Any, Callable, Optional, TypedDict
from unittest import mock

import httpx

from fastapi import status as rest_status

from sap.loggers import logger
from sap.settings import SapSettings


class FetchStrategy(IntEnum):
    """Define if new or old data should be fetched."""

    NEW = 1
    OLD = 2


class CronResponseStatus(Enum):
    """Status of the crontask after it finish running."""

    SUCCESS = "Success"
    ABORTED = "Aborted"
    ERROR = "Error"


class CronResponse(TypedDict, total=False):
    """Define a standard cron task response."""

    error: dict[str, str]
    result: dict[str, int]
    status: str


@dataclass
class CronStat:
    """Metric that gives insight into data to be processed by a cron."""

    name: str
    value: int


class CronTask:
    """
    Define how cron task classes should be structured.

    Each run logs its status, its duration and the stats of the cron, such as the number of elements left to process.
    """

    time_limit: Optional[int] = 60 * 60 * 3  # default to 3 hours, automatically kill the task if exceed the limit
    kwargs: dict[str, Any] = {}
    logger: logging.Logger = logger

    def __init__(self, **kw_args: Any) -> None:
        """Initialize the cron task."""
        for k, v in kw_args.items():
            setattr(self, k, v)

    @classmethod
    def get_name(cls) -> str:
        """Get Name of the current Task."""
        return cls.__module__.split(".crons", maxsplit=1)[0] + "." + str(cls.__name__)

    def get_queryset(self, *, batch_size: Optional[int] = None, **kwargs: Any) -> Any:
        """Fetch the list of elements to process."""
        raise NotImplementedError

    async def get_stats(self) -> list[CronStat]:  # pylint: disable=no-self-use
        """Give stats about the number of elements left to process."""
        return []

    async def process(self, *, batch_size: int = 100, **kwargs: Any) -> Any:
        """Run the cron task and process elements."""
        raise NotImplementedError

    async def handle_process(self, *args: Any, **kwargs: Any) -> CronResponse:
        """Run the task, then log how the run went."""
        response: CronResponse
        time_start = time.monotonic()

        try:
            result = await self.process(**self.kwargs)
        except Exception as exc:  # pylint: disable=broad-except
            if not SapSettings.is_env_prod:
                raise
            self.logger.exception(exc)
            response = {
                "error": {"class": exc.__class__.__name__, "message": str(exc)},
                "status": CronResponseStatus.ERROR.value,
            }
        else:
            response = {"result": result, "status": CronResponseStatus.SUCCESS.value}

        stats = await self.get_stats()
        self.logger.info(
            "Cron finished: task=%s status=%s duration=%.1fs stats=%s",
            self.get_name(),
            response["status"],
            time.monotonic() - time_start,
            {stat.name: stat.value for stat in stats},
        )
        return response

    async def test_process(self, filter_queryset: Callable[[Any], Any]) -> CronResponse:
        """Call this method to launch the task in test cases.

        filter_queryset: This allows you to run an extra filtering on the data being processing.
        Useful if you want to limit the data processing to a specific sample.
        It receives the queryset of `get_queryset` and returns the filtered one, see `sap.beanie.tests`.
        """
        original_get_queryset = self.get_queryset

        def mock_get_queryset(batch_size: Optional[int] = None, **kwargs: Any) -> Any:
            """Replace the normal filter by a new test filter."""
            queryset = original_get_queryset(batch_size=batch_size, **kwargs)
            return filter_queryset(queryset)

        with mock.patch.object(self, "get_queryset", side_effect=mock_get_queryset):
            return await self.handle_process()


class HealthCheckCron(CronTask):
    """Send a heartbeat signal to better stack to notify that the cron has finished processing."""

    def get_queryset(self, *, batch_size: Optional[int] = None, **kwargs: Any) -> list[int]:
        """Fetch the list of elements to process."""
        return []

    async def process(self, *, batch_size: int = 100, **kwargs: Any) -> dict[str, int]:
        """Perform heartbeat signal."""
        async with httpx.AsyncClient() as client:
            response: httpx.Response = await client.head(kwargs["heartbeat_url"])
        assert response.status_code == rest_status.HTTP_200_OK
        return {"status": response.status_code}
