"""Price sources. Each one turns a symbol into a float price."""

from __future__ import annotations

import os
from typing import Mapping

import requests

TIMEOUT = 10


class PriceSourceError(RuntimeError):
    """A price could not be fetched or parsed."""


class PriceSource:
    name = "base"

    def __init__(self, session: requests.Session | None = None) -> None:
        self.session = session or requests.Session()

    def fetch(self, symbol: str) -> float:
        raise NotImplementedError

    def _get_json(self, url: str, params: dict | None = None) -> dict:
        try:
            resp = self.session.get(url, params=params, timeout=TIMEOUT)
            resp.raise_for_status()
            return resp.json()
        except (requests.RequestException, ValueError) as exc:
            raise PriceSourceError(f"{self.name}: request failed: {exc}") from exc


class CoinbaseSource(PriceSource):
    """Coinbase public spot price. No API key. Symbols look like BTC-USD."""

    name = "coinbase"
    URL = "https://api.coinbase.com/v2/prices/{symbol}/spot"

    def fetch(self, symbol: str) -> float:
        data = self._get_json(self.URL.format(symbol=symbol))
        try:
            return float(data["data"]["amount"])
        except (KeyError, TypeError, ValueError) as exc:
            raise PriceSourceError(f"coinbase: unexpected response for {symbol}: {data!r}") from exc


class CoinGeckoSource(PriceSource):
    """CoinGecko simple price. No API key. Symbols are coin ids like 'bitcoin'."""

    name = "coingecko"
    URL = "https://api.coingecko.com/api/v3/simple/price"

    def fetch(self, symbol: str) -> float:
        data = self._get_json(self.URL, {"ids": symbol, "vs_currencies": "usd"})
        try:
            return float(data[symbol]["usd"])
        except (KeyError, TypeError, ValueError) as exc:
            raise PriceSourceError(f"coingecko: unexpected response for {symbol}: {data!r}") from exc


class AlphaVantageSource(PriceSource):
    """Stock quotes from Alpha Vantage. Needs a free key in ALPHAVANTAGE_API_KEY."""

    name = "alphavantage"
    URL = "https://www.alphavantage.co/query"

    def __init__(self, session: requests.Session | None = None, api_key: str | None = None) -> None:
        super().__init__(session)
        self.api_key = api_key

    def fetch(self, symbol: str) -> float:
        if not self.api_key:
            raise PriceSourceError("alphavantage: set ALPHAVANTAGE_API_KEY (free key at alphavantage.co)")
        data = self._get_json(
            self.URL, {"function": "GLOBAL_QUOTE", "symbol": symbol, "apikey": self.api_key}
        )
        try:
            return float(data["Global Quote"]["05. price"])
        except (KeyError, TypeError, ValueError) as exc:
            raise PriceSourceError(f"alphavantage: no quote for {symbol} (rate limit?): {data!r}") from exc


def build_sources(
    session: requests.Session | None = None, env: Mapping[str, str] | None = None
) -> dict[str, PriceSource]:
    env = os.environ if env is None else env
    session = session or requests.Session()
    return {
        "coinbase": CoinbaseSource(session),
        "coingecko": CoinGeckoSource(session),
        "alphavantage": AlphaVantageSource(session, env.get("ALPHAVANTAGE_API_KEY")),
    }
