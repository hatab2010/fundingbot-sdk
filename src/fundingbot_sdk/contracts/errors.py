"""Иерархия инфраструктурных исключений SDK.

Разделение исключений по слоям:
- В SDK/инфраструктуре описываются ошибки взаимодействия с внешними системами
  (биржи, сеть, лимитеры, БД и т.п.).
- Доменные ошибки определяются в доменном слое основного приложения и не
  импортируются здесь, чтобы не нарушать зависимость направленности.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Mapping


class ErrorCode(Enum):
    """Коды ошибок инфраструктурного уровня SDK."""

    UNKNOWN = "unknown"
    TIMEOUT = "timeout"
    NETWORK = "network"
    RATE_LIMIT = "rate_limit"
    EXCHANGE_ERROR = "exchange_error"
    VALIDATION = "validation"
    INSTRUMENT_UNAVAILABLE = "instrument_unavailable"
    TICKER_UNAVAILABLE = "ticker_unavailable"
    POSITION_UNAVAILABLE = "position_unavailable"
    FUNDING_RATE_UNAVAILABLE = "funding_rate_unavailable"
    UNSUPPORTED_FEATURE = "unsupported_feature"
    TRIGGER_ORDERS_UNAVAILABLE = "trigger_orders_unavailable"
    ORDER_UNAVAILABLE = "order_unavailable"
    BALANCE_UNAVAILABLE = "balance_unavailable"


@dataclass(slots=True, kw_only=True)
class SdkError(Exception):
    """Базовая ошибка инфраструктурного слоя SDK.

    Атрибуты
    ---------
    error_code: ErrorCode
        Машиночитаемый код класса ошибки для унификации обработки.
    retryable: bool
        Признак возможности безопасного повтора операции.
    """

    error_code: ErrorCode = ErrorCode.UNKNOWN
    retryable: bool = False


@dataclass(slots=True)
class ExchangeClientError(SdkError):
    """Ошибки клиента биржи (ccxt/HTTP и пр.).

    exchange: идентификатор биржи, symbol: торговый символ, method: имя метода SDK.
    Значения полей могут быть не заданы, если контекст недоступен.
    """

    exchange: str | None = None
    symbol: str | None = None
    method: str | None = None


@dataclass(slots=True)
class RetryableExchangeError(ExchangeClientError):
    """Временная (транзиентная) ошибка, попытку можно повторить позднее."""

    retryable: bool = True


@dataclass(slots=True)
class PermanentExchangeError(ExchangeClientError):
    """Постоянная ошибка, повтор не имеет смысла без изменения условий."""


@dataclass(slots=True)
class UnknownExchangeError(ExchangeClientError):
    """Неопознанная ошибка внешней библиотеки/сети."""

    def __post_init__(self) -> None:
        """Установить код ошибки по умолчанию для неизвестной ошибки."""
        self.error_code = ErrorCode.UNKNOWN


@dataclass(slots=True)
class RateLimiterError(SdkError):
    """Ошибки, связанные с внешним rate-limiter'ом."""


@dataclass(slots=True)
class RateLimiterNotConfiguredError(RateLimiterError):
    """Клиент вызван без установленного rate-limiter'а там, где он обязателен."""


@dataclass(slots=True)
class TickerUnavailableError(ExchangeClientError):
    """Текущий тикер не получен или неполон для указанного символа."""

    def __post_init__(self) -> None:
        """Установить код ошибки для отсутствующего тикера."""
        self.error_code = ErrorCode.TICKER_UNAVAILABLE

    def __str__(self) -> str:
        """Вернуть человекочитаемое представление ошибки."""
        return f"Не удалось получить тикер для символа {self.symbol}, биржа {self.exchange}"


@dataclass(slots=True)
class FundingRateUnavailableError(RetryableExchangeError):
    """Отсутствуют корректные данные о ставке финансирования по инструменту."""

    def __post_init__(self) -> None:
        """Установить код ошибки для отсутствующей ставки финансирования."""
        self.error_code = ErrorCode.FUNDING_RATE_UNAVAILABLE

    def __str__(self) -> str:
        """Вернуть человекочитаемое представление ошибки."""
        return f"Нет ставки funding для {self.symbol} на {self.exchange}"


@dataclass(slots=True)
class PositionUnavailableError(RetryableExchangeError):
    """Отсутствуют корректные данные о позиции по инструменту."""

    def __post_init__(self) -> None:
        """Установить код ошибки для отсутствующей позиции."""
        self.error_code = ErrorCode.POSITION_UNAVAILABLE

    def __str__(self) -> str:
        """Вернуть человекочитаемое представление ошибки."""
        return f"Нет позиции для {self.symbol} на {self.exchange}"


@dataclass(slots=True)
class InstrumentUnavailableError(RetryableExchangeError):
    """Отсутствуют корректные данные о инструменте."""

    def __post_init__(self) -> None:
        """Установить код ошибки для отсутствующего инструмента."""
        self.error_code = ErrorCode.INSTRUMENT_UNAVAILABLE

    def __str__(self) -> str:
        """Вернуть человекочитаемое представление ошибки."""
        return f"Нет инструмента для {self.symbol} на {self.exchange}"


@dataclass(slots=True)
class TriggerOrdersUnavailableError(RetryableExchangeError):
    """Отсутствуют корректные данные о триггер‑ордерах по инструменту."""

    def __post_init__(self) -> None:
        """Установить код ошибки для отсутствующих триггер‑ордеров."""
        self.error_code = ErrorCode.TRIGGER_ORDERS_UNAVAILABLE

    def __str__(self) -> str:
        """Вернуть человекочитаемое представление ошибки."""
        return f"Нет данных по триггер‑ордерам для {self.symbol} на {self.exchange}"


@dataclass(slots=True)
class BalanceUnavailableError(RetryableExchangeError):
    """Отсутствуют корректные данные о балансе по монете."""

    def __post_init__(self) -> None:
        """Установить код ошибки для отсутствующего баланса."""
        self.error_code = ErrorCode.BALANCE_UNAVAILABLE

    def __str__(self) -> str:
        """Вернуть человекочитаемое представление ошибки."""
        return f"Нет баланса для {self.symbol} на {self.exchange}"


@dataclass(slots=True)
class UnsupportedFeatureError(SdkError):
    """Функция не поддерживается биржей."""

    cex_id: str
    method: str
    params: Mapping[str, Any]

    def __post_init__(self) -> None:
        """Зафиксировать параметры и установить код ошибки."""
        # Защитная копия и запрет мутаций переданных параметров
        self.params = MappingProxyType(dict(self.params))
        self.error_code = ErrorCode.UNSUPPORTED_FEATURE

    def __str__(self) -> str:
        """Вернуть человекочитаемое представление ошибки."""
        return f"Функция {self.method} не поддерживается биржей {self.cex_id} для параметров {self.params}"


@dataclass(slots=True)
class OrderUnavailableError(ExchangeClientError):
    """Отсутствуют корректные данные о созданном ордере."""

    def __post_init__(self) -> None:
        """Установить код ошибки для отсутствующих данных ордера."""
        self.error_code = ErrorCode.ORDER_UNAVAILABLE

    def __str__(self) -> str:
        """Вернуть человекочитаемое представление ошибки."""
        return f"Нет данных по ордеру для {self.symbol} на {self.exchange}"
