"""
# Serializers.

Handle data validation.
"""
from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Any, Generic, Optional, TypeVar, Union, get_args, get_origin, List
from typing_extensions import Literal

from fastapi import Request
from pydantic import BaseModel
from pydantic.fields import FieldInfo

from sap.beanie.document import DocT, Document

from .pagination import CursorInfo, PaginatedData

if TYPE_CHECKING:
    from pydantic.main import IncEx


class ObjectSerializer(BaseModel, Generic[DocT]):
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
    def _get_instance_data(cls, instance: DocT, exclude: Optional["IncEx"] = None) -> dict[str, Any]:
        """Retrieve the serializer value from the instance and getters."""

        def _get_field_value(field_name: str, field_info: FieldInfo) -> Any:
            """Retrieve the value of a serialized field"""

            # A: An explicit method was declared to retrieve the value
            if hasattr(cls, f"get_{field_name}"):
                return getattr(cls, f"get_{field_name}")(instance=instance)

            related_object = getattr(instance, field_name, None)

            assert field_info.annotation

            # B. The field is an embedded serializer
            if issubclass(field_info.annotation, ObjectSerializer):
                return (
                    field_info.annotation.read(related_object, exclude=field_info.exclude) if related_object else None
                )

            origin = get_origin(field_info.annotation)
            args = get_args(field_info.annotation)

            # C. The field is a list of embedded serializer
            if origin is List and issubclass(args[0], ObjectSerializer):
                return args[0].read_list(related_object, exclude=field_info.exclude) if related_object else []

            return getattr(instance, field_name)

        data = {}
        exclude = exclude or set()
        for field_name, field_info in cls.model_fields.items():
            if field_name in exclude:
                continue
            data[field_name] = _get_field_value(field_name, field_info)
        return data

    @classmethod
    def read(cls: type["SerializerT"], instance: DocT, exclude: Optional["IncEx"] = None) -> "SerializerT":
        """Serialize a single object instance."""
        return cls(**cls._get_instance_data(instance, exclude=exclude))

    @classmethod
    def read_list(
        cls: type["SerializerT"], instance_list: list[DocT], exclude: Optional["IncEx"] = None
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


class WriteObjectSerializer(BaseModel, Generic[DocT]):
    """Serialize an object for create or update."""

    instance: Optional[DocT] = None

    async def run_async_validators(self, **kwargs: Any) -> None:
        """Check that data pass DB validation."""

        embedded_serializers = {}
        for field_name, field_info in self.model_fields.items():
            if field_info.annotation and issubclass(field_info.annotation, WriteObjectSerializer):
                embedded_serializers[field_name] = field_info

        field_serializer: WriteObjectSerializer[DocT]
        for field_name in embedded_serializers:
            if field_serializer := getattr(self, field_name):
                if self.instance:
                    field_serializer.instance = getattr(self.instance, field_name)
                await field_serializer.run_async_validators(**kwargs)

    def model_dump(
        self,
        *,
        mode: Literal["json", "python"] | str = "python",
        include: Optional["IncEx"] = None,
        exclude: Optional["IncEx"] = None,
        by_alias: bool = False,
        exclude_unset: bool = False,
        exclude_defaults: bool = False,
        exclude_none: bool = False,
        round_trip: bool = False,
        warnings: bool = True,
    ) -> dict[str, Any]:
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

        for field_name, field_info in self.model_fields.items():
            if field_name in exclude_:
                continue

            if not field_info.annotation:
                continue

            if issubclass(field_info.annotation, Document):
                exclude_doc_dumps[field_name] = True
                exclude_[field_name] = True

            elif issubclass(field_info.annotation, WriteObjectSerializer):
                embedded_serializers[field_name] = field_info.annotation.model_fields["instance"].annotation

            # # Some fields are excluded as they are only needed for create
            # if field.field_info.extra.get("exclude_update") and self.instance:
            #     exclude_[field_name] = True

            # # Some fields are excluded as they are only needed for update
            # elif field.field_info.extra.get("exclude_create") and not self.instance:
            #     exclude_[field_name] = True

        result = super().model_dump(
            mode=mode,
            include=include,
            exclude=exclude_,
            by_alias=by_alias,
            exclude_unset=exclude_unset,
            exclude_defaults=exclude_defaults,
            exclude_none=exclude_none,
            round_trip=round_trip,
            warnings=warnings,
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
        instance_class: type[DocT] = self.model_fields["instance"].annotation
        self.instance = await instance_class(**self.model_dump()).create()
        return self.instance

    async def update(self, **kwargs: Any) -> DocT:
        """Update the object in the database using the data extracted by the serializer."""
        assert self.instance
        instance: DocT = self.instance.copy(update=self.dict())
        await instance.save()
        self.instance = instance
        return instance


WSerializerT = TypeVar("WSerializerT", bound=WriteObjectSerializer[Any])
