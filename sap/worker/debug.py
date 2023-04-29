"""
Celery Tasks Debug. 

This module contains utilities tasks to debug your cron, lambda or rpc tasks. 
If your celery tasks are not running as expected, you can use this tasks that will register 
all running activities to help debug where the issue might be.
"""

from typing import Any
import os
import time
from datetime import datetime


from sap.loggers import logger

from .crons import CronTask, CronStat
from .lambdas import LambdaTask
from .packet import SignalPacket  # , RPCPacket

# from .rpc import RPCTask

packet_order = SignalPacket(topic="radix.*.*.order.created", providing_args=["identifier", "order_data"])


class DebugTask:
    name: str = ""

    def get_queryset(self, **kwargs: Any) -> str:
        """Simple queryset that return a datetime string for debugging"""
        return str(datetime.now())

    async def process(self, *args: Any, **kwargs: Any) -> dict[str, str]:
        time_now = self.get_queryset()

        # import traceback

        # traceback.print_stack()
        # raise Exception('Yo')

        logger.warn(
            f"Running Start self.name={self.name} proc.pid={os.getpid()} args={args} kwargs={kwargs} time_now={time_now}"
        )

        time.sleep(30)

        logger.warn(f"Running End self.name={self.name} proc.pid={os.getpid()} args={args} kwargs={kwargs} time_now={time_now}")
        # raise Exception("I am tired.!")

        return {"result": time_now}


class DebugCronTask(DebugTask, CronTask):
    """Useful for debugging cron tasks."""

    async def get_stats(self) -> list[CronStat]:
        """Get stats about debug cron."""
        return [CronStat(name="debug", value=1)]
    
    async def process(self, *args: Any, **kwargs: Any) -> dict[str, str]:
        self.name = self.get_name()
        return await super().process(*args, **kwargs)



class DebugLambdaTask1(DebugTask, LambdaTask):
    """Useful for debugging lambda tasks."""

    packet = packet_order

    async def handle_receive(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        """Simulate processing of a lambda task"""
        self.name = self.get_name()
        return await self.process(*args, **kwargs)


class DebugLambdaTask2(DebugTask, LambdaTask):
    """
    Useful for debugging lambda tasks.

    Create a second task just to ensure that there are 2
    different tasks registered with different names.
    """

    packet = packet_order

    async def handle_receive(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        """Simulate processing of a lambda task"""
        self.name = self.get_name()
        return await self.process(*args, **kwargs)


# class DebugRPCTask(DebugTask, RPCTask):
#     packet = RPCPacket(topic='radix.test.order.debug')

#     def exec(self, **kwargs):
#         return self.process(clover_id=0, **kwargs)
