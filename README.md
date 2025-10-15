# FundingBot SDK

Пакет для внешних интеграций FundingBot. Содержит:
- `fundingbot_sdk.contracts` — публичные контракты (ports/protocols)
- `fundingbot_sdk.schemas` — публичные DTO (Pydantic‑модели)
- `fundingbot_sdk.toolkit` — утилиты (декораторы RL, базовые клиенты, нормализация и пр.)

## Установка

Poetry (локальная зависимость):
```toml
# pyproject.toml основного проекта
[tool.poetry.dependencies]
fundingbot-sdk = { path = "fundingbot-sdk", develop = true }
```

Из Git (VCS‑зависимость):
```toml
fundingbot-sdk = { git = "https://github.com/you/fundingbot-sdk.git", tag = "v0.1.0" }
```

Опциональные зависимости (extras):
```toml
# если нужны утилиты, зависящие от ccxt
fundingbot-sdk = { git = "https://github.com/you/fundingbot-sdk.git", tag = "v0.1.0", extras = ["ccxt"] }
```

Установка командой:
```bash
poetry update fundingbot-sdk
```

## Быстрый старт: базовый клиент CcxtClient
Пример использования готового базового клиента из toolkit (ccxt):

```python
import asyncio
from fundingbot_sdk.toolkit.client_base import CcxtClient
from fundingbot_sdk.contracts.ports.cex_client import CexClientConfig

async def main():
    cfg = CexClientConfig(
        api_key="...",
        api_secret="...",
        password=None,
        uid=None,
        default_type="swap",  # или "future"/"spot" при необходимости
        testnet=True,
        rate_limiter=None,     # можно передать реализацию RateLimiterPort
    )

    client = CcxtClient("bybit", cfg)
    await client.load_markets()
    ticker = await client.get_ticker("BTC/USDT:USDT")
    print(ticker)
    await client.close()

asyncio.run(main())
```

Краткий пример адаптера через наследование базового класса (если требуется бирже‑специфичная логика):

```python
from fundingbot_sdk.toolkit.client_base import CcxtClient

class MyBybitClient(CcxtClient):
    # при необходимости переопределяйте методы под особенности биржи
    # например, отчёт о закрытой позиции
    async def get_closed_position_report(self, **kwargs):
        # своя реализация поверх базового клиента
        return await super().get_closed_position_report(**kwargs)
```

## Плагины (опционально)
Адаптеры можно подключать как плагины через entry points.

В адаптере:
```toml
[project.entry-points."fundingbot.adapters"]
myexchange = "fundingbot_adapter_myexchange.client:MyExchangeClient"
```

В вашем проекте загрузите плагины через `importlib.metadata.entry_points` один раз в фабрике клиентов.

## Типизация
- Пакет содержит `py.typed` (PEP 561), поэтому типы доступны в mypy/pyright.
- Для VSCode/pyright добавьте пути:
```json
{
  "python.analysis.extraPaths": ["src", "fundingbot-sdk/src"],
  "cursorpyright.analysis.extraPaths": ["${workspaceFolder}/src", "${workspaceFolder}/fundingbot-sdk/src"]
}
```

## Лицензия
MIT — см. файл LICENSE.
