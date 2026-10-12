"""Command line interface."""

from __future__ import annotations

import argparse
import logging
import sys

from .config import ConfigError, load_config
from .engine import Tracker
from .notifiers import NotifierError, build_notifiers
from .sources import PriceSourceError, build_sources


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="marketwatch", description="Price alerts for crypto and stocks.")
    p.add_argument("-c", "--config", default="config.yaml", help="path to config file (default: config.yaml)")
    p.add_argument("-v", "--verbose", action="store_true", help="log every price check")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("run", help="watch continuously and send alerts")
    sub.add_parser("once", help="check every symbol one time and exit")
    sub.add_parser("test-alert", help="send a test message to every configured notifier")

    price = sub.add_parser("price", help="print the current price of one symbol")
    price.add_argument("symbol", help="e.g. BTC-USD (coinbase), bitcoin (coingecko), AAPL (alphavantage)")
    price.add_argument("-s", "--source", default="coinbase", choices=["coinbase", "coingecko", "alphavantage"])
    return p


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    if args.command == "price":
        try:
            print(f"{build_sources()[args.source].fetch(args.symbol):,.2f}")
            return 0
        except PriceSourceError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1

    try:
        config = load_config(args.config)
        notifiers = build_notifiers(config.notifiers)
    except (ConfigError, NotifierError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.command == "test-alert":
        for n in notifiers:
            try:
                n.send("marketwatch test alert: your notifications are working.")
                print(f"sent via {n.name}")
            except NotifierError as exc:
                print(f"failed via {n.name}: {exc}", file=sys.stderr)
        return 0

    tracker = Tracker(config, build_sources(), notifiers)
    if args.command == "once":
        alerts = tracker.check_once()
        print(f"{len(alerts)} alert(s) sent")
        return 0

    try:
        tracker.run_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
