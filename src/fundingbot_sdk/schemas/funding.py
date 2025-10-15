from datetime import UTC, datetime
from decimal import Decimal

from pydantic import Field, field_validator
from pydantic.dataclasses import dataclass as pdc_dataclass

from fundingbot_sdk.schemas.base import ResponseBase


@pdc_dataclass(slots=True, frozen=True)
class FundingRateResponse(ResponseBase):
    """Нормализует данные о ставке финансирования инструмента."""

    symbol: str = Field(..., validation_alias="symbol", description="Торговый инструмент")
    exchange: str = Field(..., validation_alias="exchange", description="Биржа")

    funding_rate: Decimal = Field(
        ...,
        validation_alias="fundingRate",
        description="Ставка финансирования (доля)"
    )
    funding_date: datetime = Field(
        ...,
        validation_alias="fundingTimestamp",
        description="Дата и время выплаты финансирования (ISO)"
    )

    @field_validator("symbol", mode="before")
    def _normalize_symbol(cls, v: str) -> str:  # noqa: D401, PLR6301
        """Приводит символ к виду BASE/USDT:USDT."""
        raw = str(v)
        if ":" in raw:
            return raw if raw.endswith(":USDT") else f"{raw}:USDT"
        if raw.endswith("USDT"):
            base = raw[:-4]
            return f"{base}/USDT:USDT"
        return raw

    @field_validator("funding_date", mode="before")
    def _to_datetime(cls, v: datetime | str | int) -> datetime:  # noqa: D401, PLR6301
        """Преобразует ISO или миллисекунды Unix к UTC‑aware datetime."""
        if isinstance(v, datetime):
            return v
        if isinstance(v, (int, float)):
            return datetime.fromtimestamp(int(v) / 1000, tz=UTC)
        # строка: допускаем суффикс Z
        iso = str(v).replace("Z", "+00:00")
        return datetime.fromisoformat(iso)
