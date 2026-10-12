"""Alert rules and the rolling price history they look at."""

from __future__ import annotations

from dataclasses import dataclass

from .config import Rule


@dataclass(frozen=True)
class Alert:
    symbol: str
    rule_key: str
    message: str
    price: float


class PriceHistory:
    """Time-ordered (timestamp, price) samples."""

    def __init__(self, samples: list[tuple[float, float]] | None = None) -> None:
        self._samples: list[tuple[float, float]] = list(samples or [])

    def add(self, ts: float, price: float) -> None:
        self._samples.append((ts, price))

    def prune(self, oldest_ts: float) -> None:
        """Drop samples older than oldest_ts, always keeping the newest one."""
        if len(self._samples) > 1:
            self._samples = [s for s in self._samples[:-1] if s[0] >= oldest_ts] + [self._samples[-1]]

    def reference_price(self, now: float, window_seconds: float) -> float | None:
        """Earliest price inside the window, or None if there is nothing to compare to."""
        start = now - window_seconds
        for ts, price in self._samples[:-1]:
            if ts >= start:
                return price
        return None

    def to_list(self) -> list[list[float]]:
        return [[ts, price] for ts, price in self._samples]

    @classmethod
    def from_list(cls, raw: list[list[float]]) -> "PriceHistory":
        return cls([(float(ts), float(price)) for ts, price in raw])

    def __len__(self) -> int:
        return len(self._samples)


def _money(value: float) -> str:
    return f"${value:,.2f}"


def evaluate(rule: Rule, symbol: str, price: float, history: PriceHistory, now: float) -> Alert | None:
    """Return an Alert if the rule fires for the latest price, else None."""
    if rule.type == "above" and rule.price is not None and price >= rule.price:
        return Alert(symbol, rule.key, f"{symbol} is at {_money(price)}, above your {_money(rule.price)} target", price)

    if rule.type == "below" and rule.price is not None and price <= rule.price:
        return Alert(symbol, rule.key, f"{symbol} is at {_money(price)}, below your {_money(rule.price)} floor", price)

    if rule.type == "percent_change" and rule.percent and rule.window_minutes:
        ref = history.reference_price(now, rule.window_minutes * 60)
        if ref:
            change = (price - ref) / ref * 100
            if abs(change) >= rule.percent:
                direction = "up" if change > 0 else "down"
                return Alert(
                    symbol,
                    rule.key,
                    f"{symbol} {direction} {abs(change):.2f}% in {rule.window_minutes} min: "
                    f"{_money(price)} (was {_money(ref)})",
                    price,
                )
    return None
