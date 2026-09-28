"""
Test Celery Config.

Test celery config presets for lambda and cron workers.
"""

import pytest
from kombu.pidbox import Mailbox

from sap.worker.config import CeleryConfig, CronCeleryConfig, LambdaCeleryConfig


def test_reply_exchange_format() -> None:
    """Point pidbox replies at the shared reply exchange."""
    assert getattr(Mailbox, "reply_exchange_fmt") == "%s.reply.pidbox"


@pytest.mark.parametrize(
    "case",
    [
        (LambdaCeleryConfig, True, True, False, True, False),
        (LambdaCeleryConfig, False, True, False, True, False),
        (CronCeleryConfig, True, False, True, False, True),
        (CronCeleryConfig, False, False, True, False, True),
    ],
)
def test_celery_config(case: tuple[type[CeleryConfig], bool, bool, bool, bool, bool]) -> None:
    """Apply shared naming and the prod or dev worker limits."""
    config_cls, is_prod, acks_late, acks_on_failure, reject_on_lost, has_time_limit = case
    config = config_cls(proj_name="beans", is_prod=is_prod)
    app_name = f"celery.{config.proj_node}.beans"

    assert config.is_prod is is_prod
    assert config.task_default_exchange == app_name
    assert config.task_default_queue == app_name
    assert config.task_default_routing_key == app_name
    assert config.event_exchange == f"celeryev.{config.proj_node}.beans"
    assert config.event_queue_prefix == f"celeryev.{config.proj_node}.beans"
    assert config.broker_transport_options == {"client_properties": {"connection_name": app_name}}
    assert config.accept_content == ["application/json"]
    assert config.task_serializer == "json"
    assert config.result_serializer == "json"
    assert config.worker_hijack_root_logger is False
    assert config.worker_concurrency == (2 if is_prod else 1)
    assert config.broker_pool_limit == (4 if is_prod else 2)
    assert config.task_create_missing_queues is False
    assert config.task_acks_late is acks_late
    assert config.task_acks_on_failure_or_timeout is acks_on_failure
    assert config.task_reject_on_worker_lost is reject_on_lost
    if has_time_limit:
        assert getattr(config, "task_soft_time_limit") == 60 * 60 * 3
        assert getattr(config, "task_time_limit") == 60 * 60 * 3
    else:
        assert not hasattr(config, "task_soft_time_limit")
        assert not hasattr(config, "task_time_limit")
