"""
# Serializers.

Handle data validation.
"""
from __future__ import annotations

import typing
import datetime

from pydantic import BaseModel, Field, create_model, validator
from pydantic.fields import ModelField

ModelType = typing.TypeVar("ModelType", bound=BaseModel)
SerializerType = typing.TypeVar("SerializerType", bound=BaseModel)


class ObjectSerializer(BaseModel):
    """Serialize an object."""

    @classmethod
    def get_id(cls, instance: ModelType) -> str:
        return str(instance.id)

    @classmethod
    def get_created(cls, instance: ModelType) -> datetime.datetime:
        """Return the user creation date."""
        return instance.doc_meta.created

    @classmethod
    def _get_instance_data(cls, instance: ModelType) -> dict[str, typing.Any]:
        """Retrieve the serializer value from the instance and getters."""
        data = {}
        for field_name in cls.__fields__.keys():
            if hasattr(cls, f"get_{field_name}"):
                data[field_name] = getattr(cls, f"get_{field_name}")(instance=instance)
            else:
                data[field_name] = getattr(instance, field_name)
        return data

    @classmethod
    def read(cls, instance: ModelType) -> "SerializerType":
        """Serialize a single object instance."""
        return cls(**cls._get_instance_data(instance))

    @classmethod
    def read_list(cls, instance_list: list[ModelType]) -> list[SerializerType]:
        """Serialize a list of objects."""
        return [cls.read(instance) for instance in instance_list]

    @classmethod
    def class_write(cls) -> typing.Type[BaseModel]:
        attributes = {}
        field: ModelField
        for attr, field in cls.__fields__.items():
            if field.field_info.extra.get("editable"):
                attributes[attr] = (field.type_, ...) if field.default is None else field.default

        return create_model(
            f"Write{cls.__name__}",
            __module__=cls.__module__,
            # __base__=cls,
            **attributes,
        )

    # @classmethod
    # def update(cls, instance: ModelType, data: dict[str, typing.Any]) -> ObjectSerializer:
    #     data_instance = cls._get_instance_data(instance)
    #     for key, value in data.items():
    #         if key in cls.__fields__.keys():
    #             field: ModelField = cls.__fields__[key]
    #             if field.extra.get("editable"):
    #                 data_instance[key] = value
    #     return cls(**data_instance)
