"""
Topics.

Packets are routed by topic, the routing key of an AMQP topic exchange such as `stem.card_1.credit.created`.
"""


def match_amqp_topics(topic_alpha: str, topic_beta: str) -> bool:
    """
    Check that the routing key `topic_beta` matches the binding pattern `topic_alpha`.

    Follow the AMQP topic exchange rules: words are separated by dots,
    `*` matches exactly one word and `#` matches zero or more words.
    """
    return _match_topic_words(topic_alpha.split("."), topic_beta.split("."))


def _match_topic_words(pattern: list[str], words: list[str]) -> bool:
    """Match the words of a binding pattern against the words of a routing key."""
    if not pattern:
        return not words
    head, rest = pattern[0], pattern[1:]
    if head == "#":
        return any(_match_topic_words(rest, words[index:]) for index in range(len(words) + 1))
    return bool(words) and head in ("*", words[0]) and _match_topic_words(rest, words[1:])
