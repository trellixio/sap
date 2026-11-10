"""
Celery.

This package regroups all common helpers to run lambdas and crons with Celery, on RabbitMQ.

It needs the `celery` extra: `pip install sapx[celery]`.
"""

try:
    import celery
except ImportError as exc:
    raise ImportError("sap.worker.celery needs the celery extra: pip install 'sapx[celery]'") from exc

from sap.worker.packet import EventPublisher, SignalPacket

from .crons import CronStat, CronTask, FetchStrategy, register_crontask
from .lambdas import LambdaResponse, LambdaTask, LambdaWorker, register_lambda
from .utils import register_tasks_with_celery_beat

__all__ = [
    "EventPublisher",
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
