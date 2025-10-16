"""Базовые утилиты и реализация клиента CEX на основе ccxt.

Содержит декоратор для весового rate‑лимита, контекстный менеджер пометки
предварительного захвата квоты, а также реализацию ``CcxtClient``
как адаптера под абстракцию ``CexClientPort``.
"""

from __future__ import annotations

import contextvars
import logging
import re
import types
from collections.abc import Awaitable, Callable, Sequence
from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime
from decimal import Decimal
from functools import wraps
from typing import TYPE_CHECKING, Any, TypeVar, cast, final, override

import ccxt.async_support as ccxt
from pydantic import TypeAdapter, ValidationError

from fundingbot_sdk.contracts.errors import (
    BalanceUnavailableError,
    FundingRateUnavailableError,
    InstrumentUnavailableError,
    OrderUnavailableError,
    PositionUnavailableError,
    RateLimiterNotConfiguredError,
    TickerUnavailableError,
    TriggerOrdersUnavailableError,
    UnsupportedFeatureError,
)
from fundingbot_sdk.contracts.ports.cex_client import CexClientPort
from fundingbot_sdk.contracts.protocols import TriggerOrderProtocol
from fundingbot_sdk.schemas.balance import BalanceResponse
from fundingbot_sdk.schemas.funding import FundingRateResponse
from fundingbot_sdk.schemas.market import MarketResponse
from fundingbot_sdk.schemas.order import CreateOrderResponse, TriggerOrderResponse
from fundingbot_sdk.schemas.position_info import CCXTPositionInfoResponse
from fundingbot_sdk.schemas.ticker import TickerResponse
from fundingbot_sdk.toolkit.error_mapper import map_sdk_errors

TICKER_RESPONSE_ADAPTER = TypeAdapter(TickerResponse)
CCXT_POSITION_INFO_ADAPTER = TypeAdapter(CCXTPositionInfoResponse)
MARKET_RESPONSE_ADAPTER = TypeAdapter(MarketResponse)
TRIGGER_ORDER_LIST_ADAPTER = TypeAdapter(list[TriggerOrderResponse])
FUNDING_RATE_RESPONSE_ADAPTER = TypeAdapter(FundingRateResponse)
CREATE_ORDER_RESPONSE_ADAPTER = TypeAdapter(CreateOrderResponse)
BALANCE_RESPONSE_ADAPTER = TypeAdapter(BalanceResponse)


if TYPE_CHECKING:
    from fundingbot_sdk.contracts.ports.cex_client import CexClientConfig
    from fundingbot_sdk.contracts.ports.rate_limiter import RateLimiterPort, RateLimitPermitProtocol
    from fundingbot_sdk.contracts.protocols import (
        BalanceProtocol,
        FundingProtocol,
        InstrumentProtocol,
        OrderEntityProtocol,
        PositionProtocol,
        TickerProtocol,
    )

F = TypeVar("F", bound=Callable[..., object])

logger = logging.getLogger(__name__)
_current_weight: contextvars.ContextVar[int | None] = contextvars.ContextVar("_current_weight", default=None)
_preacquired: contextvars.ContextVar[bool] = contextvars.ContextVar("_preacquired", default=False)


def rate_limited(weight: int = 1) -> Callable[[F], F]:
    """Сохраняет вес операции и передаёт его в ccxt.request().

    Сохраняет вес в __rl_weight__ (для Barrier'а); во время вызова кладёт его
    в contextvar _current_weight, чтобы его увидел ccxt.request().
    """

    def deco(fn: F) -> F:
        fn.__rl_weight__ = weight  # type: ignore[attr-defined]  # ① читается Barrier'ом

        @wraps(fn)
        async def wrapper(*args: object, **kwargs: object) -> object:
            token = _current_weight.set(weight)  # ② увидит request()
            try:
                return await cast("Any", fn)(*args, **kwargs)  # type: ignore[reportUnknownMemberType]
            finally:
                _current_weight.reset(token)

        return cast("F", wrapper)

    return deco


class MarkPreacquired(AbstractAsyncContextManager[None]):
    """Контекстная пометка, что квота rate‑лимитера уже захвачена внешним кодом.

    Используйте этот контекст, если квота была получена заранее через внешний
    барьер/лимитер и повторный захват внутри клиента не требуется.
    """

    async def __aenter__(self) -> None:
        """Отметить текущее выполнение как «предзахваченное» для лимитера."""
        self._token = _preacquired.set(True)

    async def __aexit__(
        self, exc_t: type[BaseException] | None, exc: BaseException | None, tb: types.TracebackType | None
    ) -> None:
        """Снять отметку предзахвата при выходе из контекста."""
        _preacquired.reset(self._token)


def get_weight() -> int | None:
    """Вернуть текущий вес операции из контекстной переменной."""
    return _current_weight.get()


def is_preacquired() -> bool:
    """Проверить, помечена ли текущая операция как предварительно захваченная."""
    return _preacquired.get()


class CcxtClient(CexClientPort):
    """Реализация ``CexClientPort`` на базе ``ccxt.async_support``.

    Обеспечивает вызовы к биржам через ccxt и прозрачно интегрирует внешний
    асинхронный rate‑лимитер для учёта веса запросов.
    """

    def __init__(self, exchange_name: str, config: CexClientConfig, *, verbose: bool = False) -> None:
        """Инициализировать клиента ccxt.

        Параметры
        ----------
        exchange_name: str
            Имя класса биржи из ccxt (например, ``bybit``, ``okx``).
        config: CexClientConfig
            Конфигурация клиента (ключи, тестнет, опции, rate‑лимитер).
        verbose: bool
            Включить подробный лог ccxt.
        """
        super().__init__(exchange_name, config)
        self._default_type = config.default_type
        self._exchange_name = exchange_name
        self._rate_limiter: RateLimiterPort | None = config.rate_limiter

        exchange_class = getattr(ccxt, exchange_name)
        # ccxt не полностью типизирован; используем Any, чтобы не протекали Unknown-типы
        self._exchange: Any = exchange_class({
            "apiKey": config.api_key,
            "secret": config.api_secret,
            "password": config.password,
            "verbose": verbose,
            "enableRateLimit": False,
            "uid": config.uid,
            "options": {"defaultType": config.default_type},
        })
        if config.testnet:
            self._exchange.set_sandbox_mode(True)
        self._patch_request()

    @final
    @override
    async def acquire_permit(self, op: Callable[..., Awaitable[Any]]) -> RateLimitPermitProtocol:
        fn = op.__func__ if hasattr(op, "__func__") else op  # type: ignore[reportUnknownMemberType]
        weight: int = getattr(fn, "__rl_weight__", 1)
        if self._rate_limiter is None:
            raise RateLimiterNotConfiguredError
        return await self._rate_limiter.acquire(weight)

    async def load_markets(self, *, reload: bool = False, params: dict[str, Any] | None = None) -> None:
        """Загрузить справочник рынков ccxt, при необходимости обновив кэш."""
        await self._exchange.load_markets(reload=reload, params=params or {})

    @property
    def cex_id(self) -> str:
        """Вернуть идентификатор (имя) биржи, используемый в ccxt."""
        return self._exchange_name

    @override
    @map_sdk_errors
    async def get_market_symbols(self) -> list[str]:
        await self.load_markets()
        return [m["symbol"] for m in self._exchange.markets.values() if m.get("type") == self._default_type]

    @override
    @map_sdk_errors
    async def get_ticker(self, symbol: str) -> TickerProtocol:
        data = await self._exchange.fetch_ticker(symbol)
        try:
            dto = TICKER_RESPONSE_ADAPTER.validate_python(data)
        except ValidationError as e:
            raise TickerUnavailableError(symbol=symbol, exchange=self.cex_id) from e
        return dto

    @override
    @map_sdk_errors
    async def get_positions(
        self,
        symbols: list[str],
        params: dict[str, Any] | None = None
    ) ->  Sequence[PositionProtocol]:
        data = await self._exchange.fetch_positions(symbols=symbols, params=params or {})
        filtered: list[CCXTPositionInfoResponse] = []
        for item in data:
            try:
                position = CCXT_POSITION_INFO_ADAPTER.validate_python(item)
            except ValidationError as e:
                raise PositionUnavailableError(symbol=item.get("symbol"), exchange=self.cex_id) from e

            if position.contracts == 0:  # Некоторые биржи возвращают нулевые позиции, поэтому их нужно фильтровать.
                continue
            filtered.append(position)

        return filtered

    @override
    @map_sdk_errors
    async def close_trigger_orders(self, symbol: str, ids: list[str], params: dict[str, Any] | None = None) -> None:
        params_ = dict(params or {})
        params_["stop"] = True
        await self._exchange.cancel_orders(symbol=symbol, ids=ids, params=params_)

    @override
    @map_sdk_errors
    async def get_instrument_info(self, symbol: str) -> InstrumentProtocol:
        await self.load_markets()
        data = self._exchange.markets.get(symbol)
        if data is None:
            raise InstrumentUnavailableError(symbol=symbol, exchange=self.cex_id)
        dto_dict = {**data, "symbol": symbol}
        try:
            dto = MARKET_RESPONSE_ADAPTER.validate_python(dto_dict)
        except ValidationError as e:
            raise InstrumentUnavailableError(symbol=symbol, exchange=self.cex_id) from e

        return dto

    @override
    @map_sdk_errors
    async def get_trigger_orders(self, symbol: str) -> Sequence[TriggerOrderProtocol]:
        tpsl_orders = await self._exchange.fetch_open_orders(symbol=symbol, params={"planType": "profit_loss"})
        try:
            return TRIGGER_ORDER_LIST_ADAPTER.validate_python(tpsl_orders)
        except ValidationError as e:
            raise TriggerOrdersUnavailableError(symbol=symbol, exchange=self.cex_id) from e

    @override
    @map_sdk_errors
    async def get_funding_rate(self, symbol: str) -> FundingProtocol:
        await self.load_markets()
        data = await self._exchange.fetch_funding_rate(symbol)
        try:
            dto = FUNDING_RATE_RESPONSE_ADAPTER.validate_python(data)
        except ValidationError as e:
            raise FundingRateUnavailableError(symbol=symbol, exchange=self.cex_id) from e

        return dto

    @override
    @map_sdk_errors
    @rate_limited(weight=10)
    async def get_funding_usdt_rates(self, *, is_active: bool = True) -> Sequence[FundingProtocol]:
        await self._exchange.load_markets()

        # Фильтр доступных своп‑инструментов (:USDT) по состоянию рынка.
        active_symbols: set[str] | None = None
        if is_active:
            active_symbols = {
                m.get("symbol")
                for m in self._exchange.markets.values()
                if (m.get("swap") is True) and m.get("symbol").endswith(":USDT") and (m.get("active") is True)
            }

        data = await self._exchange.fetch_funding_rates()
        now = datetime.now(UTC)
        result: list[FundingRateResponse] = []

        for symbol, raw in data.items():
            if not re.match(r"^\w+\/USDT(?:\:USDT)?$", symbol):
                continue

            payload = {**raw, "symbol": symbol, "exchange": self.cex_id}
            try:
                dto = FUNDING_RATE_RESPONSE_ADAPTER.validate_python(payload)
            except ValidationError as e:
                raise FundingRateUnavailableError(symbol=symbol, exchange=self.cex_id) from e

            if dto.funding_date < now:
                continue

            if active_symbols is not None and dto.symbol not in active_symbols:
                continue
            result.append(dto)

        if not result:
            # Нет актуальных ставок по рынкам USDT
            raise FundingRateUnavailableError(symbol="*/USDT", exchange=self.cex_id)

        return result

    @override
    @map_sdk_errors
    async def set_position_mode(
        self, *, hedged: bool, symbol: str | None = None, params: dict[str, Any] | None = None
    ) -> None:
        await self._exchange.set_position_mode(hedged, symbol, params or {})

    @override
    @map_sdk_errors
    async def set_margin_mode(
        self, *, margin_mode: str, symbol: str | None = None, params: dict[str, Any] | None = None
    ) -> None:
        await self._exchange.set_margin_mode(margin_mode, symbol, params or {})

    @override
    @map_sdk_errors
    async def set_leverage(
        self, *, leverage: int, symbol: str | None = None, params: dict[str, Any] | None = None
    ) -> None:
        await self._exchange.set_leverage(leverage, symbol, params or {})

    @override
    @map_sdk_errors
    async def create_tpsl_position(
        self,
        *,
        symbol: str,
        side: str,
        order_type: str,
        amount: Decimal,
        take_profit: Decimal,
        stop_loss: Decimal,
        margin_mode: str = "isolated",
    ) -> OrderEntityProtocol:
        data = await self._exchange.create_order(
            symbol=symbol,
            side=side,
            type=order_type,
            amount=amount,
            params={
                "takeProfit": {"triggerPrice": take_profit},
                "stopLoss": {"triggerPrice": stop_loss},
                "marginMode": margin_mode,
            },
        )
        try:
            return CREATE_ORDER_RESPONSE_ADAPTER.validate_python(data)
        except ValidationError as e:
            raise OrderUnavailableError(symbol=symbol, exchange=self.cex_id) from e

    @override
    @map_sdk_errors
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
        params = dict(params or {})
        params["marginMode"] = margin_mode
        data = await self._exchange.create_order(
            symbol=symbol, type=order_type, side=side, amount=amount, price=price, params=params
        )
        try:
            return CREATE_ORDER_RESPONSE_ADAPTER.validate_python(data)
        except ValidationError as e:
            raise OrderUnavailableError(symbol=symbol, exchange=self.cex_id) from e

    @override
    def price_to_precision(self, symbol: str, price: Decimal) -> Decimal:
        # ccxt может возвращать str/float; приводим к Decimal с сохранением точности
        value = self._exchange.price_to_precision(symbol=symbol, price=price)
        return Decimal(str(value))

    @override
    @map_sdk_errors
    async def get_balance(self, coin: str) -> BalanceProtocol:
        data = await self._exchange.fetch_balance()
        s_balance = data.get(coin, None)
        if s_balance is None:
            return BalanceResponse(free=Decimal(0), used=Decimal(0), total=Decimal(0))
        try:
            return BALANCE_RESPONSE_ADAPTER.validate_python(s_balance)
        except ValidationError as e:
            raise BalanceUnavailableError(symbol=coin, exchange=self.cex_id) from e

    @override
    async def set_take_profit(
        self, symbol: str, side: str, amount: Decimal, take_profit_price: Decimal
    ) -> OrderEntityProtocol:
        raise UnsupportedFeatureError(cex_id=self.cex_id, method="set_take_profit", params={
            "symbol": symbol,
            "side": side,
            "amount": amount,
            "take_profit_price": take_profit_price,
        })

    @override
    async def set_stop_loss(
        self, symbol: str, side: str, amount: Decimal, stop_price: Decimal
    ) -> OrderEntityProtocol:
        raise UnsupportedFeatureError(cex_id=self.cex_id, method="set_stop_loss", params={
            "symbol": symbol,
            "side": side,
            "amount": amount,
            "stop_price": stop_price,
        })

    @final
    @override
    async def close(self) -> None:
        # Базовый метод ccxt – закрывает транспорт/коннектор.
        await self._exchange.close()

        # У некоторых реализаций (aiohttp backend) есть открытая session.
        session = getattr(self._exchange, "session", None)
        if session is not None and not session.closed:
            try:
                await session.close()
            except Exception as exc:  # noqa: BLE001 – лишь логируем
                logger.warning("Не удалось корректно закрыть aiohttp session %s: %s", session, exc)

        if self._rate_limiter is not None:
            try:
                await self._rate_limiter.close()
            except Exception as exc:  # noqa: BLE001 – лишь логируем
                logger.warning("Не удалось закрыть rate_limiter %s: %s", self._rate_limiter, exc)

    @final
    def _patch_request(self) -> None:
        if not hasattr(self, "_origin_request"):
            self._origin_request = self._exchange.request

        orig_request = self._origin_request
        limiter = self._rate_limiter

        async def patched_request(
            _self: object,
            path: str,
            api: str = "public",
            method: str = "GET",
            params: dict[str, object] | None = None,
            headers: dict[str, object] | None = None,
            body: dict[str, object] | None = None,
            **kwargs: object,
        ) -> object:
            if is_preacquired():  # квота уже взята
                return await orig_request(
                    path, api=api, method=method, params=params, headers=headers, body=body, **kwargs
                )

            if limiter is None:
                return await orig_request(
                    path, api=api, method=method, params=params, headers=headers, body=body, **kwargs
                )

            weight = get_weight() or 1  # вес из декоратора
            async with await limiter.acquire(weight):
                return await orig_request(
                    path, api=api, method=method, params=params, headers=headers, body=body, **kwargs
                )

        # привязываем к экземпляру
        self._exchange.request = types.MethodType(patched_request, self._exchange)
