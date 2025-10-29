# pylint: disable=too-many-locals

"""
# Serializers.

Handle data validation.
"""

from __future__ import annotations

import inspect
import json
from datetime import date, datetime, time
from decimal import Decimal
from typing import (
    TYPE_CHECKING,
    Any,
    ClassVar,
    Generic,
    List,
    Optional,
    Sequence,
    TypeVar,
    Union,
    get_args,
    get_origin,
    overload,
)

import pydantic_core
from typing_extensions import Literal

from fastapi import Request
from pydantic import BaseModel
from pydantic.fields import FieldInfo, PrivateAttr

from sap.beanie.document import Document
from sap.sqlachemy import AlchemyOrPydanticModelT
from sap.typing import UnionType

from .pagination import CursorInfo, PaginatedData

try:
    from sqlalchemy.orm import DeclarativeBase
except ImportError:
    # Use Document as DeclarativeBase if sqlalchemy is not available
    DeclarativeBase = Document  # type: ignore

if TYPE_CHECKING:
    from pydantic.main import IncEx
    from sqlalchemy.ext.asyncio import AsyncSession


class ObjectSerializer(BaseModel, Generic[AlchemyOrPydanticModelT]):
    """Serialize an object for retrieve or list."""

    serializer_metadata: ClassVar[dict[str, Any]] = {}

    @classmethod
    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Initialize metadata about getter methods."""
        super().__init_subclass__(**kwargs)

        # Analyze all get_* methods
        for name in cls.__dict__:
            method = getattr(cls, name)
            if name.startswith("get_") and callable(method):
                # Check if the method accepts context
                if "context" in method.__code__.co_varnames:
                    cls.serializer_metadata[name] = {"accepts_context": True}
                else:
                    cls.serializer_metadata[name] = {"accepts_context": False}

    @classmethod
    def get_id(cls, instance: AlchemyOrPydanticModelT) -> str:
        """Return the ID of the object."""
        if hasattr(instance, "public_id"):
            return str(instance.public_id)

        if isinstance(instance, (Document, DeclarativeBase)):
            return str(instance.id)  # type: ignore

        raise NotImplementedError

    @classmethod
    def get_object(cls, instance: AlchemyOrPydanticModelT) -> str:
        """Return the type of the object."""
        if hasattr(cls, "object"):
            return str(cls.object)

        return instance.__class__.__name__.lower()

    @classmethod
    def get_created(cls, instance: AlchemyOrPydanticModelT) -> datetime:
        """Return the user creation date."""
        if isinstance(instance, Document):
            assert instance.doc_meta.created  # let mypy know that this cannot be null
            return instance.doc_meta.created

        if hasattr(instance, "created") and isinstance(instance.created, datetime):
            return instance.created

        raise NotImplementedError

    @classmethod
    def get_updated(cls, instance: AlchemyOrPydanticModelT) -> datetime:
        """Return the user creation date."""
        if isinstance(instance, Document):
            assert instance.doc_meta.updated  # let mypy know that this cannot be null
            return instance.doc_meta.updated

        if hasattr(instance, "updated") and isinstance(instance.updated, datetime):
            return instance.updated

        raise NotImplementedError

    @classmethod
    def _get_instance_data(
        cls,
        instance: AlchemyOrPydanticModelT,
        exclude: Optional["IncEx"] = None,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Retrieve the serializer value from the instance and getters."""
        context = context or {}

        def _get_field_value(field_name: str, field_info: FieldInfo) -> Any:
            """Retrieve the value of a serialized field."""

            # A: An explicit method was declared to retrieve the value
            if get_field := getattr(cls, f"get_{field_name}", None):
                if cls.serializer_metadata.get(f"get_{field_name}", {}).get("accepts_context"):
                    return get_field(instance=instance, context=context)
                return get_field(instance=instance)

            related_object = getattr(instance, field_name, None)

            origin = get_origin(field_info.annotation) or field_info.annotation
            args = get_args(field_info.annotation)

            # B. The field is an embedded serializer
            if inspect.isclass(origin) and issubclass(origin, ObjectSerializer):
                return origin.read(related_object, exclude=exclude, context=context) if related_object else None

            # C. The field is a list of embedded serializer or optional
            if (
                origin in [List, Union, UnionType]
                and inspect.isclass(args[0])
                and issubclass(args[0], ObjectSerializer)
            ):
                value_default: Union[list[Any], None] = [] if origin == List else None
                return (
                    args[0].read(related_object, exclude=exclude, context=context) if related_object else value_default
                )

            return getattr(instance, field_name)

        data = {}
        exclude = exclude or set()
        for field_name, field_info in cls.model_fields.items():
            if field_name in exclude:
                continue
            data[field_name] = _get_field_value(field_name, field_info)
        return data

    @classmethod
    def read(
        cls: type["SerializerT"],
        instance: AlchemyOrPydanticModelT,
        exclude: Optional["IncEx"] = None,
        context: dict[str, Any] | None = None,
    ) -> "SerializerT":
        """Serialize a single object instance."""
        return cls(**cls._get_instance_data(instance, exclude=exclude, context=context))

    @classmethod
    def read_list(
        cls: type["SerializerT"],
        instance_list: Sequence[AlchemyOrPydanticModelT],
        exclude: Optional["IncEx"] = None,
        context: dict[str, Any] | None = None,
    ) -> list["SerializerT"]:
        """Serialize a list of objects."""
        return [cls.read(instance, exclude=exclude, context=context) for instance in instance_list]

    @classmethod
    def read_page(
        cls,
        instance_list: Sequence[AlchemyOrPydanticModelT],
        cursor_info: CursorInfo,
        request: Request,
        context: dict[str, Any] | None = None,
    ) -> PaginatedData["SerializerT"]:
        """Serialize a list of objects."""
        page_next = cursor_info.get_next()
        page_previous = cursor_info.get_previous()
        return PaginatedData(
            count=cursor_info.get_count(),
            next=str(request.url.include_query_params(cursor=page_next)) if page_next else None,
            previous=str(request.url.include_query_params(cursor=page_previous)) if page_previous else None,
            data=cls.read_list(instance_list, context=context),
        )


SerializerT = TypeVar("SerializerT", bound=ObjectSerializer[Any])


class WriteObjectSerializer(BaseModel, Generic[AlchemyOrPydanticModelT]):
    """Serialize an object for create or update."""

    _instance: Optional[AlchemyOrPydanticModelT] = PrivateAttr(default=None)

    _embedded_serializers: ClassVar[dict[str, type[BaseModel]]] = {}
    _document_fields: ClassVar[set[str]] = set()

    @property
    def instance(self) -> Optional[AlchemyOrPydanticModelT]:
        """Get the instance."""
        return self._instance

    @instance.setter
    def instance(self, instance: AlchemyOrPydanticModelT) -> None:
        """Set the instance."""
        self._instance = instance

    def __init__(self, instance: AlchemyOrPydanticModelT | None = None, **data: Any) -> None:
        """Initialize with instance."""
        super().__init__(**data)
        self._instance = instance

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """On subclass initialization, collect embedded serializers."""
        super().__init_subclass__(**kwargs)
        cls._embedded_serializers = {}
        for field_name, field_info in cls.model_fields.items():
            if inspect.isclass(field_info.annotation):
                if issubclass(field_info.annotation, WriteObjectSerializer):
                    cls._embedded_serializers[field_name] = field_info.annotation
                if issubclass(field_info.annotation, Document):
                    cls._document_fields.add(field_name)

    @overload
    async def run_async_validators(self, *, db: "AsyncSession", **kwargs: Any) -> None:
        """run_async_validators overload for sqlachemy app using db."""

    @overload
    async def run_async_validators(self, **kwargs: Any) -> None:
        """run_async_validators overload for sqlachemy app using db."""

    async def run_async_validators(self, **kwargs: Any) -> None:
        """Check that data pass DB validation."""

        # Automatically run async validators on embedded serializers
        field_serializer: WriteObjectSerializer[AlchemyOrPydanticModelT]
        for field_name in self._embedded_serializers:
            if field_serializer := getattr(self, field_name):
                if self.instance:
                    field_serializer.instance = getattr(self.instance, field_name)
                await field_serializer.run_async_validators(**kwargs)

    def model_dump(
        self,
        *,
        mode: Literal["json", "python"] | str = "python",
        include: IncEx | None = None,
        exclude: IncEx | None = None,
        context: Any | None = None,
        by_alias: bool = False,
        exclude_unset: bool = False,
        exclude_defaults: bool = False,
        exclude_none: bool = False,
        round_trip: bool = False,
        warnings: bool | Literal["none", "warn", "error"] = True,
        serialize_as_any: bool = False,
    ) -> dict[str, Any]:
        """Dump the serializer data with exclusion of unwanted fields."""
        # Exclude from dumping
        exclude = exclude or set()
        exclude |= self._document_fields | {"instance", "_instance"}  # type: ignore

        # # Some fields are only excluded from being cascade dumps to dict,
        # # but their original value is still needed
        # exclude_doc_dumps = {}

        result = super().model_dump(
            mode=mode,
            include=include,
            exclude=exclude,
            context=context,
            by_alias=by_alias,
            exclude_unset=exclude_unset,
            exclude_defaults=exclude_defaults,
            exclude_none=exclude_none,
            round_trip=round_trip,
            warnings=warnings,
            serialize_as_any=serialize_as_any,
        )

        # for field_name in exclude_doc_dumps:
        #     result[field_name] = getattr(self, field_name)

        instance_embedded: Optional[BaseModel]
        for field_name, field_model in self._embedded_serializers.items():
            if not result[field_name]:
                continue
            if instance_embedded := getattr(self.instance, field_name, None):
                result[field_name] = instance_embedded.model_copy(update=result[field_name]).model_dump()
            else:
                result[field_name] = field_model(**result[field_name]).model_dump()

        return result

    @overload
    async def create(self, *, db: "AsyncSession", **kwargs: Any) -> AlchemyOrPydanticModelT:
        """Create overload for sqlachemy app using db."""

    @overload
    async def create(self, **kwargs: Any) -> AlchemyOrPydanticModelT:
        """Create overload for sqlachemy app using db."""

    async def create(self, **kwargs: Any) -> AlchemyOrPydanticModelT:
        """Create the object in the database using the data extracted by the serializer."""
        instance_class: type[AlchemyOrPydanticModelT] | None = type(self).model_fields["instance"].annotation
        if instance_class and issubclass(instance_class, Document):
            return await instance_class(**self.model_dump()).create()
        raise NotImplementedError

    @overload
    async def update(self, *, db: "AsyncSession", **kwargs: Any) -> AlchemyOrPydanticModelT:
        """Update overload for sqlachemy app using db."""

    @overload
    async def update(self, **kwargs: Any) -> AlchemyOrPydanticModelT:
        """Update overload for sqlachemy app using db."""

    async def update(self, **kwargs: Any) -> AlchemyOrPydanticModelT:
        """Update the object in the database using the data extracted by the serializer."""
        assert self.instance

        if isinstance(self.instance, Document):
            self.instance = self.instance.model_copy(update=self.model_dump())
            assert self.instance and isinstance(self.instance, Document)
            await self.instance.save()
            return self.instance

        raise NotImplementedError


WSerializerT = TypeVar("WSerializerT", bound=WriteObjectSerializer[Any])


class CustomJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles Decimal and datetime objects."""

    def default(self, o: Any) -> Any:
        """Convert special objects to JSON serializable format."""
        if isinstance(o, Decimal):
            return float(o)
        if isinstance(o, (datetime, date)):
            return o.isoformat()
        if isinstance(o, time):
            return o.strftime("%H:%M:%S")
        if isinstance(o, pydantic_core.Url):
            return str(o)
        if isinstance(o, BaseModel):
            return o.model_dump()
        return super().default(o)
