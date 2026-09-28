"""
Test Debug Tasks.

Test debug cron and lambda helpers.
"""

from unittest import mock

import pytest

from sap.worker.crons import CronStat
from sap.worker.debug import DebugCronTask, DebugLambdaTask1, DebugLambdaTask2
from sap.worker.lambdas import LambdaTask


@pytest.mark.asyncio
@pytest.mark.parametrize("task_cls", [DebugLambdaTask1, DebugLambdaTask2])
async def test_debug_lambda_process(task_cls: type[LambdaTask]) -> None:
    """Run a debug lambda without waiting on the sleep."""
    task = task_cls()
    with mock.patch("sap.worker.debug.asyncio.sleep", new_callable=mock.AsyncMock) as sleep:
        result = await task.handle_process("order-1", order_data={"id": 1})

    sleep.assert_awaited_once_with(30)
    assert result["result"] is True
    assert result["data"]


@pytest.mark.asyncio
async def test_debug_cron_stats() -> None:
    """Return a single debug stat from the cron task."""
    stats = await DebugCronTask().get_stats()
    assert stats == [CronStat(name="debug", value=1)]
