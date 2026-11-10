"""
Test Crons.

Test what crons process and report, whatever runs them.
"""

from typing import Any, Optional
from unittest import mock

import pytest

from beanie.odm.queries.find import FindMany

from sap.settings import SapSettings
from sap.tests.crons import get_filter_queryset_dummy
from sap.worker.crons import CronStat, CronTask, FetchStrategy, HealthCheckCron
from tests.samples import DummyDoc


class DummyCron(CronTask):
    """Dummy cron to test that crontask utilities are functioning."""

    def get_queryset(self, *, batch_size: Optional[int] = None, **kwargs: Any) -> FindMany[Any]:
        """Return dummy data for testing."""
        strategy: FetchStrategy = kwargs["strategy"]
        limit = batch_size or 100
        if strategy == FetchStrategy.NEW:
            return DummyDoc.find_many(DummyDoc.num >= 0, limit=limit)
        if strategy == FetchStrategy.OLD:
            return DummyDoc.find_many(DummyDoc.num <= 0, limit=limit)
        raise NotImplementedError

    async def process(self, *, batch_size: int = 100, **kwargs: Any) -> list[int]:
        """Process dummy data for testing."""
        strategy: FetchStrategy = kwargs["strategy"]
        qs: list[DummyDoc] = await self.get_queryset(batch_size=batch_size, strategy=strategy).to_list()
        result: list[int] = []
        for doc in qs:
            if doc.num > 0:
                result.append(doc.num)
        if kwargs.get("error"):
            raise ValueError("Invalid Data: dummy error")
        return result

    async def get_stats(self) -> list[CronStat]:
        """Get stats."""
        return [
            CronStat(name="data_new", value=await self.get_queryset(strategy=FetchStrategy.NEW).count()),
            CronStat(name="data_old", value=await self.get_queryset(strategy=FetchStrategy.OLD).count()),
        ]


DUMMY_KWARGS = {"strategy": FetchStrategy.NEW, "batch_size": 20}


async def test_cron_task_test_process() -> None:
    """Run the cron on the data sample of the test case."""
    response = await DummyCron(kwargs=DUMMY_KWARGS).test_process(filter_queryset=get_filter_queryset_dummy())
    assert response == {"result": list(range(1, 10)), "status": "Success"}


async def test_cron_task_raises_errors_outside_prod() -> None:
    """Raise the errors of a run outside production, so tests and developers see them."""
    with pytest.raises(ValueError):
        await DummyCron(kwargs=DUMMY_KWARGS | {"error": True}).handle_process()


async def test_cron_task_reports_errors_in_prod() -> None:
    """Report the error of a run in its response in production, so the worker carries on."""
    with mock.patch.object(SapSettings, "is_env_prod", True):
        response = await DummyCron(kwargs=DUMMY_KWARGS | {"error": True}).handle_process()
    assert response == {"error": {"class": "ValueError", "message": "Invalid Data: dummy error"}, "status": "Error"}


async def test_cron_task_logs_each_run() -> None:
    """Log the status and the stats of every run."""
    task = DummyCron(kwargs=DUMMY_KWARGS)
    with mock.patch.object(task, "logger") as logger:
        await task.handle_process()

    message, name, status, _, stats = logger.info.call_args.args
    assert message.startswith("Cron finished:")
    assert (name, status) == ("tests.worker.test_crons.DummyCron", "Success")
    assert stats == {"data_new": 10, "data_old": 11}


async def test_health_check_cron() -> None:
    """Head the heartbeat URL and report an empty queryset."""
    task = HealthCheckCron()
    assert not task.get_queryset()
    assert not await task.get_stats()  # crons report no stats unless they define some

    entered = mock.AsyncMock()
    entered.head.return_value = mock.Mock(status_code=200)
    client = mock.MagicMock()
    client.__aenter__ = mock.AsyncMock(return_value=entered)
    client.__aexit__ = mock.AsyncMock(return_value=None)
    with mock.patch("sap.worker.crons.httpx.AsyncClient", return_value=client):
        assert await task.process(heartbeat_url="https://example.com/heartbeat") == {"status": 200}
