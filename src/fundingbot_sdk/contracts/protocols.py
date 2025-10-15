"""Контракты-протоколы сущностей, возвращаемых CEX-клиентами SDK.

Определяют минимально необходимый набор свойств для балансов, позиций, ордеров,
инструментов, тикеров и ставок funding. Используются адаптерами и приложением
для статической типизации и контрактного программирования.
"""

from datetime import datetime
from decimal import Decimal
from typing import Protocol, runtime_checkable


@runtime_checkable
class BalanceProtocol(Protocol):
    """Снимок баланса по монете на бирже."""

    @property
    def free(self) -> Decimal:
        """Свободный баланс (доступен к использованию)."""
        ...

    @property
    def used(self) -> Decimal:
        """Зарезервированный баланс (в ордерах и позициях)."""
        ...

    @property
    def total(self) -> Decimal:
        """Суммарный баланс: free + used."""
        ...


class PositionProtocol(Protocol):
    """Снимок открытой деривативной позиции."""

    @property
    def symbol(self) -> str:
        """Символ инструмента, например ``BTC/USDT:USDT``."""
        ...

    @property
    def collateral(self) -> Decimal:
        """Залог (маржа), выделенный под позицию."""
        ...

    @property
    def contracts(self) -> Decimal:
        """Количество контрактов в позиции."""
        ...

    @property
    def datetime(self) -> datetime:
        """Время последнего обновления позиции в ISO‑формате."""
        ...

    @property
    def entry_price(self) -> Decimal:
        """Цена входа в позицию."""
        ...

    @property
    def hedged(self) -> bool:
        """Флаг хеджированного режима (dual‑side)."""
        ...

    @property
    def id(self) -> str | None:
        """Идентификатор позиции на бирже, если присутствует."""
        ...

    @property
    def leverage(self) -> Decimal:
        """Используемое кредитное плечо."""
        ...

    @property
    def margin_mode(self) -> str | None:
        """Режим маржи позиции, если доступен: ``isolated`` или ``cross``.

        Может отсутствовать на биржах, не предоставляющих явный режим.
        """
        ...

    @property
    def liquidation_price(self) -> Decimal:
        """Цена ликвидации позиции."""
        ...

    @property
    def notional(self) -> Decimal:
        """Нотиональная стоимость позиции (в валюте котировки)."""
        ...

    @property
    def side(self) -> str:
        """Направление позиции: long или short."""
        ...

    @property
    def stop_loss_price(self) -> Decimal | None:
        """Текущий уровень Stop‑Loss, если задан."""
        ...

    @property
    def take_profit_price(self) -> Decimal | None:
        """Текущий уровень Take‑Profit, если задан."""
        ...

    @property
    def timestamp(self) -> int:
        """Метка времени последнего обновления в миллисекундах Unix."""
        ...


class OrderEntityProtocol(Protocol):
    """Снимок ордера на деривативном рынке."""

    @property
    def id(self) -> str:
        """Идентификатор ордера на бирже."""
        ...

    @property
    def client_order_id(self) -> str | None:
        """Клиентский идентификатор ордера, если использовался."""
        ...


class TriggerOrderProtocol(OrderEntityProtocol, Protocol):
    """Снимок триггерного ордера."""

    @property
    def symbol(self) -> str:
        """Символ инструмента."""
        ...

    @property
    def side(self) -> str:
        """Направление ордера."""
        ...

    @property
    def amount(self) -> Decimal:
        """Количество ордера."""
        ...

    @property
    def type(self) -> str:
        """Тип ордера."""
        ...

    @property
    def trigger_price(self) -> Decimal | None:
        """Статус ордера."""
        ...

    @property
    def stop_loss_price(self) -> Decimal | None:
        """Цена Stop‑Loss."""
        ...

    @property
    def take_profit_price(self) -> Decimal | None:
        """Цена Take‑Profit."""
        ...


class FundingProtocol(Protocol):
    """Снимок прогнозной ставки funding по инструменту."""

    @property
    def symbol(self) -> str:
        """Символ инструмента (например, ``BTC/USDT:USDT``)."""
        ...

    @property
    def exchange(self) -> str:
        """Идентификатор биржи, предоставившей данные."""
        ...

    @property
    def funding_date(self) -> datetime:
        """Момент ближайшей выплаты funding."""
        ...

    @property
    def funding_rate(self) -> Decimal:
        """Ставка funding (доля за период)."""
        ...


class InstrumentProtocol(Protocol):
    """Метаданные торгового инструмента (точности, лоты, лимиты)."""

    @property
    def contract_size(self) -> Decimal:
        """Размер контракта (для расчетов нотионала)."""
        ...

    @property
    def symbol(self) -> str:
        """Символ инструмента."""
        ...

    @property
    def amount_precision(self) -> Decimal:
        """Точность количества (минимальный шаг объёма)."""
        ...

    @property
    def price_precision(self) -> Decimal:
        """Точность цены (минимальный шаг цены)."""
        ...

    @property
    def cost_precision(self) -> Decimal | None:
        """Точность стоимости, если поддерживается биржей."""
        ...

    @property
    def min_cost(self) -> Decimal | None:
        """Минимально допустимая стоимость ордера."""
        ...

    @property
    def max_cost(self) -> Decimal | None:
        """Максимально допустимая стоимость ордера."""
        ...

    @property
    def min_amount(self) -> Decimal | None:
        """Минимальный объём ордера."""
        ...

    @property
    def max_amount(self) -> Decimal | None:
        """Максимальный объём ордера."""
        ...

    @property
    def min_price(self) -> Decimal | None:
        """Минимальная цена ордера."""
        ...

    @property
    def max_price(self) -> Decimal | None:
        """Максимальная цена ордера."""
        ...


class TickerProtocol(Protocol):
    """Снимок текущего тикера инструмента."""

    @property
    def symbol(self) -> str:
        """Символ инструмента тикера."""
        ...

    @property
    def last_price(self) -> Decimal:
        """Последняя цена сделки (last)."""
        ...
