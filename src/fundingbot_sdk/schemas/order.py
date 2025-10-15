from decimal import Decimal

from pydantic import Field
from pydantic.dataclasses import dataclass as pdc_dataclass

from fundingbot_sdk.schemas.base import ResponseBase


@pdc_dataclass(slots=True, frozen=True)
class OrderEntityResponse(ResponseBase):
    """Снимок ордера биржи для сериализации и контрактов SDK."""

    id: str = Field(..., description="Идентификатор ордера", validation_alias="id")
    symbol: str = Field(..., description="Символ инструмента", validation_alias="symbol")


@pdc_dataclass(slots=True, frozen=True, kw_only=True)
class CreateOrderResponse(OrderEntityResponse):
    """Снимок ордера биржи для сериализации и контрактов SDK."""

    client_order_id: str | None = Field(default=None, description="Client‑order‑id", validation_alias="clientOrderId")


@pdc_dataclass(slots=True, frozen=True)
class TriggerOrderResponse(CreateOrderResponse):
    """Снимок триггер-ордера биржи для сериализации и контрактов SDK."""

    type: str = Field(..., description="Тип ордера", validation_alias="type")
    side: str = Field(..., description="Направление ордера", validation_alias="side")
    amount: Decimal = Field(..., description="Количество ордера", validation_alias="amount")
    trigger_price: Decimal | None = Field(default=None, description="Цена срабатывания", validation_alias="triggerPrice")
    stop_loss_price: Decimal | None = Field(default=None, description="Цена Stop‑Loss", validation_alias="stopLossPrice")
    take_profit_price: Decimal | None = Field(default=None, description="Цена Take‑Profit", validation_alias="takeProfitPrice")
