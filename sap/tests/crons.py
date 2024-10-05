"""
Test Crons.

Helpers to make it easier to create test cases for crons.
"""

import typing

import beanie
from beanie.odm.queries.find import FindMany


def get_filter_queryset_dummy() -> typing.Callable[[FindMany[typing.Any]], FindMany[typing.Any]]:
    """Return initial queryset without filtering."""

    def filter_nothing(queryset: FindMany[typing.Any]) -> FindMany[typing.Any]:
        """Filter queryset."""
        return queryset

    return filter_nothing


def get_filter_queryset_for_merchant(
    model_class: type[beanie.Document], merchant_id: beanie.PydanticObjectId
) -> typing.Callable[[FindMany[typing.Any]], FindMany[typing.Any]]:
    """Filter the queryset to the test merchant.

    Use this filter on a queryset returning a list of Merchant or objects related to Merchants.
    :model_class: The class of the data being filtered.
    """

    def filter_merchant(queryset: FindMany[typing.Any]) -> FindMany[typing.Any]:
        """Filter queryset to a specific merchant."""
        return queryset.find_many(model_class.id == merchant_id)

    def filter_related_objects(queryset: FindMany[typing.Any]) -> FindMany[typing.Any]:
        """Filter queryset to object related to a specific merchant."""
        if hasattr(model_class, "merchant"):
            return queryset.find_many(model_class.merchant.id == merchant_id)
        raise NotImplementedError

    if hasattr(model_class, "merchant"):
        return filter_related_objects

    if hasattr(model_class, "beans_card_id"):
        return filter_merchant

    raise NotImplementedError
