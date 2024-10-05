"""
Utils.

Utilities methods to manage worker tasks.
"""

# mypy: disable-error-code="import-untyped"

import typing

import celery
import celery.schedules
from celery.events.state import State
from celery.utils.serialization import strtobool
from celery.worker.control import Panel

from .crons import CronTask

# @contextlib.contextmanager
# def context_timeout(seconds: int) -> typing.Iterator[None]:
#     """
#     Provide a timeout context, to automatically abort
#     background tasks that exceeds time limit.
#     """

#     def raise_timeout(signum: int, frame: typing.Optional[types.FrameType]) -> None:
#         raise TimeoutError

#     # Register a function to raise a TimeoutError on the signal.
#     signal.signal(signal.SIGALRM, raise_timeout)

#     # Schedule the signal to be sent after ``time``.
#     signal.alarm(seconds)

#     try:
#         yield
#     except TimeoutError:
#         raise
#     finally:
#         # Unregister the signal so it won't be triggered
#         # if the timeout is not reached.
#         signal.signal(signal.SIGALRM, signal.SIG_IGN)


def match_amqp_topics(topic_alpha: str, topic_beta: str) -> bool:
    """
    Allow comparison on topics pattern.

    This method makes it easy to know if topic_a is contained in topic_b.
    """
    parts_alpha = topic_alpha.split(".")
    parts_beta = topic_beta.split(".")
    if any(a != b and a != "*" and b != "*" for (a, b) in zip(parts_alpha, parts_beta)):
        return False
    return True


class CeleryBeatTaskParams(typing.TypedDict, total=True):
    """Params to schedule a celery beat task."""

    task: str
    schedule: celery.schedules.crontab
    args: list[typing.Any]
    kwargs: dict[str, typing.Any]
    options: dict[str, str]


def register_tasks_with_celery_beat(
    celery_app: celery.Celery, tasks: list[CronTask], options: dict[str, str]
) -> dict[str, CeleryBeatTaskParams]:
    """Retrieve all task params to set up celery beat."""
    beat_schedule: dict[str, CeleryBeatTaskParams] = {}

    for task in tasks:
        uid_args = "-".join([str(x) for x in task.args])
        uid_kwargs = "-".join([str(x) for x in task.kwargs.values()])
        uid = f"{task.get_name()}:{uid_args}:{uid_kwargs}"
        celery_app.register_task(task)
        beat_schedule[uid] = {
            "task": task.get_name(),
            "schedule": task.schedule,
            "args": task.args,
            "kwargs": task.kwargs,
            "options": options,
        }

    return beat_schedule


@Panel.register(  # type: ignore[misc]
    type="inspect",
    alias="dump_conf",
    signature="[include_defaults=False]",
    args=[("with_defaults", strtobool)],
)
def conf(state: State, with_defaults: bool = False, **kwargs: typing.Any) -> dict[str, str]:
    """
    Override the default `conf` inspect command to effectively disable it.

    This is to stop sensitive configuration information appearing in e.g. Flower.
    (Celery makes an attempt to remove sensitive information, but it is not foolproof.)
    """
    assert state is not None and with_defaults is not None and kwargs is not None  # silent pylint
    return {"error": "Config inspection has been disabled."}
