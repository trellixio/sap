"""
Airtable Cron Tasks.

A version of cron tasks that store the results on Airtable.
Airtable makes it easy to visualized data.
"""

import json
from datetime import datetime
from typing import ClassVar, Optional

import pyairtable.api
import pyairtable.formulas as pyOps
import pyairtable.utils
from pyairtable.api.table import Table

from .crons import CronResponse, CronStat, CronStorage, FetchStrategy


class AirtableStorage(CronStorage):
    """store cron results in Airtable"""

    run_id: str = ""

    PROJECT_NAME: ClassVar[str]

    TABLE_TASKS: ClassVar[Table]
    TABLE_RUNS: ClassVar[Table]
    TABLE_STATS: ClassVar[Table]

    @classmethod
    def get_env_params(cls) -> tuple[str, str]:
        """Return env name and env id on airtable"""
        raise NotImplementedError

    async def record_task(self) -> None:
        """Register the task meta info on Airtable."""
        env_name, env_id = self.get_env_params()

        query = {"Env": env_name, "Name": self.task_name}
        task_info = self.TABLE_TASKS.first(formula=pyOps.match(query), fields=["Name", "Env"])  # type: ignore
        if task_info:
            self.task_id = task_info["id"]

        microapp = self.task_name.split(".")[1]
        fields = {"Project": self.PROJECT_NAME, "Name": self.task_name, "Microapp": microapp, "Env": [env_id]}
        if self.task_id:
            task_record = self.TABLE_TASKS.update(self.task_id, fields=fields)
        else:
            task_record = self.TABLE_TASKS.create(fields=fields)

        self.task_id = task_record["id"]

    async def record_run_start(self) -> None:
        """Record in the DB that the crontask has started."""
        kwargs = self.task.kwargs
        strategy: Optional[FetchStrategy] = kwargs.get("strategy")
        run = self.TABLE_RUNS.create(
            fields={
                "Task": [self.task_id],
                "Status": "Running",
                "Batch Size": kwargs.get("batch_size", 0),
                "Strategy": strategy.name if strategy else "NONE",
                "Arguments": json.dumps({k: v for k, v in kwargs.items() if k not in ["batch_size", "strategy"]}),
                "Started": pyairtable.utils.datetime_to_iso_str(datetime.utcnow()),
            }
        )
        self.run_id = run["id"]

    async def record_run_end(self, response: CronResponse) -> None:
        """Record in the DB that the crontask has ended."""
        self.TABLE_RUNS.update(
            self.run_id,
            fields={
                "Response": json.dumps(response),
                "Status": "Error" if "error" in response else "Success",
                "Ended": pyairtable.utils.datetime_to_iso_str(datetime.utcnow()),
            },
        )

    async def record_stats(self, stats: list[CronStat]) -> None:
        """Record un the DB stats about data to process by this cron."""
        for stat in stats:
            self.TABLE_STATS.create(fields={"Task": [self.task_id], "Key": stat.name, "Value": stat.value})
