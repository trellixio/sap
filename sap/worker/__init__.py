"""
FastAPI.

This package regroups all common helpers exclusively
for Celery and background workers in general.
"""

from .crons import CronTask, FetchStrategy, register_crontask
from .lambdas import LambdaTask, LambdaWorker, register_lambda
from .packet import AMQPClient, SignalPacket
from .utils import register_tasks_with_celery_beat

__all__ = [
    "AMQPClient",
    "SignalPacket",
    "LambdaTask",
    "LambdaWorker",
    "CronTask",
    "FetchStrategy",
    "register_lambda",
    "register_crontask",
    "register_tasks_with_celery_beat",
]
