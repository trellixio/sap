"""
Helpers for views.

Helpers methods used in app.views.
"""

import typing
from dataclasses import dataclass

import pydantic
from fastapi import Request
from fastapi.datastructures import FormData

from sap.beanie import Document
from .utils import Flash, FlashLevel, pydantic_format_errors, unflatten_form_data, merge_dict_deep
from .serializers import ObjectSerializer, WriteObjectSerializer
from .exceptions import Validation422Error


@dataclass
class FormValidation:
    """Return the result of data validation for a form serializer."""

    data: FormData
    errors: dict[str, typing.Any]
    serializer: pydantic.BaseModel


async def validate_form(
    request: Request,
    serializer_write_class: type[WriteObjectSerializer],
    serializer_read_class: type[ObjectSerializer] = None,
    instance: Document = None,
) -> FormValidation:
    """Check that a submitted form pass validation."""
    form_data: dict[str, typing.Any] = {}

    if serializer_read_class and instance:
        # Means this is an update. So we first populate existing data
        serializer_read: ObjectSerializer = serializer_read_class.read(instance=instance)
        form_data = serializer_read.dict()

    form_data_received = await request.form()
    form_data = merge_dict_deep(form_data, unflatten_form_data(form_data_received))
    form_errors: dict[str, typing.Any] = {}

    async def run_validation() -> pydantic.BaseModel:
        """Run serializer validation."""
        serializer_ = serializer_write_class(**form_data, instance=instance)
        await serializer_.run_async_validators()
        return serializer_

    serializer_write: typing.Optional[WriteObjectSerializer] = None

    try:
        serializer_write = await run_validation()
    except pydantic.ValidationError as err:
        form_errors = pydantic_format_errors(err.errors())
        msg = "Les informations soumises ne sont pas valides."
        form_errors["__root__"] = {"msg": msg}
        Flash.add_message(request, msg, level=FlashLevel.ERROR)
    except (AssertionError, Validation422Error) as err:
        form_errors["__root__"] = {"msg": str(err)}
        Flash.add_message(request, str(err), level=FlashLevel.ERROR)

    return FormValidation(serializer=serializer_write, data=form_data, errors=form_errors)
