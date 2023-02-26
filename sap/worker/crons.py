"""
Tasks.

Background tasks that run a worker server.
These tasks can run even while the user is not online,
not making any active HTTP requests, or not using the application.
"""

import typing
from enum import IntEnum

import celery
import celery.schedules

from sap.loggers import logger
from sap.settings import SapSettings


class FetchStrategy(IntEnum):
    """Define if new or old data should be fetched."""

    NEW: int = 1
    OLD: int = 2


class CronResponse(typing.TypedDict, total=False):
    """Define a standard cron task response."""

    error: dict[str, str]
    result: dict[str, int]


class CronTask(celery.Task):
    """Define how cron task classes should be structured."""

    expires = 60 * 60  # automatically expires if not run within 1 hour
    time_limit = 60 * 60 * 3  # default to 3 hours, automatically kill the task if exceed the limit
    args: list[typing.Any]
    kwargs: dict[str, typing.Any]
    schedule: celery.schedules.crontab

    def __init__(self, **kwargs: typing.Any) -> None:
        """Initialize the cron task."""
        for k, v in kwargs.items():
            setattr(self, k, v)

    @classmethod
    def get_name(cls) -> str:
        """Get Name of the current Task."""
        return cls.__module__.split(".crons", maxsplit=1)[0] + "." + str(cls.__name__)

    def get_queryset(self, *, batch_size: typing.Optional[int] = None, **kwargs: typing.Any) -> typing.Any:
        """Fetch the list of elements to process."""
        raise NotImplementedError

    async def process(self, *, batch_size: int = 100, **kwargs: typing.Any) -> typing.Any:
        """Run the cron task and process elements."""
        raise NotImplementedError

    async def get_stats(self) -> dict[str, int]:
        """Give stats about the number of elements left to process."""
        raise NotImplementedError

    async def run(self) -> CronResponse:
        """Run the task and save meta info to Airtable."""
        response: CronResponse

        # B. Runs the task
        try:
            result = await self.process(**self.kwargs)
        except Exception as exc:  # pylint: disable=broad-except;
            if not SapSettings.is_env_prod:
                raise
            logger.exception(exc)
            response = {"error": {"class": exc.__class__.__name__, "message": str(exc)}}
        else:
            response = {"result": result}

        return response


def register_crontask(
    crontask_class: type[CronTask],
    schedule: celery.schedules.crontab,
    kwargs: typing.Optional[dict[str, typing.Any]] = None,
) -> CronTask:
    """Register a task on the worker servers."""
    return crontask_class(schedule=schedule, kwargs=kwargs or {})
