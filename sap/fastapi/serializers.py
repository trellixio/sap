"""
# Serializers.

Handle data validation.
"""
from __future__ import annotations

import datetime
import typing

from pydantic import BaseModel
from pydantic.fields import SHAPE_LIST

from beanie import Document

ModelType = typing.TypeVar("ModelType", bound=Document)
SerializerType = typing.TypeVar("SerializerType", bound=BaseModel)


class ObjectSerializer(BaseModel):
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
    def _get_instance_data(cls, instance: ModelType) -> dict[str, typing.Any]:
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
    def read_list(cls, instance_list: list[ModelType]) -> list[SerializerType]:
        """Serialize a list of objects."""
        return [cls.read(instance) for instance in instance_list]


# class WriteObjectSerializer(BaseModel):
#     """Serialize an object for create or update."""

#     @classmethod
#     def write(cls, instance: ModelType) -> "SerializerType":
#         """Serialize a single object instance."""
#         return cls(**cls._get_instance_data(instance))
