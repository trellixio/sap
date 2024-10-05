"""Patch used for overload Beanie."""

# mypy: ignore-errors

from typing import Any, List, Optional, Union, get_args, get_origin

from beanie.odm.fields import LinkInfo, LinkTypes
from beanie.odm.registry import DocsRegistry
from beanie.odm.utils.init import Initializer as Initializer  # pylint: disable=useless-import-alias
from pydantic.fields import FieldInfo

from sap.typing import UnionType

from .link import Link as MLink

original__detect_link = Initializer.detect_link


def detect_link(self, field: FieldInfo, field_name: str) -> Optional[LinkInfo]:
    """
    Detect link and returns LinkInfo if any found.

    :param field: FieldInfo
    :param field_name: str
    :return: Optional[LinkInfo]
    """
    origin = get_origin(field.annotation)
    args = get_args(field.annotation)

    def get_link_info(link_type: str, type_args: list[Any]):
        return LinkInfo(
            field_name=field_name,
            lookup_field_name=field_name,
            document_class=DocsRegistry.evaluate_fr(type_args[0]),  # type: ignore
            link_type=link_type,
        )

    if origin is MLink:
        return get_link_info(LinkTypes.DIRECT, type_args=args)

    if origin is List and get_origin(args[0]) is MLink:
        return get_link_info(LinkTypes.LIST, type_args=get_args(args[0]))

    if origin in [Union, UnionType] and get_origin(args[0]) is MLink:
        return get_link_info(LinkTypes.OPTIONAL_DIRECT, type_args=get_args(args[0]))

    return original__detect_link(self, field=field, field_name=field_name)


Initializer.detect_link = detect_link
