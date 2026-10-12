"""The polling loop: fetch prices, evaluate rules, notify, remember state."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Callable, Mapping, Sequence

from .config import Config
from .notifiers import Notifier, NotifierError
from .rules import Alert, PriceHistory, evaluate
from .sources import PriceSource, PriceSourceError

log = logging.getLogger("marketwatch")


class Tracker:
    def __init__(
        self,
        config: Config,
        sources: Mapping[str, PriceSource],
        notifiers: Sequence[Notifier],
        clock: Callable[[], float] = time.time,
        persist: bool = True,
    ) -> None:
        self.config = config
        self.sources = sources
        self.notifiers = list(notifiers)
        self.clock = clock
        self.persist = persist
        self.state_path = Path(config.state_file)
        self.histories: dict[str, PriceHistory] = {}
        self.last_alert: dict[str, float] = {}
        if persist:
            self._load_state()

    # -- state -------------------------------------------------------------
    def _load_state(self) -> None:
        try:
            raw = json.loads(self.state_path.read_text())
            self.histories = {k: PriceHistory.from_list(v) for k, v in raw.get("histories", {}).items()}
            self.last_alert = {k: float(v) for k, v in raw.get("last_alert", {}).items()}
        except FileNotFoundError:
            pass
        except (ValueError, TypeError, AttributeError):
            log.warning("state file %s is unreadable; starting fresh", self.state_path)

    def _save_state(self) -> None:
        payload = {
            "histories": {k: h.to_list() for k, h in self.histories.items()},
            "last_alert": self.last_alert,
        }
        tmp = self.state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload))
        tmp.replace(self.state_path)

    # -- core --------------------------------------------------------------
    def check_once(self) -> list[Alert]:
        """Run one polling pass and return the alerts that were sent."""
        now = self.clock()
        sent: list[Alert] = []

        for item in self.config.watchlist:
            source = self.sources.get(item.source)
            if source is None:
                log.error("unknown source %r for %s", item.source, item.symbol)
                continue
            try:
                price = source.fetch(item.symbol)
            except PriceSourceError as exc:
                log.warning("skipping %s: %s", item.key, exc)
                continue

            history = self.histories.setdefault(item.key, PriceHistory())
            history.add(now, price)
            log.info("%s = %s", item.key, price)

            for rule in item.rules:
                alert = evaluate(rule, item.symbol, price, history, now)
                if alert is None:
                    continue
                cooldown_key = f"{item.key}|{rule.key}"
                last = self.last_alert.get(cooldown_key)
                if last is not None and now - last < self.config.cooldown_minutes * 60:
                    continue
                self._dispatch(alert)
                self.last_alert[cooldown_key] = now
                sent.append(alert)

            longest = max((r.window_minutes or 0 for r in item.rules), default=0) * 60
            history.prune(now - longest)

        if self.persist:
            self._save_state()
        return sent

    def _dispatch(self, alert: Alert) -> None:
        for notifier in self.notifiers:
            try:
                notifier.send(alert.message)
            except NotifierError as exc:
                log.error("could not deliver via %s: %s", notifier.name, exc)

    def run_forever(self, sleep: Callable[[float], None] = time.sleep) -> None:
        log.info(
            "watching %d symbols every %ds", len(self.config.watchlist), self.config.interval_seconds
        )
        while True:
            self.check_once()
            sleep(self.config.interval_seconds)
