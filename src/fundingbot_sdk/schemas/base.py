from abc import ABC
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, field_serializer
from pydantic.dataclasses import dataclass as pdc_dataclass


class BaseSchema(BaseModel):
    """Базовая схема с общими настройками Pydantic v2."""

    model_config = ConfigDict(
        populate_by_name=True,         # разрешить заполнять поля как по alias, так и по их именам
        arbitrary_types_allowed=True,  # разрешить произвольные типы (Decimal и т.п.)
        frozen=True,                   # сделать экземпляры неизменяемыми (заменяет allow_mutation=False)
    )

    # универсальный сериализатор
    @field_serializer("*", when_used="json")
    def _serialize_decimal(self, v: Any) -> Any:  # noqa: ANN401, PLR6301
        """Преобразует Decimal ➜ str при выгрузке в JSON.

        Декоратор с mask '*' применяется ко всем полям; для любых других типов
        значение возвращается как есть.

        Returns:
            Any: Строка, если ``v`` является ``Decimal``, иначе исходное значение.

        """
        if isinstance(v, Decimal):
            return str(v)
        return v


@pdc_dataclass(
    config=ConfigDict(
        extra="ignore",
        populate_by_name=True,         # принимать и имена полей, и алиасы
        arbitrary_types_allowed=True,  # если где-то будут нестандартные типы
    ),
    frozen=True
)
class ResponseBase(ABC):
    @field_serializer("*", when_used="json")
    def _serialize_decimal(self, v: Any) -> Any:  # noqa: ANN401, PLR6301
        if isinstance(v, Decimal):
            return str(v)
        return v
