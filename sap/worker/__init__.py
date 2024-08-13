"""
FastAPI.

This package regroups all common helpers exclusively
for Celery and background workers in general.
"""

from .amqp import AMQPClient
from .crons import CronStat, CronTask, FetchStrategy, register_crontask
from .lambdas import LambdaResponse, LambdaTask, LambdaWorker, register_lambda
from .packet import SignalPacket
from .utils import register_tasks_with_celery_beat

__all__ = [
    "AMQPClient",
    "SignalPacket",
    "LambdaResponse",
    "LambdaTask",
    "LambdaWorker",
    "CronTask",
    "CronStat",
    "FetchStrategy",
    "register_lambda",
    "register_crontask",
    "register_tasks_with_celery_beat",
]
