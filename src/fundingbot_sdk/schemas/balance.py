from decimal import Decimal

from pydantic import Field
from pydantic.dataclasses import dataclass as pdc_dataclass

from fundingbot_sdk.schemas.base import ResponseBase


@pdc_dataclass(frozen=True, slots=True)
class BalanceResponse(ResponseBase):
    """Датакласс баланса монеты на бирже."""

    free: Decimal = Field(..., description="Free balance", validation_alias="free")
    used: Decimal = Field(..., description="Used balance", validation_alias="used")
    total: Decimal = Field(..., description="Total balance", validation_alias="total")
