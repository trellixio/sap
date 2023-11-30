"""
# Serializers.

Handle data validation.
"""
from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Any, Generic, Optional, TypeVar, Union

from fastapi import Request
from pydantic import BaseModel
from pydantic.fields import SHAPE_LIST, ModelField

from sap.beanie.document import DocT, Document

from .pagination import CursorInfo, PaginatedData

if TYPE_CHECKING:
    from pydantic.typing import AbstractSetIntStr, DictStrAny, MappingIntStrAny

    ExcludeType = Union[AbstractSetIntStr, MappingIntStrAny]


class ObjectSerializer(Generic[DocT], BaseModel):
    """Serialize an object for retrieve or list."""

    @classmethod
    def get_id(cls, instance: DocT) -> str:
        """Return the Mongo ID of the object."""
        return str(instance.id)

    @classmethod
    def get_created(cls, instance: DocT) -> datetime.datetime:
        """Return the user creation date."""
        assert instance.doc_meta.created  # let mypy know that this cannot be null
        return instance.doc_meta.created

    @classmethod
    def get_updated(cls, instance: DocT) -> datetime.datetime:
        """Return the user creation date."""
        assert instance.doc_meta.updated  # let mypy know that this cannot be null
        return instance.doc_meta.updated

    @classmethod
    def _get_instance_data(cls, instance: DocT, exclude: Optional["ExcludeType"] = None) -> dict[str, Any]:
        """Retrieve the serializer value from the instance and getters."""
        data = {}
        exclude = exclude or set()
        for field_name, field in cls.__fields__.items():
            if field_name in exclude:
                continue
            if hasattr(cls, f"get_{field_name}"):
                data[field_name] = getattr(cls, f"get_{field_name}")(instance=instance)
            elif issubclass(field.type_, ObjectSerializer):
                related_object = getattr(instance, field_name, None)
                if field.shape == SHAPE_LIST:
                    data[field_name] = (
                        field.type_.read_list(related_object, exclude=field.field_info.exclude)
                        if related_object
                        else []
                    )
                else:
                    data[field_name] = (
                        field.type_.read(related_object, exclude=field.field_info.exclude) if related_object else None
                    )
            else:
                data[field_name] = getattr(instance, field_name)
        return data

    @classmethod
    def read(cls: type["SerializerT"], instance: DocT, exclude: Optional["ExcludeType"] = None) -> "SerializerT":
        """Serialize a single object instance."""
        return cls(**cls._get_instance_data(instance, exclude=exclude))

    @classmethod
    def read_list(
        cls: type["SerializerT"], instance_list: list[DocT], exclude: Optional["ExcludeType"] = None
    ) -> list["SerializerT"]:
        """Serialize a list of objects."""
        return [cls.read(instance, exclude=exclude) for instance in instance_list]

    @classmethod
    def read_page(
        cls,
        instance_list: list[DocT],
        cursor_info: CursorInfo,
        request: Request,
    ) -> PaginatedData["SerializerT"]:
        """Serialize a list of objects."""

        # TODO: implemented proper cursor pagination, for now fake it till you make it.

        page_next = cursor_info.get_next()
        page_previous = cursor_info.get_previous()
        return PaginatedData(
            count=0,
            next=str(request.url.include_query_params(cursor=page_next)) if page_next else None,
            previous=str(request.url.include_query_params(cursor=page_previous)) if page_previous else None,
            data=cls.read_list(instance_list),
        )


SerializerT = TypeVar("SerializerT", bound=ObjectSerializer[Any])


class WriteObjectSerializer(Generic[DocT], BaseModel):
    """Serialize an object for create or update."""

    instance: Optional[DocT] = None

    async def run_async_validators(self, **kwargs: Any) -> None:
        """Check that data pass DB validation."""

        field: ModelField
        embedded_serializers = {}
        for field_name, field in self.__fields__.items():
            if issubclass(field.type_, WriteObjectSerializer):
                embedded_serializers[field_name] = field

        field_serializer: WriteObjectSerializer[DocT]
        for field_name in embedded_serializers:
            if field_serializer := getattr(self, field_name):
                if self.instance:
                    field_serializer.instance = getattr(self.instance, field_name)
                await field_serializer.run_async_validators(**kwargs)

    def dict(
        self,
        *,
        include: Optional["ExcludeType"] = None,
        exclude: Optional["ExcludeType"] = None,
        by_alias: bool = False,
        skip_defaults: Optional[bool] = None,
        exclude_unset: bool = False,
        exclude_defaults: bool = False,
        exclude_none: bool = False,
    ) -> "DictStrAny":
        """Dump the serializer data with exclusion of unwanted fields."""
        # Exclude from dumping
        exclude_: dict[Union[int, str], bool] = {"instance": True}
        if exclude:
            for x in exclude:
                exclude_[x] = True

        # Some fields are only excluded from being cascade dumps to dict,
        # but their original value is still needed
        exclude_doc_dumps = {}

        # Embedded documents need to be converted to object after dumps
        embedded_serializers = {}

        for field_name, field in self.__fields__.items():
            if field_name in exclude_:
                continue

            if issubclass(field.type_, Document):
                exclude_doc_dumps[field_name] = True
                exclude_[field_name] = True

            elif issubclass(field.type_, WriteObjectSerializer):
                embedded_serializers[field_name] = field.type_.__fields__["instance"].type_

            # # Some fields are excluded as they are only needed for create
            # if field.field_info.extra.get("exclude_update") and self.instance:
            #     exclude_[field_name] = True

            # # Some fields are excluded as they are only needed for update
            # elif field.field_info.extra.get("exclude_create") and not self.instance:
            #     exclude_[field_name] = True

        result = super().dict(
            include=include,
            exclude=exclude_,
            by_alias=by_alias,
            skip_defaults=skip_defaults,
            exclude_unset=exclude_unset,
            exclude_defaults=exclude_defaults,
            exclude_none=exclude_none,
        )

        for field_name in exclude_doc_dumps:
            result[field_name] = getattr(self, field_name)

        instance_embedded: Optional[BaseModel]
        for field_name, field_model in embedded_serializers.items():
            if not result[field_name]:
                continue
            if instance_embedded := getattr(self.instance, field_name, None):
                result[field_name] = instance_embedded.copy(update=result[field_name])
            else:
                result[field_name] = field_model(**result[field_name])

        return result

    async def create(self, **kwargs: Any) -> DocT:
        """Create the object in the database using the data extracted by the serializer."""
        instance_class: type[DocT] = self.__fields__["instance"].type_
        self.instance = await instance_class(**self.dict()).create()
        return self.instance

    async def update(self, **kwargs: Any) -> DocT:
        """Update the object in the database using the data extracted by the serializer."""
        assert self.instance
        instance: DocT = self.instance.copy(update=self.dict())
        await instance.save()
        self.instance = instance
        return instance


WSerializerT = TypeVar("WSerializerT", bound=WriteObjectSerializer[Any])
