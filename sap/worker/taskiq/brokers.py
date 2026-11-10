"""
Brokers.

A broker carries the tasks of one worker through RabbitMQ, from the services that kick them to the worker.
"""

from aio_pika import ExchangeType
from taskiq import AsyncBroker, InMemoryBroker, SmartRetryMiddleware
from taskiq_aio_pika import AioPikaBroker, Exchange, Queue


def make_broker(
    url: str, *, name: str, with_retries: bool = False, retry_delay: float = 5, in_memory: bool = False
) -> AsyncBroker:
    """
    Build the broker of the worker `name`, such as `trellis.lambdas`.

    Tasks go through the `taskiq.<name>` quorum queue.
    Messages that RabbitMQ gives up on (the consumer died too many times) land in `taskiq.<name>.dead_letter`.

    :with_retries: retry the tasks that opt in, after `retry_delay` seconds, then with an exponential backoff
        capped to a minute. The delayed tasks wait in the `taskiq.<name>.delay` queue.
    :in_memory: run tasks in the process that kicks them, as soon as they are kicked. Use it in test cases.
    """
    broker: AsyncBroker
    if in_memory:
        broker = InMemoryBroker(await_inplace=True)
    else:
        broker = AioPikaBroker(
            url,
            exchange=Exchange(name=f"taskiq.{name}", type=ExchangeType.DIRECT),
            task_queues=[Queue(name=f"taskiq.{name}")],
            dead_letter_queue=Queue(name=f"taskiq.{name}.dead_letter"),
            delay_queue=Queue(name=f"taskiq.{name}.delay") if with_retries else None,
        )

    if with_retries:
        broker.add_middlewares(
            SmartRetryMiddleware(
                default_retry_label=False,  # retries are opt-in, see `LambdaHandler.autoretry_for`
                default_delay=retry_delay,
                use_jitter=True,
                use_delay_exponent=True,
                max_delay_exponent=60,
            )
        )

    return broker
