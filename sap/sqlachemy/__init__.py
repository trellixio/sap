import pydantic
from typing import TypeVar, Union
from sqlalchemy.orm import DeclarativeBase


AlchemyModelT = TypeVar("AlchemyModelT", bound=DeclarativeBase)
AlchemyOrPydanticModelT = TypeVar("AlchemyOrPydanticModelT", bound=Union[pydantic.BaseModel, DeclarativeBase])
