"""
Cron Tasks.

Background tasks that run a worker server.
These tasks can run even while the user is not online,
not making any active HTTP requests, or not using the application.

The cron logic lives in `sap.worker.crons`; this module runs it as Celery tasks scheduled by Celery beat.
"""

import asyncio
from typing import Any, Optional

import celery
import celery.schedules

from sap.loggers import logger
from sap.worker import crons as base_crons
from sap.worker.crons import CronResponse, CronResponseStatus, CronStat, FetchStrategy

__all__ = [
    "CronTask",
    "HealthCheckCron",
    "register_crontask",
    "CronResponse",
    "CronResponseStatus",
    "CronStat",
    "FetchStrategy",
]


class CronTask(base_crons.CronTask, celery.Task):  # type: ignore  # pylint: disable=abstract-method
    """Define how cron task classes should be structured."""

    expires = 60 * 60  # automatically expires if not run within 1 hour
    name: str
    args: list[Any] = []
    schedule: celery.schedules.crontab

    def __init__(self, **kw_args: Any) -> None:
        """Initialize the cron task."""
        self.name = self.get_name()
        super().__init__(**kw_args)

    def run(self, *args: Any, **kwargs: Any) -> Any:
        """
        Run the task in an event loop of its own, as Celery tasks are sync.

        Clients bound to an event loop, such as a MongoDB client, must be opened by the task itself.
        """
        logger.debug("Running task=%s args=%s kwargs=%s", self.get_name(), str(args), str(kwargs))
        return asyncio.run(self.handle_process(*args, **kwargs))


def register_crontask(
    crontask_class: type[CronTask],
    schedule: celery.schedules.crontab,
    kwargs: Optional[dict[str, Any]] = None,
) -> CronTask:
    """Register a task on the worker servers."""
    return crontask_class(schedule=schedule, kwargs=kwargs or {})


class HealthCheckCron(base_crons.HealthCheckCron, CronTask):
    """Send a heartbeat signal to better stack to notify that the cron has finished processing."""
