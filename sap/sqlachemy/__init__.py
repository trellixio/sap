import pydantic
from typing import TypeVar, Union

try:
    from sqlalchemy.orm import DeclarativeBase
except ImportError: 
    from pydantic import BaseModel as DeclarativeBase


AlchemyModelT = TypeVar("AlchemyModelT", bound=DeclarativeBase)
AlchemyOrPydanticModelT = TypeVar("AlchemyOrPydanticModelT", bound=Union[pydantic.BaseModel, DeclarativeBase])
