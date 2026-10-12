import pytest

from helpers import FakeResponse, FakeSession
from marketwatch.sources import (
    AlphaVantageSource,
    CoinbaseSource,
    CoinGeckoSource,
    PriceSourceError,
    build_sources,
)


def test_coinbase_parses_spot_price():
    session = FakeSession(FakeResponse({"data": {"base": "BTC", "currency": "USD", "amount": "64210.55"}}))
    assert CoinbaseSource(session).fetch("BTC-USD") == 64210.55
    assert session.calls[0][1] == "https://api.coinbase.com/v2/prices/BTC-USD/spot"


def test_coinbase_bad_payload():
    with pytest.raises(PriceSourceError):
        CoinbaseSource(FakeSession(FakeResponse({"errors": []}))).fetch("NOPE-USD")


def test_http_error_becomes_source_error():
    with pytest.raises(PriceSourceError):
        CoinbaseSource(FakeSession(FakeResponse({}, status=429))).fetch("BTC-USD")


def test_non_json_body_becomes_source_error():
    with pytest.raises(PriceSourceError):
        CoinbaseSource(FakeSession(FakeResponse(None))).fetch("BTC-USD")


def test_coingecko_parses_price():
    session = FakeSession(FakeResponse({"bitcoin": {"usd": 64000}}))
    assert CoinGeckoSource(session).fetch("bitcoin") == 64000.0
    assert session.calls[0][2] == {"ids": "bitcoin", "vs_currencies": "usd"}


def test_coingecko_unknown_coin():
    with pytest.raises(PriceSourceError):
        CoinGeckoSource(FakeSession(FakeResponse({}))).fetch("notacoin")


def test_alphavantage_parses_quote():
    session = FakeSession(FakeResponse({"Global Quote": {"05. price": "189.8400"}}))
    assert AlphaVantageSource(session, api_key="k").fetch("AAPL") == 189.84


def test_alphavantage_requires_key():
    with pytest.raises(PriceSourceError, match="ALPHAVANTAGE_API_KEY"):
        AlphaVantageSource(FakeSession(FakeResponse({})), api_key=None).fetch("AAPL")


def test_alphavantage_rate_limit_response():
    session = FakeSession(FakeResponse({"Information": "rate limit"}))
    with pytest.raises(PriceSourceError):
        AlphaVantageSource(session, api_key="k").fetch("AAPL")


def test_build_sources_reads_key_from_env():
    sources = build_sources(session=FakeSession(FakeResponse({})), env={"ALPHAVANTAGE_API_KEY": "abc"})
    assert set(sources) == {"coinbase", "coingecko", "alphavantage"}
    assert sources["alphavantage"].api_key == "abc"
