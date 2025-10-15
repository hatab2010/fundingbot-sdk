from datetime import UTC, datetime as dt
from decimal import Decimal
from typing import Any, cast

from pydantic import Field, field_validator, model_validator
from pydantic.dataclasses import dataclass as pdc_dataclass

from fundingbot_sdk.schemas.base import ResponseBase


@pdc_dataclass(slots=True, frozen=True)
class PositionInfoResponse(ResponseBase):
    """Снимок открытой позиции в терминах SDK (минимум по PositionProtocol)."""

    timestamp: int = Field(..., description="Метка времени (мс)", validation_alias="timestamp")
    symbol: str = Field(..., description="Символ инструмента", validation_alias="symbol")
    collateral: Decimal = Field(..., description="Залог", validation_alias="collateral")
    contracts: Decimal = Field(..., description="Количество контрактов", validation_alias="contracts")
    datetime: dt = Field(..., description="Время в ISO", validation_alias="datetime")
    entry_price: Decimal = Field(..., description="Цена входа", validation_alias="entryPrice")
    hedged: bool = Field(..., description="Хеджированный режим", validation_alias="hedged")
    leverage: Decimal = Field(..., description="Кредитное плечо", validation_alias="leverage")
    liquidation_price: Decimal = Field(..., description="Цена ликвидации", validation_alias="liquidationPrice")
    notional: Decimal = Field(..., description="Нотиональная стоимость", validation_alias="notional")
    side: str = Field(..., description="Направление", validation_alias="side")
    margin_mode: str | None = Field(default=None, description="Режим маржи", validation_alias="marginMode")

    id: str | None = Field(default=None, description="Идентификатор позиции", validation_alias="id")
    stop_loss_price: Decimal | None = Field(
        default=None,
        description="Stop‑Loss",
        validation_alias="stopLossPrice",
    )
    take_profit_price: Decimal | None = Field(
        default=None,
        description="Take‑Profit",
        validation_alias="takeProfitPrice",
    )


@pdc_dataclass(slots=True, frozen=True)
class CCXTPositionInfoResponse(PositionInfoResponse):
    """Снимок позиции ccxt с нормализацией полей источника.

    Контракт совпадает с ``PositionInfoResponse``. Дополнительно нормализуются:
    - ``id`` приводится к ``str`` при наличии;
    - при отсутствии ``timestamp`` и ``datetime`` используются значения из ``info.updateTime`` (мс, UTC);
    - допускается строковый ``datetime`` (ISO 8601), который будет разобран Pydantic.
    """

    @field_validator("contracts", mode="before")
    @classmethod
    def _contracts_none_or_empty_to_zero(cls, v: object) -> object:
        """Нормализует ``contracts``: ``None`` или пустая строка преобразуются в 0."""
        if v is None:
            return Decimal(0)
        if isinstance(v, str) and not v.strip():
            return Decimal(0)
        return v

    @model_validator(mode="before")
    @classmethod
    def _normalize_source(cls, data: object) -> object:
        """Привести входные данные к ожидаемой форме.

        Принимает словарь от ccxt: добавляет недостающие ``timestamp``/``datetime`` и
        приводит ``id`` к строке. Остальные поля валидируются базовым классом.
        """
        if not isinstance(data, dict):
            return data

        item: dict[str, Any] = dict(cast("dict[str, Any]", data))

        # Привести id к строке при наличии
        id_value = item.get("id")
        if id_value is not None and not isinstance(id_value, str):
            item["id"] = str(id_value)

        # Заполнить timestamp/datetime из info.updateTime, если оба отсутствуют
        if item.get("timestamp") is None and item.get("datetime") is None:
            info_raw = item.get("info")
            info: dict[str, Any] = cast("dict[str, Any]", info_raw) if isinstance(info_raw, dict) else {}
            update_at: Any = info.get("updateTime") or info.get("updatedTime") or info.get("uTime")
            update_at_int: int | None = None
            if isinstance(update_at, (int, float)):
                update_at_int = int(update_at)
            elif isinstance(update_at, str):
                raw = update_at.strip()
                if raw.isdigit():
                    update_at_int = int(raw)
            elif update_at is not None:
                try:
                    update_at_int = int(update_at)  # type: ignore[arg-type]
                except (ValueError, TypeError):
                    update_at_int = None

            if update_at_int is not None:
                item["timestamp"] = update_at_int
                item["datetime"] = dt.fromtimestamp(update_at_int / 1000, UTC)

        return item
