"""Централизованный маппер внешних исключений в ошибки SDK.

Назначение: унифицировать семантику повтора/неповтора запросов и коды ошибок.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
from dataclasses import dataclass
from functools import wraps
from threading import RLock
from typing import TYPE_CHECKING, Any, Concatenate, ParamSpec, TypeVar, overload

from fundingbot_sdk.contracts.ports.cex_client import CexIdentifiable

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
    from types import CoroutineType

import ccxt
import httpx
from pydantic import ValidationError

from fundingbot_sdk.contracts.errors import (
    ErrorCode,
    ExchangeClientError,
    PermanentExchangeError,
    RetryableExchangeError,
    SdkError,
    UnknownExchangeError,
)

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ErrorContext:
    """Контекст метода SDK для обогащения ошибок."""

    exchange: str | None = None
    symbol: str | None = None
    method: str | None = None


class ErrorMapper:
    """Маппер внешних ошибок в иерархию SDK.

    Предусмотрена регистрация дополнительных правил через register().
    """

    def __init__(self) -> None:
        """Создать экземпляр маппера ошибок."""
        self._rules: list[Callable[[BaseException, ErrorContext], SdkError | None]] = []
        self._rule_ids: set[tuple[str, str]] = set()
        self._lock = RLock()

    def register(self, rule: Callable[[BaseException, ErrorContext], SdkError | None]) -> None:
        """Регистрирует пользовательское правило маппинга."""
        rule_id = self._rule_id(rule)

        with self._lock:
            if rule_id in self._rule_ids:
                return
            self._rules.append(rule)
            self._rule_ids.add(rule_id)

    def translate(self, exc: BaseException, ctx: ErrorContext) -> SdkError:
        """Преобразовать исключение внешней библиотеки в SdkError."""
        # Пользовательские правила первыми
        with self._lock:
            rules_snapshot = tuple(self._rules)

        for rule in rules_snapshot:
            mapped = rule(exc, ctx)
            if mapped is not None:
                return self._enrich(mapped, ctx)

        # Базовые правила по умолчанию
        mapped: SdkError | None = None
        if isinstance(exc, (httpx.ConnectError, httpx.ReadError, httpx.NetworkError, httpx.RemoteProtocolError)):
            mapped = RetryableExchangeError(error_code=ErrorCode.NETWORK)
        elif isinstance(exc, (httpx.TimeoutException, asyncio.TimeoutError)):
            mapped = RetryableExchangeError(error_code=ErrorCode.TIMEOUT)
        elif isinstance(exc, (ccxt.RateLimitExceeded, ccxt.NetworkError)):
            mapped = RetryableExchangeError(error_code=ErrorCode.RATE_LIMIT)
        elif isinstance(exc, (ccxt.ExchangeError,)):
            mapped = PermanentExchangeError(error_code=ErrorCode.EXCHANGE_ERROR)
        elif isinstance(exc, ValidationError):
            mapped = PermanentExchangeError(error_code=ErrorCode.VALIDATION)
        else:
            mapped = UnknownExchangeError()

        return self._enrich(mapped, ctx)

    @staticmethod
    def _enrich(err: SdkError, ctx: ErrorContext) -> SdkError:
        if isinstance(err, ExchangeClientError):
            err.exchange = ctx.exchange
            err.symbol = ctx.symbol
            err.method = ctx.method
        return err

    @staticmethod
    def _rule_id(rule: Callable[[BaseException, ErrorContext], SdkError | None]) -> tuple[str, str]:
        module = getattr(rule, "__module__", "")
        qualname = getattr(rule, "__qualname__", getattr(rule, "__name__", ""))
        return module, qualname


default_error_mapper = ErrorMapper()

# Тип-параметр исходной функции; декоратор сохраняет его без изменений
P = ParamSpec("P")
R = TypeVar("R")


def _wrap_sync[**P, R](fn: Callable[P, R]) -> Callable[P, R]:
    sig = inspect.signature(fn)
    method_name = getattr(fn, "__name__", "unknown")

    @wraps(fn)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        self_obj = args[0] if args else None
        exchange = getattr(self_obj, "cex_id", None)
        bound = sig.bind_partial(*args, **kwargs)
        bound.apply_defaults()
        symbol = bound.arguments.get("symbol", None)
        try:
            return fn(*args, **kwargs)
        except SdkError:
            raise
        except Exception as exc:
            ctx = ErrorContext(exchange=exchange, symbol=symbol, method=method_name)
            logger.exception("Исключение на границе SDK: %s.%s", exchange, method_name)
            raise default_error_mapper.translate(exc, ctx) from exc

    return wrapper


def _wrap_async[**P, R](fn: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
    sig = inspect.signature(fn)
    method_name = getattr(fn, "__name__", "unknown")

    @wraps(fn)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        self_obj = args[0] if args else None
        exchange = getattr(self_obj, "cex_id", None)
        bound = sig.bind_partial(*args, **kwargs)
        bound.apply_defaults()
        symbol = bound.arguments.get("symbol", None)
        try:
            return await fn(*args, **kwargs)
        except SdkError:
            raise
        except Exception as exc:
            ctx = ErrorContext(exchange=exchange, symbol=symbol, method=method_name)
            logger.exception("Исключение на границе SDK: %s.%s", exchange, method_name)
            t_ecx = default_error_mapper.translate(exc, ctx)
            raise t_ecx from exc

    return wrapper


@overload
def map_sdk_errors[**P, R, T: CexIdentifiable](
    fn: Callable[Concatenate[T, P], Awaitable[R]],
) -> Callable[Concatenate[T, P], CoroutineType[Any, Any, R]]: ...
@overload
def map_sdk_errors[**P, R, T: CexIdentifiable](
    fn: Callable[Concatenate[T, P], R],
) -> Callable[Concatenate[T, P], R]: ...


def map_sdk_errors[**P, R, T: CexIdentifiable](
    fn: Callable[Concatenate[T, P], R] | Callable[Concatenate[T, P], Awaitable[R]],
):
    """Декоратор границы SDK.

    Сохраняет тип функции (включая async/sync форму) и добавляет маппинг ошибок.
    """
    if inspect.iscoroutinefunction(fn):
        return _wrap_async(fn)
    return _wrap_sync(fn)
