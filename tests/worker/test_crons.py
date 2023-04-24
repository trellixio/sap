"""
Test Crons.

Test xlib.tasks utilities.
"""
from typing import ClassVar, Callable, Optional, Any

import celery.schedules
import pytest

from beanie.odm.queries.find import FindMany
from pyairtable.api.table import Table
from AppMain.settings import AppSettings
from sap.worker.crons import CronStorage, CronTask, FetchStrategy, CronStat, register_crontask
from sap.worker.crons_airtable import AirtableStorage

from .samples import DummyDoc

AIRTABLE_APP = "app9HzOEd8QnsCbJ4"


class TestAirtableStorage(AirtableStorage):
    PROJECT_NAME: ClassVar[str] = "sap"

    TABLE_TASKS: ClassVar[Table] = Table(AppSettings.AIRTABLE_TOKEN, AIRTABLE_APP, "Tasks")
    TABLE_RUNS: ClassVar[Table] = Table(AppSettings.AIRTABLE_TOKEN, AIRTABLE_APP, "Runs")
    TABLE_STATS: ClassVar[Table] = Table(AppSettings.AIRTABLE_TOKEN, AIRTABLE_APP, "Stats")

    @classmethod
    def get_env_params(cls) -> tuple[str, str]:
        """Return env name and env id on airtable"""
        return "TEST", "rec8deejyHcQzGVda"


class DummyCron(CronTask):
    """Dummy cron to test that crontask utilities are functioning."""

    storage_class: ClassVar[type[CronStorage]] = TestAirtableStorage

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


def get_filter_queryset_dummy() -> Callable[[FindMany[Any]], FindMany[Any]]:
    """Return initial queryset without filtering."""

    def filter_nothing(queryset: FindMany[Any]) -> FindMany[Any]:
        """Filter queryset."""
        return queryset

    return filter_nothing


@pytest.mark.parametrize("is_error", [False, True])
@pytest.mark.asyncio
async def test_cron_task(is_error: bool) -> None:
    """Create dummy cron task to ensure that CronTask class is functioning."""
    task = register_crontask(
        DummyCron,
        schedule=celery.schedules.crontab(hour="12", minute="00", day_of_week="mon"),
        kwargs={"strategy": FetchStrategy.NEW, "batch_size": 20, "error": is_error},
    )

    # with mock.patch.object(pyairtable.Table, "_request", return_value={"records": [{"id": "0"}]}):
    #     await task.register_to_airtable()

    if AppSettings.AIRTABLE_TOKEN and AppSettings.APP_ENV in ["DEV"]:
        # Testing that airtable sync is working as expected
        await task.run()

    elif is_error:
        # Testing that error are raised on dev env on failure
        with pytest.raises(ValueError):
            await task.run_test(filter_queryset=get_filter_queryset_dummy())

    else:
        await task.run_test(filter_queryset=get_filter_queryset_dummy())
