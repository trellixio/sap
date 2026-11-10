"""
Taskiq.

This package regroups all common helpers to run lambdas and crons with Taskiq, on RabbitMQ:
- `make_broker` builds the broker of a worker;
- `register_lambda` and `EventDispatcher` run lambda handlers when other services publish events;
  the dispatcher runs in its own process: `python -m sap.worker.taskiq <module>:<dispatcher>`;
- `register_cron` schedules cron tasks;
- `SignalPacket` sends packets, see `sap.worker.packet`.

It needs the `taskiq` extra: `pip install sapx[taskiq]`.
"""

from sap.worker.crons import CronResponse, CronStat, CronTask, FetchStrategy, HealthCheckCron
from sap.worker.lambdas import LambdaHandler, LambdaResponse
from sap.worker.packet import EventPublisher, SignalPacket

from .brokers import make_broker
from .crons import CronLock, register_cron
from .dispatcher import EventDispatcher
from .lambdas import register_lambda

__all__ = [
    "make_broker",
    "EventDispatcher",
    "EventPublisher",
    "SignalPacket",
    "LambdaHandler",
    "LambdaResponse",
    "register_lambda",
    "CronLock",
    "CronResponse",
    "CronStat",
    "CronTask",
    "FetchStrategy",
    "HealthCheckCron",
    "register_cron",
]
