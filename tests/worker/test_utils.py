"""
Test Worker Utils.

Test celery beat registration and inspect commands.
"""

import celery
import celery.schedules
import pytest
from celery.events.state import State

from sap.worker.crons import HealthCheckCron
from sap.worker.utils import conf, match_amqp_topics, register_tasks_with_celery_beat


def test_register_tasks_with_celery_beat() -> None:
    """Register a cron and build its beat id from args and kwargs."""
    app = celery.Celery("coverage")
    task = HealthCheckCron(
        schedule=celery.schedules.crontab(minute="0"),
        kwargs={"heartbeat_url": "https://example.com"},
    )
    task.args = [1]
    options = {"queue": "cron"}

    beat = register_tasks_with_celery_beat(app, [task], options)

    uid = f"{task.get_name()}:1:https://example.com"
    assert beat[uid]["task"] == task.get_name()
    assert beat[uid]["args"] == [1]
    assert beat[uid]["kwargs"] == {"heartbeat_url": "https://example.com"}
    assert beat[uid]["options"] == options
    assert task.name in app.tasks


def test_conf_inspect_is_disabled() -> None:
    """Hide celery configuration from inspect commands."""
    assert conf(State(), with_defaults=False) == {"error": "Config inspection has been disabled."}


@pytest.mark.parametrize(
    "pattern, topic, expected",
    [
        ("stem.*.credit.created", "stem.card_1.credit.created", True),
        ("stem.*.credit.created", "stem.card_1.debit.created", False),
        ("stem.*.credit.created", "stem.card_1.credit", False),  # topic shorter than pattern
        ("stem.*.credit.created", "stem.card_1.credit.created.extra", False),  # topic longer than pattern
        ("stem.*", "stem", False),  # `*` matches exactly one word
        ("stem.#", "stem.card_1.credit.created", True),
        ("stem.#", "stem", True),  # `#` matches zero words
        ("stem.#.created", "stem.card_1.credit.created", True),
        ("stem.#.created", "stem.created", True),
        ("stem.#.created", "stem.card_1.credit.updated", False),
        ("#", "stem.card_1.credit.created", True),
    ],
)
def test_match_amqp_topics(pattern: str, topic: str, expected: bool) -> None:
    """Match a routing key against a binding pattern with the AMQP topic exchange rules."""
    assert match_amqp_topics(pattern, topic) is expected
