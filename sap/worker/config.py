import typing

# do not remove, forcing update of format for better amqp exchanges structures
from kombu.pidbox import Mailbox

Mailbox.reply_exchange_fmt = "%s.reply.pidbox"


class LambdaConfig:
    """Default config params for celery application."""

    proj_node: str = "lambda"

    task_default_exchange: str
    task_default_queue: str
    task_default_routing_key: str

    event_exchange: str
    event_queue_prefix: str

    worker_concurrency: int
    broker_pool_limit: int

    task_create_missing_queues: bool
    task_acks_late: bool
    task_acks_on_failure_or_timeout: bool
    task_reject_on_worker_lost: bool
    worker_hijack_root_logger: bool

    accept_content: list[str] = ["application/json"]
    task_serializer: str = "json"
    result_serializer: str = "json"

    broker_transport_options: dict[str, typing.Any]

    def __init__(self, proj_name: str, is_prod: bool) -> None:
        celery_app_name = f"celery.{self.proj_node}.{proj_name}"
        self.task_default_exchange = celery_app_name
        self.task_default_queue = celery_app_name
        self.task_default_routing_key = celery_app_name
        self.event_exchange = f"celeryev.{self.proj_node}.{proj_name}"
        self.event_queue_prefix = f"celeryev.{self.proj_node}.{proj_name}"

        self.worker_concurrency = 2 if is_prod else 1
        self.broker_pool_limit = 4 if is_prod else 2

        self.task_create_missing_queues = False
        self.task_acks_late = True
        self.task_acks_on_failure_or_timeout = False
        self.task_reject_on_worker_lost = True
        self.worker_hijack_root_logger = False

        self.broker_transport_options = {"client_properties": {"connection_name": celery_app_name}}
