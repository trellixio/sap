"""
Test Crons.

Test that crons run as Celery tasks.
"""

import typing
from unittest import mock

import celery
import celery.schedules
import pytest

from sap.beanie.client import BeanieClient
from sap.settings import SapSettings
from sap.worker.celery.crons import CronResponse, CronTask, HealthCheckCron, register_crontask
from tests.worker.test_crons import DUMMY_KWARGS, DummyCron


class DummyCeleryCron(DummyCron, CronTask):
    """Dummy cron run by Celery, which opens MongoDB in the event loop of each run, as apps do."""

    async def handle_process(self, *args: typing.Any, **kwargs: typing.Any) -> CronResponse:
        """Reopen MongoDB in the event loop of the run, then run the cron."""
        await BeanieClient.reopen_for_current_loop()
        return await super().handle_process(*args, **kwargs)


def test_register_crontask() -> None:
    """Register the cron as a Celery task with its schedule and kwargs."""
    schedule = celery.schedules.crontab(hour="12", minute="00", day_of_week="mon")
    task = register_crontask(DummyCeleryCron, schedule=schedule, kwargs=DUMMY_KWARGS)

    assert isinstance(task, celery.Task)
    assert task.name == "tests.worker.celery.test_crons.DummyCeleryCron"
    assert (task.schedule, task.kwargs) == (schedule, DUMMY_KWARGS)
    assert HealthCheckCron().name == "sap.worker.celery.HealthCheckCron"


@pytest.mark.parametrize("is_error, status", [(False, "Success"), (True, "Error")])
def test_cron_task_run(is_error: bool, status: str) -> None:
    """Run a registered cron in its own event loop, as the Celery worker does in production."""
    schedule = celery.schedules.crontab(hour="12", minute="00", day_of_week="mon")
    task = register_crontask(DummyCeleryCron, schedule=schedule, kwargs=DUMMY_KWARGS | {"error": is_error})

    with mock.patch.object(SapSettings, "is_env_prod", True):
        assert task.run()["status"] == status
