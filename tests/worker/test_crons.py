"""
Test Crons.

Test xlib.tasks utilities.
"""
from typing import Any, Callable, ClassVar, Optional

import celery.schedules
import pytest
from pyairtable.api.table import Table

from beanie.odm.queries.find import FindMany

from AppMain.settings import AppSettings
from sap.settings import SapSettings
from sap.worker.crons import CronStat, CronStorage, CronTask, FetchStrategy, register_crontask
from sap.worker.crons_airtable import AirtableStorage

from .samples import DummyDoc

AIRTABLE_APP = "app9HzOEd8QnsCbJ4"


class DummyAirtableStorage(AirtableStorage):
    PROJECT_NAME: ClassVar[str] = "sap"

    @classmethod
    def get_env_params(cls) -> tuple[str, str]:
        """Return env name and env id on airtable"""
        return "TEST", "rec8deejyHcQzGVda"

    def get_airtable(self, table_name: str = "") -> Table:
        """Return instance of the table to use give the table_name."""
        if table_name == "tasks":
            return Table(AppSettings.AIRTABLE_TOKEN, AIRTABLE_APP, "Tasks")
        if table_name == "runs":
            return Table(AppSettings.AIRTABLE_TOKEN, AIRTABLE_APP, "Runs")
        if table_name == "stats":
            return Table(AppSettings.AIRTABLE_TOKEN, AIRTABLE_APP, "Stats")
        raise NotImplementedError


class DummyCron(CronTask):
    """Dummy cron to test that crontask utilities are functioning."""

    storage_class: ClassVar[type[CronStorage]] = DummyAirtableStorage

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


def get_task(is_error: bool) -> CronTask:
    """Initialize a cron task for testing"""
    return register_crontask(
        DummyCron,
        schedule=celery.schedules.crontab(hour="12", minute="00", day_of_week="mon"),
        kwargs={"strategy": FetchStrategy.NEW, "batch_size": 20, "error": is_error},
    )


@pytest.mark.parametrize("is_error", [False, True])
def test_cron_task_run(is_error: bool) -> None:
    task = get_task(is_error=is_error)
    # Force the test to behave like if it were a prod environment
    SapSettings.is_env_prod = True

    if AppSettings.AIRTABLE_TOKEN:
        # Testing that airtable sync is working as expected
        task.run()

    SapSettings.is_env_prod = False


@pytest.mark.parametrize("is_error", [False, True])
@pytest.mark.asyncio
async def test_cron_task_test_process(is_error: bool) -> None:
    """Create dummy cron task to ensure that CronTask class is functioning."""
    task = get_task(is_error=is_error)

    if is_error:
        # Testing that error are raised on dev env on failure
        with pytest.raises(ValueError):
            await task.test_process(filter_queryset=get_filter_queryset_dummy())

    else:
        await task.test_process(filter_queryset=get_filter_queryset_dummy())
