# mypy: ignore-errors
# pylint: skip-file

from typing import Optional, get_args, get_origin

from beanie.odm.fields import LinkInfo, LinkTypes
from beanie.odm.registry import DocsRegistry
from beanie.odm.utils.init import Initializer as Initializer
from pydantic.fields import FieldInfo
from pydantic.typing import get_origin

from .link import Link as MLink

original__detect_link = Initializer.detect_link


def detect_link(self, field: FieldInfo, field_name: str) -> Optional[LinkInfo]:
    """
    It detects link and returns LinkInfo if any found.

    :param field: ModelField
    :return: Optional[LinkInfo]
    """
    if get_origin(field.annotation) is MLink:
        args = get_args(field.annotation)
        return LinkInfo(
            field_name=field_name,
            lookup_field_name=field_name,
            document_class=DocsRegistry.evaluate_fr(args[0]),  # type: ignore
            link_type=LinkTypes.DIRECT,
        )
    return original__detect_link(self, field=field, field_name=field_name)


Initializer.detect_link = detect_link
