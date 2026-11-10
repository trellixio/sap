"""
Test Topics.

Test that routing keys match binding patterns as on an AMQP topic exchange.
"""

import pytest

from sap.worker.topics import match_amqp_topics


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
