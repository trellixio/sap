"""
Celery Tasks Debug.

This module contains utilities tasks to debug your cron, lambda or rpc tasks.
If your celery tasks are not running as expected, you can use this tasks that will register
all running activities to help debug where the issue might be.
"""

import asyncio
import os
from datetime import datetime
from typing import Any

from sap.loggers import logger

from .crons import CronStat, CronTask
from .lambdas import LambdaResponse, LambdaTask
from .packet import SignalPacket  # , RPCPacket

# from .rpc import RPCTask

packet_order = SignalPacket(topic="radix.*.*.order.created", providing_args=["identifier", "order_data"])


class DebugTask:
    """Base for DebugTask."""

    name: str

    def get_queryset(self, **kwargs: Any) -> str:
        """Return a datetime string for debugging as Queryset."""
        assert self.name
        return str(datetime.utcnow())

    async def process(self, *args: Any, **kwargs: Any) -> LambdaResponse:
        """Mock a task process for debugging."""
        time_now = self.get_queryset()

        # import traceback

        # traceback.print_stack()
        # raise Exception('Yo')

        log_args = [self.name, os.getpid(), str(args), str(kwargs), str(time_now)]

        logger.warning("Running Start self.name=%s proc.pid=%d args=%s kwargs=%s time_now=%s", *log_args)

        await asyncio.sleep(30)

        logger.warning("Running End self.name=%s proc.pid=%d args=%s kwargs=%s time_now=%s", *log_args)
        # raise Exception("I am tired.!")

        return {"result": True, "data": time_now}


class DebugCronTask(DebugTask, CronTask):
    """Useful for debugging cron tasks."""

    async def get_stats(self) -> list[CronStat]:
        """Get stats about debug cron."""
        return [CronStat(name="debug", value=1)]


class DebugLambdaTask1(DebugTask, LambdaTask):
    """Useful for debugging lambda tasks."""

    packet = packet_order

    async def handle_process(self, *args: Any, **kwargs: Any) -> LambdaResponse:
        """Simulate processing of a lambda task."""
        return await self.process(*args, **kwargs)


class DebugLambdaTask2(DebugTask, LambdaTask):
    """
    Useful for debugging lambda tasks.

    Create a second task just to ensure that there are 2
    different tasks registered with different names.
    """

    packet = packet_order

    async def handle_process(self, *args: Any, **kwargs: Any) -> LambdaResponse:
        """Simulate processing of a lambda task."""
        return await self.process(*args, **kwargs)


# class DebugRPCTask(DebugTask, RPCTask):
#     packet = RPCPacket(topic='radix.test.order.debug')

#     def exec(self, **kwargs):
#         return self.process(clover_id=0, **kwargs)
