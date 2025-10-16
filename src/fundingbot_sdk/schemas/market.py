"""Схемы рынка (market) SDK.

Определяют компактные pydantic dataclass‑модели метаданных инструмента: точности,
граничные лимиты и идентификацию символа. Схемы согласованы с контрактами
``fundingbot_sdk.contracts.protocols.InstrumentProtocol`` и предназначены для
нормализации данных поставщиков (например, биржевых API).

Модели принимают избыточные входные ключи и игнорируют их (см. базовый ``BaseDTO``),
что упрощает интеграцию с различными источниками. Состав полей может расширяться
в минорных релизах без нарушения обратной совместимости.
"""
from decimal import Decimal

from pydantic import AliasPath, Field
from pydantic.dataclasses import dataclass as pdc_dataclass

from fundingbot_sdk.schemas.base import ResponseBase


@pdc_dataclass(slots=True, frozen=True)
class MarketResponse(ResponseBase):
    """Нормализованная модель метаданных инструмента.

    Содержит идентификатор символа, размер контракта и плоские поля точности/лимитов,
    согласованные с ``InstrumentProtocol``. Поля маппятся на вложенные ключи источника
    через ``validation_alias``.
    """

    symbol: str = Field(..., validation_alias="symbol")
    contract_size: Decimal = Field(..., validation_alias="contractSize")

    # точности
    amount_precision: Decimal = Field(..., validation_alias=AliasPath("precision", "amount"))
    price_precision: Decimal = Field(..., validation_alias=AliasPath("precision", "price"))
    cost_precision: Decimal | None = Field(default=None, validation_alias=AliasPath("precision", "cost"))

    # лимиты (могут отсутствовать на источнике)
    min_cost: Decimal | None = Field(default=None, validation_alias=AliasPath("limits", "cost", "min"))
    max_cost: Decimal | None = Field(default=None, validation_alias=AliasPath("limits", "cost", "max"))
    min_amount: Decimal | None = Field(default=None, validation_alias=AliasPath("limits", "amount", "min"))
    max_amount: Decimal | None = Field(default=None, validation_alias=AliasPath("limits", "amount", "max"))
    min_price: Decimal | None = Field(default=None, validation_alias=AliasPath("limits", "price", "min"))
    max_price: Decimal | None = Field(default=None, validation_alias=AliasPath("limits", "price", "max"))
