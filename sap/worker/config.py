# pylint: disable=too-many-instance-attributes

"""
CeleryConfig.

Celery config utility make it easier for app to load celery params
depending of use case. The different use cases are:
- LambdaCeleryConfig: Tasks that run on a remote server asynchronously, no need of waiting for result.
- RPCCeleryConfig: Tasks that run on a remote server synchronously, need to wait for a result.
- CronCeleryConfig: Periodic tasks that are scheduled.
"""
import typing

# do not remove, forcing update of format for better amqp exchanges structures
from kombu.pidbox import Mailbox

Mailbox.reply_exchange_fmt = "%s.reply.pidbox"  # type: ignore


class CeleryConfig:
    """Default config params for all celery applications."""

    proj_node: str
    is_prod: bool

    task_default_exchange: str
    task_default_queue: str
    task_default_routing_key: str

    event_exchange: str
    event_queue_prefix: str

    accept_content: list[str] = ["application/json"]
    task_serializer: str = "json"
    result_serializer: str = "json"

    broker_transport_options: dict[str, typing.Any]

    worker_hijack_root_logger: bool = False

    worker_concurrency: int
    broker_pool_limit: int

    task_create_missing_queues: bool
    task_acks_late: bool
    task_acks_on_failure_or_timeout: bool
    task_reject_on_worker_lost: bool

    def __init__(self, proj_name: str, is_prod: bool) -> None:
        """Initialize config."""
        self.is_prod = is_prod

        celery_app_name = f"celery.{self.proj_node}.{proj_name}"
        self.task_default_exchange = celery_app_name
        self.task_default_queue = celery_app_name
        self.task_default_routing_key = celery_app_name
        self.event_exchange = f"celeryev.{self.proj_node}.{proj_name}"
        self.event_queue_prefix = f"celeryev.{self.proj_node}.{proj_name}"

        self.broker_transport_options = {"client_properties": {"connection_name": celery_app_name}}


class LambdaCeleryConfig(CeleryConfig):
    """Default config params for lambda celery applications."""

    proj_node: str = "lambda"

    def __init__(self, proj_name: str, is_prod: bool) -> None:
        """Initialize config."""

        super().__init__(proj_name=proj_name, is_prod=is_prod)

        self.worker_concurrency = 2 if is_prod else 1
        self.broker_pool_limit = 4 if is_prod else 2

        self.task_create_missing_queues = False
        self.task_acks_late = True
        self.task_acks_on_failure_or_timeout = False
        self.task_reject_on_worker_lost = True


class CronCeleryConfig(CeleryConfig):
    """Default config params for cron celery applications."""

    proj_node: str = "cron"

    def __init__(self, proj_name: str, is_prod: bool) -> None:
        """Initialize config."""

        super().__init__(proj_name=proj_name, is_prod=is_prod)

        self.worker_concurrency = 2 if is_prod else 1
        self.broker_pool_limit = 4 if is_prod else 2

        self.task_create_missing_queues = False
        self.task_acks_late = False
        self.task_acks_on_failure_or_timeout = True
        self.task_reject_on_worker_lost = False

        # default to 3 hours, automatically send stop signal to the task if exceed the limit
        self.task_soft_time_limit = 60 * 60 * 3
        self.task_time_limit = 60 * 60 * 3
