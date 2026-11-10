"""
Cron Tasks.

Background tasks that the Taskiq scheduler kicks on a crontab schedule.
The cron logic lives in `sap.worker.crons`; this module registers it on a broker and schedules it.
"""

import contextlib
from typing import Any, AsyncIterator, ClassVar, Coroutine, Optional, TypeAlias

from redis.asyncio import Redis
from redis.exceptions import LockError
from taskiq import AsyncBroker, AsyncTaskiqDecoratedTask
from taskiq.acks import AcknowledgeType

from sap.loggers import logger
from sap.worker.crons import CronResponse, CronResponseStatus, CronTask

RegisteredCron: TypeAlias = AsyncTaskiqDecoratedTask[..., Coroutine[Any, Any, CronResponse]]


class CronLock:
    """
    Skip a cron run while the previous run of the same schedule is still going.

    Point `CronLock.redis_url` to Redis once at startup to turn the lock on; without it, runs are not locked.
    """

    redis_url: ClassVar[Optional[str]] = None

    @classmethod
    @contextlib.asynccontextmanager
    async def hold(cls, key: str, ttl: int) -> AsyncIterator[bool]:
        """Hold the lock for at most `ttl` seconds, and tell whether it was acquired."""
        if cls.redis_url is None:
            yield True
            return

        async with Redis.from_url(cls.redis_url) as client:
            lock = client.lock(f"sap:cron:{key}", timeout=ttl, blocking=False)
            if not await lock.acquire():
                yield False
                return
            try:
                yield True
            finally:
                with contextlib.suppress(LockError):  # the lock expired before the run ended
                    await lock.release()


def get_schedule_id(task_name: str, kwargs: dict[str, Any]) -> str:
    """Identify the schedule of a cron by its name and kwargs."""
    return ":".join([task_name, *(str(value) for value in kwargs.values())])


def register_cron(
    broker: AsyncBroker,
    crontask_class: type[CronTask],
    cron: str,
    kwargs: Optional[dict[str, Any]] = None,
) -> RegisteredCron:
    """
    Register the cron task on the broker and schedule it.

    :cron: a crontab expression, evaluated in UTC, such as `5 */12 * * *`.
    :kwargs: passed to `process`. They travel through the broker, so they must serialize to JSON.

    Register a cron class several times with other kwargs to schedule it several times.
    The task is acknowledged as soon as the worker receives it: a long cron does not hit the consumer timeout
    of RabbitMQ, and a run interrupted by a restart waits for its next schedule.
    """
    task_name = crontask_class.get_name()
    schedule = {"cron": cron, "kwargs": kwargs or {}, "schedule_id": get_schedule_id(task_name, kwargs or {})}

    task = broker.local_task_registry.get(task_name)
    if task is None:
        task = _register_crontask(broker, crontask_class)
    elif any(other["schedule_id"] == schedule["schedule_id"] for other in task.labels["schedule"]):
        raise ValueError(f"{schedule['schedule_id']} is already scheduled.")

    task.labels["schedule"].append(schedule)
    return task


def _register_crontask(broker: AsyncBroker, crontask_class: type[CronTask]) -> RegisteredCron:
    """Register the task that runs the cron, without any schedule yet."""
    task_name = crontask_class.get_name()
    time_limit = crontask_class.time_limit

    async def run_crontask(**kwargs: Any) -> CronResponse:
        """Run the cron with a new instance of the cron task, unless the previous run is still going."""
        schedule_id = get_schedule_id(task_name, kwargs)
        async with CronLock.hold(schedule_id, ttl=(time_limit or 60 * 60 * 24) + 60) as is_acquired:
            if not is_acquired:
                logger.warning("Skipping cron=%s: the previous run is still going", schedule_id)
                return {"status": CronResponseStatus.ABORTED.value}
            logger.debug("Running cron=%s", schedule_id)
            return await crontask_class(kwargs=kwargs).handle_process()

    labels: dict[str, Any] = {"schedule": [], "ack_type": AcknowledgeType.WHEN_RECEIVED.value}
    if time_limit is not None:
        labels["timeout"] = time_limit

    return broker.register_task(run_crontask, task_name=task_name, **labels)
