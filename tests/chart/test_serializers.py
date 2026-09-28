"""
Test Chart Serializers.

Test statistic card serialization.
"""

import typing

import pytest

from sap.chart import StatSerializer


@pytest.mark.parametrize(
    ("payload", "percent"),
    [
        ({"name": "visits", "description": "Visits", "value": 1}, None),
        ({"name": "visits", "description": "Visits", "value": 1, "total": 2}, 50),
        ({"name": "visits", "description": "Visits", "value": 1, "total": 0}, 0),
    ],
)
def test_stat_serializer_percent(payload: dict[str, typing.Any], percent: int | None) -> None:
    """Calculate a stat percentage from value and total."""
    stat = StatSerializer(**payload)
    if percent is None:
        assert stat.percent is None
    else:
        assert stat.percent == percent
