"""Load and validate the YAML configuration."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

_ENV_VAR = re.compile(r"\$\{([A-Za-z0-9_]+)\}")
RULE_TYPES = {"above", "below", "percent_change"}


class ConfigError(ValueError):
    """Raised when the config file is missing or invalid."""


def _expand_env(value: Any) -> Any:
    """Replace ${VAR} with environment variables so secrets stay out of the file."""
    if isinstance(value, str):
        return _ENV_VAR.sub(lambda m: os.environ.get(m.group(1), ""), value)
    if isinstance(value, dict):
        return {k: _expand_env(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_expand_env(v) for v in value]
    return value


@dataclass(frozen=True)
class Rule:
    type: str
    price: float | None = None
    percent: float | None = None
    window_minutes: int | None = None

    @property
    def key(self) -> str:
        if self.type == "percent_change":
            return f"percent_change:{self.percent}:{self.window_minutes}"
        return f"{self.type}:{self.price}"


@dataclass(frozen=True)
class WatchItem:
    symbol: str
    source: str
    rules: tuple[Rule, ...]

    @property
    def key(self) -> str:
        return f"{self.source}:{self.symbol}"


@dataclass(frozen=True)
class Config:
    interval_seconds: int = 60
    cooldown_minutes: int = 30
    state_file: str = "state.json"
    notifiers: dict[str, Any] = field(default_factory=dict)
    watchlist: tuple[WatchItem, ...] = ()


def _parse_rule(raw: dict[str, Any], where: str) -> Rule:
    rtype = raw.get("type")
    if rtype not in RULE_TYPES:
        raise ConfigError(f"{where}: rule type must be one of {sorted(RULE_TYPES)}, got {rtype!r}")
    try:
        if rtype in ("above", "below"):
            if "price" not in raw:
                raise ConfigError(f"{where}: '{rtype}' rule needs a 'price'")
            return Rule(type=rtype, price=float(raw["price"]))
        percent = float(raw.get("percent", 0))
        window = int(raw.get("window_minutes", 0))
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"{where}: invalid number in rule: {exc}") from exc
    if percent <= 0 or window <= 0:
        raise ConfigError(f"{where}: 'percent_change' needs positive 'percent' and 'window_minutes'")
    return Rule(type=rtype, percent=percent, window_minutes=window)


def parse_config(data: dict[str, Any]) -> Config:
    data = _expand_env(data or {})
    watchlist = []
    for i, raw in enumerate(data.get("watchlist") or []):
        where = f"watchlist[{i}]"
        if "symbol" not in raw or "source" not in raw:
            raise ConfigError(f"{where}: needs 'symbol' and 'source'")
        rules = tuple(_parse_rule(r, f"{where}.rules[{j}]") for j, r in enumerate(raw.get("rules") or []))
        if not rules:
            raise ConfigError(f"{where}: add at least one rule")
        watchlist.append(WatchItem(symbol=str(raw["symbol"]), source=str(raw["source"]), rules=rules))
    if not watchlist:
        raise ConfigError("watchlist is empty; add at least one symbol")

    interval = int(data.get("interval_seconds", 60))
    cooldown = int(data.get("cooldown_minutes", 30))
    if interval < 5:
        raise ConfigError("interval_seconds must be at least 5 to respect API rate limits")
    return Config(
        interval_seconds=interval,
        cooldown_minutes=cooldown,
        state_file=str(data.get("state_file", "state.json")),
        notifiers=data.get("notifiers") or {"console": True},
        watchlist=tuple(watchlist),
    )


def load_config(path: str | Path) -> Config:
    p = Path(path)
    if not p.exists():
        raise ConfigError(f"config file not found: {p} (copy config.example.yaml to {p})")
    with p.open() as fh:
        return parse_config(yaml.safe_load(fh))
