# mypy: ignore-errors
# pylint: skip-file

import inspect
from copy import copy
from typing import Any, List, Optional, Type

from beanie.odm.fields import ExpressionField, Link, LinkInfo, LinkTypes
from beanie.odm.utils.init import Initializer as Initializer
from pydantic import BaseModel
from pydantic.fields import ModelField
from pydantic.typing import get_origin


def detect_link(field: ModelField) -> Optional[LinkInfo]:
    """
    It detects link and returns LinkInfo if any found.

    :param field: ModelField
    :return: Optional[LinkInfo]
    """
    if issubclass(field.type_, Link):
        if field.allow_none is True:
            return LinkInfo(
                field=field.name,
                model_class=field.sub_fields[0].type_,  # type: ignore
                link_type=LinkTypes.OPTIONAL_DIRECT,
            )
        return LinkInfo(
            field=field.name,
            model_class=field.sub_fields[0].type_,  # type: ignore
            link_type=LinkTypes.DIRECT,
        )
    if (
        inspect.isclass(get_origin(field.outer_type_))
        and issubclass(get_origin(field.outer_type_), list)  # type: ignore
        and len(field.sub_fields) == 1  # type: ignore
    ):
        internal_field = field.sub_fields[0]  # type: ignore
        if internal_field.type_ == Link:
            if field.allow_none is True:
                return LinkInfo(
                    field=field.name,
                    model_class=internal_field.sub_fields[0].type_,  # type: ignore
                    link_type=LinkTypes.OPTIONAL_LIST,
                )
            return LinkInfo(
                field=field.name,
                model_class=internal_field.sub_fields[0].type_,  # type: ignore
                link_type=LinkTypes.LIST,
            )
    return None


def init_document_fields(cls) -> None:
    """
    Init class fields
    :return: None
    """
    cls.update_forward_refs()

    def check_nested_links(link_info: LinkInfo, prev_models: List[Type[BaseModel]]) -> None:
        if link_info.model_class in prev_models:
            return
        for k, v in link_info.model_class.__fields__.items():
            nested_link_info = detect_link(v)
            if nested_link_info is None:
                continue

            if link_info.nested_links is None:
                link_info.nested_links = {}
            link_info.nested_links[v.name] = nested_link_info
            new_prev_models = copy(prev_models)
            new_prev_models.append(link_info.model_class)
            check_nested_links(nested_link_info, prev_models=new_prev_models)

    if cls._link_fields is None:
        cls._link_fields = {}
    for k, v in cls.__fields__.items():
        path = v.alias or v.name
        setattr(cls, k, ExpressionField(path))

        link_info = detect_link(v)
        if link_info is not None:
            cls._link_fields[v.name] = link_info
            check_nested_links(link_info, prev_models=[])

    cls._hidden_fields = cls.get_hidden_fields()


Initializer.init_document_fields = staticmethod(init_document_fields)
