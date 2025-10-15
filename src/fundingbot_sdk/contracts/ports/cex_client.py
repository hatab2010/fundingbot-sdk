"""Порты клиента централизованных бирж (CEX) для FundingBot.

Определяет абстракции конфигурации и интерфейс клиента, который реализуют
адаптеры инфраструктуры. Реализации должны обеспечивать загрузку рынков,
чтение тикеров и позиций, операции с ордерами и управление режимами
торговли и маржи, а также поддерживать внешний rate-limiter.
"""

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Concatenate, ParamSpec, TypeVar

from fundingbot_sdk.contracts.ports.rate_limiter import RateLimiterPort, RateLimitPermitProtocol
from fundingbot_sdk.contracts.protocols import (
    BalanceProtocol,
    FundingProtocol,
    InstrumentProtocol,
    OrderEntityProtocol,
    PositionProtocol,
    TickerProtocol,
    TriggerOrderProtocol,
)


@dataclass
class CexClientConfig:
    """Конфигурация клиента централизованной биржи (CEX).

    Содержит ключи API, параметры тестовой среды и дополнительные опции,
    такие как режим по умолчанию и внешний rate‑лимитер.
    """

    api_key: str | None = None
    api_secret: str | None = None
    testnet: bool = False
    password: str | None = None
    uid: str | None = None
    default_type: str = "swap"
    rate_limiter: RateLimiterPort | None = None
    options: dict[str, Any] | None = None


P = ParamSpec("P")
SelfT = TypeVar("SelfT", bound="CexClientPort")
RateLimitedMethod = Callable[Concatenate[SelfT, P], Awaitable[Any]]


class CexIdentifiable(ABC):
    """Интерфейс для получения строкового идентификатора биржи."""

    @property
    @abstractmethod
    def cex_id(self) -> str:
        """Возвращает строковый идентификатор биржи."""
        ...


class CexClientPort(CexIdentifiable, ABC):
    """Порт клиента CEX, определяющий набор операций для взаимодействия с биржей.

    Реализации обеспечивают доступ к рынкам, тикерам, позициям,
    инструментам и операциям по управлению позициями и ордерами,
    а также интеграцию с внешним rate‑лимитером.
    """

    def __init__(self, exchange_name: str, config: CexClientConfig) -> None:
        """Инициализировать клиента.

        Параметры
        ----------
        exchange_name: str
            Идентификатор/название биржи (соответствует реализации в адаптере).
        config: CexClientConfig
            Конфигурация подключения и параметров клиента.
        """
        self.exchange_name = exchange_name
        self.config = config

    @property
    @abstractmethod
    def cex_id(self) -> str:
        """Возвращает строковый идентификатор биржи (для логирования и метрик)."""
        ...

    @abstractmethod
    async def acquire_permit(self, op: Callable[..., Awaitable[Any]]) -> RateLimitPermitProtocol:
        """Получить разрешение у rate‑лимитера с учётом веса операции ``op``."""
        ...

    @abstractmethod
    async def load_markets(self) -> None:
        """Загрузить и кешировать справочник рынков у биржи."""
        ...

    @abstractmethod
    def price_to_precision(self, symbol: str, price: Decimal) -> Decimal:
        """Округлить цену ``price`` по требованиям точности инструмента ``symbol``."""
        ...

    @abstractmethod
    async def get_market_symbols(self) -> Sequence[str]:
        """Вернуть список доступных символов для текущего типа рынка."""
        ...

    @abstractmethod
    async def get_ticker(self, symbol: str) -> TickerProtocol:
        """Получить текущий тикер для инструмента ``symbol``."""
        ...

    @abstractmethod
    async def get_positions(self, symbols: list[str], params: dict[str, Any] | None = None) -> Sequence[PositionProtocol]:
        """Получить открытые позиции по списку ``symbols`` с учётом ``params``."""
        ...

    @abstractmethod
    async def get_funding_usdt_rates(self, *, is_active: bool = True) -> Sequence[FundingProtocol]:
        """Вернуть прогнозные ставки funding для USDT‑пар на бирже."""
        ...

    @abstractmethod
    async def create_tpsl_position(
        self, *, symbol: str, side: str, order_type: str, amount: Decimal, take_profit: Decimal, stop_loss: Decimal
    ) -> OrderEntityProtocol:
        """Создать позицию с заданными уровнями Take-Profit и Stop-Loss."""
        ...

    @abstractmethod
    async def get_trigger_orders(self, symbol: str) -> Sequence[TriggerOrderProtocol]:
        """Получить список отложенных (триггерных) ордеров по ``symbol``."""
        ...

    @abstractmethod
    async def close_trigger_orders(self, symbol: str, ids: list[str], params: dict[str, Any] | None = None) -> None:
        """Отменить отложенные (триггерные) ордера по ``symbol`` с указанными ``ids``."""
        ...

    @abstractmethod
    async def get_instrument_info(self, symbol: str) -> InstrumentProtocol:
        """Получить метаданные инструмента (точности, лоты, ограничения) для ``symbol``."""
        ...

    @abstractmethod
    async def get_funding_rate(self, symbol: str) -> FundingProtocol:
        """Получить ближайшую ставку funding для инструмента ``symbol``."""
        ...

    @abstractmethod
    async def set_take_profit(
        self, symbol: str, side: str, amount: Decimal, take_profit_price: Decimal
    ) -> OrderEntityProtocol:
        """Установить Take‑Profit для позиции по ``symbol``."""
        ...

    @abstractmethod
    async def set_stop_loss(self, symbol: str, side: str, amount: Decimal, stop_price: Decimal) -> OrderEntityProtocol:
        """Установить Stop‑Loss для позиции по ``symbol``."""
        ...

    @abstractmethod
    async def set_position_mode(
        self, *, hedged: bool, symbol: str | None = None, params: dict[str, Any] | None = None
    ) -> None:
        """Переключить режим позиций (хеджированный/односторонний)."""
        ...

    @abstractmethod
    async def set_margin_mode(
        self, *, margin_mode: str, symbol: str | None = None, params: dict[str, Any] | None = None
    ) -> None:
        """Установить режим маржи (например, isolated/cross)."""
        ...

    @abstractmethod
    async def set_leverage(
        self, *, leverage: int, symbol: str | None = None, params: dict[str, Any] | None = None
    ) -> None:
        """Установить кредитное плечо для инструмента или всего аккаунта."""
        ...

    @abstractmethod
    async def create_order(
        self,
        symbol: str,
        order_type: str,
        side: str,
        amount: Decimal,
        price: Decimal | None = None,
        params: dict[str, Any] | None = None,
        margin_mode: str = "isolated",
    ) -> OrderEntityProtocol:
        """Создать ордер с указанными параметрами."""
        ...

    @abstractmethod
    async def get_balance(self, coin: str) -> BalanceProtocol:
        """Получить баланс по указанной валюте ``coin``."""
        ...

    @abstractmethod
    async def close(self) -> None:
        """Закрыть сетевые ресурсы клиента и освободить связанные объекты."""
        ...
