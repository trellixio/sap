"""
Cron Tasks.

Background tasks that run a worker server.
These tasks can run even while the user is not online,
not making any active HTTP requests, or not using the application.
"""

import asyncio
import logging
from dataclasses import dataclass
from enum import Enum, IntEnum
from typing import Any, Callable, ClassVar, Optional, TypedDict
from unittest import mock

import celery
import celery.schedules
import httpx

from beanie.odm.queries.find import FindMany
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


class BaseCronTask(celery.Task):  # type: ignore
    """Define how cron task classes should be structured."""

    expires = 60 * 60  # automatically expires if not run within 1 hour
    time_limit = 60 * 60 * 3  # default to 3 hours, automatically kill the task if exceed the limit
    name: str
    args: list[Any] = []
    kwargs: dict[str, Any] = {}
    schedule: celery.schedules.crontab
    logger: logging.Logger = logger

    def __init__(self, **kw_args: Any) -> None:
        """Initialize the cron task."""
        self.name = self.get_name()
        for k, v in kw_args.items():
            setattr(self, k, v)

    @classmethod
    def get_name(cls) -> str:
        """Get Name of the current Task."""
        return cls.__module__.split(".crons", maxsplit=1)[0] + "." + str(cls.__name__)

    def get_queryset(self, *, batch_size: Optional[int] = None, **kwargs: Any) -> Any:
        """Fetch the list of elements to process."""
        raise NotImplementedError

    async def get_stats(self) -> list[CronStat]:
        """Give stats about the number of elements left to process."""
        raise NotImplementedError

    async def process(self, *, batch_size: int = 100, **kwargs: Any) -> Any:
        """Run the cron task and process elements."""
        raise NotImplementedError

    async def handle_process(self, *args: Any, **kwargs: Any) -> CronResponse:
        """Run the task and save meta info to Airtable."""
        response: CronResponse

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

        return response

    async def test_process(self, filter_queryset: Callable[[FindMany[Any]], FindMany[Any]]) -> CronResponse:
        """Call this method to launch the task in test cases.

        filter_queryset: This allows you to run an extra filtering on the data being processing.
        Useful if you want to limit the data processing to a specific sample.
        """
        original_get_queryset = self.get_queryset

        def mock_get_queryset(batch_size: Optional[int] = None, **kwargs: Any) -> FindMany[Any]:
            """Replace the normal filter by a new test filter."""
            queryset = original_get_queryset(batch_size=batch_size, **kwargs)
            return filter_queryset(queryset)

        with mock.patch.object(self, "get_queryset", side_effect=mock_get_queryset):
            return await self.handle_process()

    def run(self, *args: Any, **kwargs: Any) -> Any:
        """Run the task."""
        logger.debug("Running task=%s args=%s kwargs=%s", self.get_name(), str(args), str(kwargs))
        return asyncio.run(self.handle_process(*args, **kwargs))


class CronStorage:
    """
    Interface that store cron results in a database.

    Results can be used to collect statistics about cron runs.
    """

    task: BaseCronTask
    task_id: Optional[str] = None
    task_name: str

    def __init__(self, task: BaseCronTask):
        """Initialize the storage."""
        self.task = task
        self.task_name = task.get_name()

    async def record_task(self) -> None:
        """Register task to database and return database id of the task."""
        raise NotImplementedError

    async def record_run_start(self) -> None:
        """Record in the DB that the crontask has started."""
        raise NotImplementedError

    async def record_run_end(self, response: CronResponse) -> None:
        """Record in the DB that the crontask has ended."""
        raise NotImplementedError

    async def record_stats(self, stats: list[CronStat]) -> None:
        """Record un the DB stats about data to process by this cron."""
        raise NotImplementedError


class TestStorage(CronStorage):
    """Dummy storage used when running test cases."""

    async def record_task(self) -> None:
        """Register task to database and return database id of the task."""

    async def record_run_start(self) -> None:
        """Record in the DB that the crontask has started."""

    async def record_run_end(self, response: CronResponse) -> None:
        """Record in the DB that the crontask has ended."""

    async def record_stats(self, stats: list[CronStat]) -> None:
        """Record un the DB stats about data to process by this cron."""


# StorageT = TypeVar("StorageT", bound=CronStorage)


class CronTask(BaseCronTask):
    """Define a cron task and its storage."""

    storage_class: ClassVar[type[CronStorage]] = CronStorage
    storage: CronStorage

    def __init__(self, **kwargs: Any) -> None:
        """Initialize cron task and storage."""
        super().__init__(**kwargs)
        self.storage = self.storage_class(task=self)

    def get_queryset(self, *, batch_size: Optional[int] = None, **kwargs: Any) -> Any:
        """Fetch the list of elements to process."""
        raise NotImplementedError

    async def process(self, *, batch_size: int = 100, **kwargs: Any) -> Any:
        """Run the cron task and process elements."""
        raise NotImplementedError

    async def get_stats(self) -> list[CronStat]:
        """Give stats about the number of elements left to process."""
        raise NotImplementedError

    async def handle_process(self, *args: Any, **kwargs: Any) -> CronResponse:
        """Run the task and save meta info to Airtable."""

        # Record task
        await self.storage.record_task()

        # Record run start
        await self.storage.record_run_start()

        # Run the task
        response = await super().handle_process(*args, **kwargs)

        # Record run end
        await self.storage.record_run_end(response=response)

        # Compute stats
        stats = await self.get_stats()

        # Record stats
        await self.storage.record_stats(stats=stats)

        return response

    async def test_process(self, filter_queryset: Callable[[FindMany[Any]], FindMany[Any]]) -> CronResponse:
        """Call this method to launch the task in test cases."""
        self.storage = TestStorage(task=self)
        return await super().test_process(filter_queryset)


def register_crontask(
    crontask_class: type[CronTask],
    schedule: celery.schedules.crontab,
    kwargs: Optional[dict[str, Any]] = None,
) -> CronTask:
    """Register a task on the worker servers."""
    return crontask_class(schedule=schedule, kwargs=kwargs or {})


class HealthCheckCron(CronTask):
    """Send a heartbeat signal to better stack to notify that the cron has finished processing."""

    storage_class: ClassVar[type[CronStorage]] = TestStorage

    def get_queryset(self, *, batch_size: Optional[int] = None, **kwargs: Any) -> list[int]:
        """Fetch the list of elements to process."""
        return []

    async def process(self, *, batch_size: int = 100, **kwargs: Any) -> dict[str, int]:
        """Perform heartbeat signal."""
        async with httpx.AsyncClient() as client:
            response: httpx.Response = await client.head(kwargs["heartbeat_url"])
        assert response.status_code == rest_status.HTTP_200_OK
        return {"status": response.status_code}

    async def get_stats(self) -> list[CronStat]:
        """Give stats about the number of elements left to process."""
        return []
