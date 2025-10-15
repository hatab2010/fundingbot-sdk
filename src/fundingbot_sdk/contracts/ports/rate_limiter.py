from abc import ABC, abstractmethod
from contextlib import AbstractAsyncContextManager
from typing import Protocol


class RateLimitPermitProtocol(AbstractAsyncContextManager[None], Protocol):
    """Контекст, который освободит квоту при выходе."""


class RateLimiterPort(ABC):
    """Абстракция асинхронного rate-лимитера.

    Гарантирует, что общее число запросов не превысит установленный предел
    за указанный интервал времени. Используется в application-слое как порт,
    конкретные реализации располагаются во «внешней» инфраструктуре.
    """

    @abstractmethod
    async def acquire(self, count: int = 1) -> RateLimitPermitProtocol:
        """Блокирует корутину до момента, когда можно совершить ``count`` последовательных запросов.

        Параметры
        ----------
        count: int, default 1
            Сколько запросов планируется выполнить сразу после выхода
            из метода. Должно быть положительным.
        """
        ...

    @abstractmethod
    async def close(self) -> None:
        """Закрывает соединение с Redis или другой инфраструктурой."""
        ...
