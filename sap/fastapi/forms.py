"""
Helpers for views.

Helpers methods used in app.views.
"""


from dataclasses import dataclass
from typing import Any, Generic, Optional

import pydantic
from fastapi import Request

from sap.beanie.document import DocT

from .exceptions import Validation422Error
from .serializers import ObjectSerializer, WriteObjectSerializer, SerializerT
from .utils import Flash, FlashLevel, merge_dict_deep, pydantic_format_errors, unflatten_form_data


@dataclass
class FormValidation(Generic[SerializerT]):
    """Return the result of data validation for a form serializer."""

    data: dict[str, Any]
    errors: dict[str, Any]
    serializer: SerializerT


async def validate_form(
    request: Request,
    serializer_write_class: type[WriteObjectSerializer[DocT]],
    serializer_read_class: Optional[type[ObjectSerializer[DocT]]] = None,
    instance: Optional[DocT] = None,
) -> FormValidation[DocT]:
    """Check that a submitted form pass validation."""
    form_data: dict[str, Any] = {}

    if serializer_read_class and instance:
        # Means this is an update. So we first populate existing data
        serializer_read: ObjectSerializer[DocT] = serializer_read_class.read(instance=instance)
        form_data = serializer_read.dict()

    form_data_received = await request.form()
    form_data = merge_dict_deep(form_data, unflatten_form_data(form_data_received))
    form_errors: dict[str, Any] = {}

    async def run_validation() -> WriteObjectSerializer[DocT]:
        """Run serializer validation."""
        serializer_ = serializer_write_class(**form_data, instance=instance)
        await serializer_.run_async_validators()
        return serializer_

    serializer_write: WriteObjectSerializer[DocT]

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
