from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import Field
from pydantic.dataclasses import dataclass as pdc_dataclass

from fundingbot_sdk.schemas.base import ResponseBase


@pdc_dataclass(slots=True, frozen=True)
class TickerResponse(ResponseBase):
    """Нормализованная модель тикера: символ, последняя цена, метка времени, исходные данные."""

    symbol: str = Field(..., validation_alias="symbol")
    last_price: Decimal = Field(..., description="Последняя цена сделки", validation_alias="last")

    # время
    timestamp: int | None = Field(default=None, description="Метка времени (мс)", validation_alias="timestamp")
    datetime_iso: datetime | None = Field(default=None, description="Время ISO", validation_alias="datetime")

    # оригинальный ответ поставщика
    info: dict[str, Any] = Field(default_factory=dict, description="Сырые данные источника", validation_alias="info")
