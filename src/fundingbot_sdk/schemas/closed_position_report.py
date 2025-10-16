from datetime import datetime
from decimal import Decimal
from typing import Any, cast

from pydantic import Field
from pydantic.dataclasses import dataclass as pdc_dataclass

from fundingbot_sdk.schemas.base import ResponseBase


@pdc_dataclass(slots=True, frozen=True)
class Fee(ResponseBase):
    """Элемент детализации комиссий за сделки."""

    type: str = Field(..., description="Тип комиссии: maker/taker/other", validation_alias="type")
    currency: str = Field(..., description="Валюта комиссии", validation_alias="currency")
    cost: Decimal = Field(..., description="Сумма комиссии (отрицательное значение - списание)", validation_alias="cost")
    info: dict[str, Any] = Field(default_factory=dict, description="Сырые данные источника", validation_alias="info")


@pdc_dataclass(slots=True, frozen=True)
class ClosePositionReportResponse(ResponseBase):
    """Отчёт о закрытой позиции на бирже.

    Содержит агрегированные сведения об исполнениях открытия/закрытия, начисленном funding,
    комиссиях и дополнительной мета‑информации.
    """

    exchange: str = Field(..., description="Биржа", validation_alias="exchange")
    symbol: str = Field(..., description="Символ CCXT, например BTC/USDT:USDT", validation_alias="symbol")
    side: str = Field(..., description="buy/sell", validation_alias="side")
    contracts: Decimal = Field(..., description="Количество контрактов", validation_alias="contracts")
    opened_at: datetime = Field(
        ...,
        description="Фактическое время открытия (по исполнению)",
        validation_alias="opened_at"
    )
    closed_at: datetime = Field(
        ...,
        description="Фактическое время закрытия (по исполнению)",
        validation_alias="closed_at"
    )
    entry_price_avg: Decimal = Field(
        ..., description="Средняя цена входа по исполнениям", validation_alias="entry_price_avg"
    )
    exit_price_avg: Decimal = Field(
        ..., description="Средняя цена выхода по исполнениям", validation_alias="exit_price_avg"
    )
    leverage: Decimal = Field(
        ..., description="Плечо позиции на момент открытия/ведения", validation_alias="leverage"
    )
    funding_income: Decimal = Field(
        ...,
        description="Начисление/списание funding за период позиции",
        validation_alias="funding_income",
    )
    funding_income_percent: Decimal | None = Field(
        default=None,
        description="Funding в процентах от нотионала позиции (contracts x avg price)",
        validation_alias="funding_income_percent",
    )
    fees_total_percent: Decimal | None = Field(
        default=None,
        description="Комиссии в процентах от нотионала позиции (contracts x avg price)",
        validation_alias="fees_total_percent",
    )
    fees_total: Decimal = Field(
        default=Decimal(0), description="Сумма всех комиссий (в валюте расчёта)",
        validation_alias="fees_total"
    )
    fees: list[Fee] = Field(
        default_factory=lambda: cast("list[Fee]", []),
        description="Детализация комиссий",
        validation_alias="fees",
    )
    extra: dict[str, Any] = Field(
        default_factory=dict, description="Произвольные дополнительные поля",
        validation_alias="extra"
    )
