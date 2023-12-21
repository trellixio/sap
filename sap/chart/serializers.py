"""
Stat Serializer.

A serializer that helps normalize the format of statistics objects
"""

import typing
from decimal import Decimal, DecimalException

import pydantic


class StatSerializer(pydantic.BaseModel):
    """A stat object used to display a stat card."""

    name: str
    description: str
    value: int
    total: typing.Optional[int] = None
    percent: typing.Optional[Decimal] = None
    view: typing.Optional[str] = None  # URL the to the page to view the data with filter query

    @pydantic.model_validator(mode="before")
    @classmethod
    def set_percent(cls, values: dict[str, typing.Any]) -> dict[str, typing.Any]:
        """Calculate the percentage."""
        if values.get("total") is None:
            return values

        try:
            percent = Decimal(values["value"]) * 100 / values["total"]
        except (ZeroDivisionError, DecimalException):
            percent = 0

        values["percent"] = int(percent)
        return values
