"""
Airtable Cron Tasks.

A version of cron tasks that store the results on Airtable.
Airtable makes it easy to visualized data.
"""

import json
from typing import ClassVar, Optional

import pyairtable.api
import pyairtable.formulas as pyOps
import pyairtable.utils
from pyairtable.api.table import Table
from pyairtable.api.types import WritableFields

from sap.pydantic import datetime_utcnow

from .crons import CronResponse, CronStat, CronStorage, FetchStrategy


class AirtableStorage(CronStorage):
    """store cron results in Airtable."""

    run_id: str = ""

    PROJECT_NAME: ClassVar[str]

    def get_airtable(self, table_name: str = "") -> Table:
        """Return instance of the table to use give the table_name."""
        raise NotImplementedError

    @classmethod
    def get_env_params(cls) -> tuple[str, str]:
        """Return env name and env id on airtable."""
        raise NotImplementedError

    async def record_task(self) -> None:
        """Register the task meta info on Airtable."""
        env_name, env_id = self.get_env_params()

        query = {"Env": env_name, "Name": self.task_name}
        task_info = self.get_airtable("tasks").first(formula=pyOps.match(query), fields=["Name", "Env"])
        if task_info:
            self.task_id = task_info["id"]

        microapp = self.task_name.split(".")[1]
        fields: WritableFields = {
            "Project": self.PROJECT_NAME,
            "Name": self.task_name,
            "Microapp": microapp,
            "Env": [env_id],
        }
        if self.task_id:
            task_record = self.get_airtable("tasks").update(self.task_id, fields=fields)
        else:
            task_record = self.get_airtable("tasks").create(fields=fields)

        self.task_id = task_record["id"]

    async def record_run_start(self) -> None:
        """Record in the DB that the crontask has started."""
        assert self.task_id
        kwargs = self.task.kwargs
        strategy: Optional[FetchStrategy] = kwargs.get("strategy")
        run = self.get_airtable("runs").create(
            fields={
                "Task": [self.task_id],
                "Status": "Running",
                "Batch Size": kwargs.get("batch_size", 0),
                "Strategy": strategy.name if strategy else "NONE",
                "Arguments": json.dumps({k: v for k, v in kwargs.items() if k not in ["batch_size", "strategy"]}),
                "Started": pyairtable.utils.datetime_to_iso_str(datetime_utcnow()),
            }
        )
        self.run_id = run["id"]

    async def record_run_end(self, response: CronResponse) -> None:
        """Record in the DB that the crontask has ended."""
        self.get_airtable("runs").update(
            self.run_id,
            fields={
                "Response": json.dumps(response),
                "Status": "Error" if "error" in response else "Success",
                "Ended": pyairtable.utils.datetime_to_iso_str(datetime_utcnow()),
            },
        )

    async def record_stats(self, stats: list[CronStat]) -> None:
        """Record un the DB stats about data to process by this cron."""
        assert self.task_id
        table = self.get_airtable("stats")
        for stat in stats:
            table.create(fields={"Task": [self.task_id], "Key": stat.name, "Value": stat.value})
