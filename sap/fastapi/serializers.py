"""
# Serializers.

Handle data validation.
"""
from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Any, Generic, Optional, TypeVar, Union

from fastapi import Request
from pydantic import BaseModel
from pydantic.fields import SHAPE_LIST

from sap.beanie.document import Document

from . import utils

ModelType = TypeVar("ModelType", bound=Document)
# SerializerType = TypeVar("SerializerType", bound=BaseModel)

if TYPE_CHECKING:
    from pydantic.typing import AbstractSetIntStr, DictStrAny, MappingIntStrAny


class CursorInfo:
    """Contains information on how the list should paginated"""

    offset: int = 0
    limit: int = 10
    sort: str = "-doc_meta.created"

    def __init__(self, request: Request) -> None:
        """Initialize the cursor info."""
        cursor_str = request.query_params.get("cursor", "")
        try:
            limit, offset = utils.base64_url_decode(cursor_str).split(",")
        except ValueError:
            return
        self.limit, self.offset = int(limit), int(offset)

    def get_beanie_query_params(self) -> dict[str, Any[int, str]]:
        """Return params to apply to the database query when using beanie"""
        return {
            "limit": self.limit,
            "skip": self.offset,
            "sort": self.sort,
        }

    def get_next(self) -> Optional[str]:
        """Get the cursor to paginate forward."""
        offset = self.offset + self.limit
        return utils.base64_url_encode(f"{self.limit},{offset}")

    def get_previous(self) -> Optional[str]:
        """Get the cursor to paginate backward."""
        offset = self.offset - self.limit
        if offset <= 0:
            return None
        return utils.base64_url_encode(f"{self.limit},{offset}")


class ObjectSerializer(Generic[ModelType], BaseModel):
    """Serialize an object for retrieve or list."""

    @classmethod
    def get_id(cls, instance: ModelType) -> str:
        return str(instance.id)

    @classmethod
    def get_created(cls, instance: ModelType) -> datetime.datetime:
        """Return the user creation date."""
        assert instance.doc_meta.created  # let mypy know that this cannot be null
        return instance.doc_meta.created

    @classmethod
    def get_updated(cls, instance: ModelType) -> datetime.datetime:
        """Return the user creation date."""
        assert instance.doc_meta.updated  # let mypy know that this cannot be null
        return instance.doc_meta.updated

    @classmethod
    def _get_instance_data(cls, instance: ModelType) -> dict[str, Any]:
        """Retrieve the serializer value from the instance and getters."""
        data = {}
        for field_name, field in cls.__fields__.items():
            if hasattr(cls, f"get_{field_name}"):
                data[field_name] = getattr(cls, f"get_{field_name}")(instance=instance)
            elif issubclass(field.type_, ObjectSerializer):
                related_object = getattr(instance, field_name)
                if field.shape == SHAPE_LIST:
                    data[field_name] = field.type_.read_list(related_object) if related_object else []
                else:
                    data[field_name] = field.type_.read(related_object) if related_object else None
            else:
                data[field_name] = getattr(instance, field_name)
        return data

    @classmethod
    def read(cls, instance: ModelType) -> "SerializerType":
        """Serialize a single object instance."""
        return cls(**cls._get_instance_data(instance))

    @classmethod
    def read_list(cls, instance_list: list[ModelType]) -> list["SerializerType"]:
        """Serialize a list of objects."""
        return [cls.read(instance) for instance in instance_list]

    @classmethod
    def read_page(
        cls,
        instance_list: list[ModelType],
        cursor_info: CursorInfo,
        request: Request,
    ) -> PaginatedData["SerializerType"]:
        """Serialize a list of objects."""

        # TODO: implemented proper cursor pagination, for now fake it till you make it.

        next = cursor_info.get_next()
        previous = cursor_info.get_previous()
        return PaginatedData(
            count=0,
            next=str(request.url.include_query_params(cursor=next)) if next else None,
            previous=str(request.url.include_query_params(cursor=previous)) if previous else None,
            data=cls.read_list(instance_list),
        )


SerializerType = TypeVar("SerializerType", bound=ObjectSerializer)


class PaginatedData(Generic[SerializerType], BaseModel):
    """Represent the structure of an API paginated list response."""

    object: str = "list"
    count: int
    next: Optional[str]
    previous: Optional[str]
    data: list[Any]


class WriteObjectSerializer(Generic[ModelType], BaseModel):
    """Serialize an object for create or update."""

    instance: Optional[ModelType] = None

    def dict(
        self,
        *,
        include: Optional[Union["AbstractSetIntStr", "MappingIntStrAny"]] = None,
        exclude: Optional[Union["AbstractSetIntStr", "MappingIntStrAny"]] = None,
        by_alias: bool = False,
        skip_defaults: Optional[bool] = None,
        exclude_unset: bool = False,
        exclude_defaults: bool = False,
        exclude_none: bool = False,
    ) -> "DictStrAny":
        """Dumps the serializer data with exclusion of unwanted fields."""
        # Exclude from dumping
        exclude = exclude or {}
        exclude = exclude | {"instance": True}

        # Some fields are only excluded from being cascade dumps to dict,
        # but their original value is still needed
        exclude_dumps = {}

        for field_name, field in self.__fields__.items():
            field.field_info

            if issubclass(field.type_, Document):
                exclude_dumps[field_name] = True

            # Some fields are excluded as they are only needed for create
            if field.field_info.extra.get("exclude_update") and self.instance:
                exclude[field_name] = True

            # Some fields are excluded as they are only needed for update
            if field.field_info.extra.get("exclude_create") and not self.instance:
                exclude[field_name] = True

        exclude = exclude | exclude_dumps

        result = super().dict(
            include=include,
            exclude=exclude,
            by_alias=by_alias,
            skip_defaults=skip_defaults,
            exclude_unset=exclude_unset,
            exclude_defaults=exclude_defaults,
            exclude_none=exclude_none,
        )

        for field_name in exclude_dumps:
            result[field_name] = getattr(self, field_name)

        return result
