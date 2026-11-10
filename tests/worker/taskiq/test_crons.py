"""
Test Crons.

Test that crons are scheduled with their kwargs, run with a new instance, and skip a run while the previous one goes on.
"""

import asyncio
import typing

import pytest
import pytest_asyncio
from taskiq import AsyncBroker
from taskiq.schedule_sources import LabelScheduleSource

from AppMain.settings import AppSettings
from sap.worker.taskiq import CronLock, CronStat, CronTask, make_broker, register_cron
from tests.worker.conftest import AMQP_URL


class CountingCron(CronTask):
    """Record the instance and the kwargs of every run."""

    runs: typing.ClassVar[list[tuple[CronTask, int]]] = []

    def get_queryset(self, *, batch_size: typing.Optional[int] = None, **kwargs: typing.Any) -> list[int]:
        """Process nothing."""
        return []

    async def process(self, *, batch_size: int = 100, **kwargs: typing.Any) -> dict[str, int]:
        """Record the run."""
        self.runs.append((self, batch_size))
        return {"processed": batch_size}

    async def get_stats(self) -> list[CronStat]:
        """Report no stats."""
        return []


class UnlimitedCron(CountingCron):
    """Run without a time limit."""

    time_limit = None


@pytest_asyncio.fixture(name="broker")
async def fixture_broker() -> typing.AsyncIterator[AsyncBroker]:
    """Run crons in memory."""
    broker = make_broker(AMQP_URL, name="sap_tests.crons", in_memory=True)
    await broker.startup()
    CountingCron.runs.clear()
    yield broker
    await broker.shutdown()


@pytest.fixture(name="cron_lock")
def fixture_cron_lock() -> typing.Iterator[None]:
    """Lock cron runs in the Redis of the test settings."""
    CronLock.redis_url = AppSettings.REDIS.get_dns()
    yield
    CronLock.redis_url = None


def test_register_cron_schedules(broker: AsyncBroker) -> None:
    """Schedule a cron once per registration, acknowledge it on receipt and limit its time."""
    task = register_cron(broker, CountingCron, "5 */12 * * *", kwargs={"batch_size": 20})
    assert register_cron(broker, CountingCron, "*/5 * * * *", kwargs={"batch_size": 100}) is task

    assert task.task_name == "tests.worker.taskiq.test_crons.CountingCron"
    assert task.labels == {
        "ack_type": "when_received",
        "timeout": 60 * 60 * 3,
        "schedule": [
            {"cron": "5 */12 * * *", "kwargs": {"batch_size": 20}, "schedule_id": f"{task.task_name}:20"},
            {"cron": "*/5 * * * *", "kwargs": {"batch_size": 100}, "schedule_id": f"{task.task_name}:100"},
        ],
    }
    assert "timeout" not in register_cron(broker, UnlimitedCron, "0 * * * *").labels


def test_register_cron_refuses_duplicate_schedules(broker: AsyncBroker) -> None:
    """Refuse to schedule the same cron twice with the same kwargs."""
    register_cron(broker, CountingCron, "5 */12 * * *", kwargs={"batch_size": 20})
    with pytest.raises(ValueError, match="already scheduled"):
        register_cron(broker, CountingCron, "0 0 * * *", kwargs={"batch_size": 20})


async def test_scheduler_reads_cron_schedules(broker: AsyncBroker) -> None:
    """Give the Taskiq scheduler every schedule, with the labels of the task."""
    register_cron(broker, CountingCron, "5 */12 * * *", kwargs={"batch_size": 20})
    register_cron(broker, CountingCron, "*/5 * * * *", kwargs={"batch_size": 100})

    source = LabelScheduleSource(broker)
    await source.startup()
    schedules = await source.get_schedules()

    assert sorted((schedule.cron or "", schedule.kwargs["batch_size"]) for schedule in schedules) == [
        ("*/5 * * * *", 100),
        ("5 */12 * * *", 20),
    ]
    assert all(schedule.labels["ack_type"] == "when_received" for schedule in schedules)


async def test_cron_runs_a_new_task_per_run(broker: AsyncBroker) -> None:
    """Run each schedule with a new instance of the cron task, given the kwargs of the schedule."""
    task = register_cron(broker, CountingCron, "5 */12 * * *", kwargs={"batch_size": 20})

    result_first = await (await task.kiq(batch_size=20)).wait_result(timeout=10)
    result_second = await (await task.kiq(batch_size=100)).wait_result(timeout=10)

    assert result_first.return_value == {"result": {"processed": 20}, "status": "Success"}
    assert result_second.return_value == {"result": {"processed": 100}, "status": "Success"}
    instances = [instance for instance, _ in CountingCron.runs]
    assert len(instances) == 2 and instances[0] is not instances[1]
    assert [batch_size for _, batch_size in CountingCron.runs] == [20, 100]


@pytest.mark.usefixtures("cron_lock")
async def test_cron_skips_a_run_while_the_previous_one_goes_on(broker: AsyncBroker) -> None:
    """Abort a run while the previous run of the same schedule holds the lock, and run once it is released."""
    task = register_cron(broker, CountingCron, "5 */12 * * *", kwargs={"batch_size": 20})

    async with CronLock.hold(f"{task.task_name}:20", ttl=60) as is_acquired:
        assert is_acquired
        result_locked = await (await task.kiq(batch_size=20)).wait_result(timeout=10)
    result_released = await (await task.kiq(batch_size=20)).wait_result(timeout=10)

    assert result_locked.return_value == {"status": "Aborted"}
    assert result_released.return_value["status"] == "Success"
    assert len(CountingCron.runs) == 1


@pytest.mark.usefixtures("cron_lock")
async def test_cron_lock_expires() -> None:
    """Release a lock that expired during the run without failing, so the next run can take it."""
    async with CronLock.hold("sap_tests.expiring", ttl=1) as is_acquired:
        assert is_acquired
        await asyncio.sleep(1.2)
    async with CronLock.hold("sap_tests.expiring", ttl=1) as is_acquired:
        assert is_acquired


async def test_cron_lock_is_off_without_redis() -> None:
    """Never skip a run when no Redis is configured."""
    async with CronLock.hold("sap_tests.unlocked", ttl=60) as is_acquired_first:
        async with CronLock.hold("sap_tests.unlocked", ttl=60) as is_acquired_second:
            assert is_acquired_first and is_acquired_second
