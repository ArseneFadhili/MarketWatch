# marketwatch

A small Python command-line tool that watches crypto and stock prices and sends you a **Discord or Telegram alert** when the market moves.

It polls free public price APIs, keeps a rolling price history, and fires an alert when a rule you wrote is triggered, such as "BTC moved 3% in 15 minutes" or "ETH dropped below $2,000". Alerts have a cooldown so you are not spammed, and history survives restarts.

```
$ marketwatch run
ALERT  BTC-USD down 3.41% in 15 min: $61,982.10 (was $64,171.00)
```

## Features

- **Price sources:** Coinbase (no key), CoinGecko (no key), Alpha Vantage for stocks (free key)
- **Rules:** `above`, `below`, and `percent_change` over a time window
- **Notifiers:** terminal, Discord webhook, Telegram bot (use any combination)
- **Cooldowns** per symbol and rule, remembered across restarts
- **Resilient:** a failed API call or a broken notifier never crashes the loop
- **Secrets stay out of git:** webhook URLs and tokens come from environment variables
- Fully unit-tested with no network access required

## Quick start

```bash
git clone https://github.com/ArseneFadhili/MarketWatch.git
cd MarketWatch
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

cp config.example.yaml config.yaml                   # then edit your watchlist
marketwatch price BTC-USD                            # sanity check the API
marketwatch run                                      # start watching
```

### Commands

| Command | What it does |
| --- | --- |
| `marketwatch run` | Watch continuously and send alerts |
| `marketwatch once` | Check everything one time and exit (handy for cron) |
| `marketwatch price BTC-USD [-s coingecko]` | Print one current price |
| `marketwatch test-alert` | Send a test message to every configured notifier |

Use `-c path/to/config.yaml` to pick a different config and `-v` to log every price check.

## Setting up alerts

**Discord:** Server Settings → Integrations → Webhooks → New Webhook → Copy Webhook URL.

```bash
export DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..."
```

**Telegram:** message `@BotFather` to create a bot and get a token, send your new bot any message, then open `https://api.telegram.org/bot<TOKEN>/getUpdates` to find your `chat.id`.

```bash
export TELEGRAM_BOT_TOKEN="123456:ABC..."
export TELEGRAM_CHAT_ID="987654321"
```

Uncomment the matching block in `config.yaml`, then run `marketwatch test-alert` to confirm delivery.

**Stocks:** get a free key at alphavantage.co and `export ALPHAVANTAGE_API_KEY=...`. The free tier allows only a few requests per day, so keep that watchlist short.

## Rules

```yaml
rules:
  - type: percent_change   # moved at least `percent` within `window_minutes`, up or down
    percent: 3
    window_minutes: 15
  - type: above            # price >= target
    price: 120000
  - type: below            # price <= floor
    price: 50000
```

## How it works

```
sources.py   ->  engine.py  ->  rules.py   ->  notifiers.py
fetch price      poll loop,      evaluate        console / Discord /
from an API      history,        each rule       Telegram
                 cooldowns,
                 state.json
```

| File | Role |
| --- | --- |
| `config.py` | Parses and validates YAML, expands `${ENV_VARS}` |
| `sources.py` | One class per API, all returning a float or raising `PriceSourceError` |
| `rules.py` | Pure functions plus `PriceHistory`, so rules are trivial to test |
| `notifiers.py` | Delivery channels, isolated so one failure can't affect others |
| `engine.py` | The `Tracker` loop, with injectable clock for deterministic tests |
| `cli.py` | argparse entry point |

## Tests

```bash
pytest -q
```

GitHub Actions runs the suite on Python 3.10 and 3.12 for every push.

## Run it all day

- **Raspberry Pi or a spare computer:** `nohup marketwatch run &`
- **cron:** `*/5 * * * * cd ~/marketwatch && .venv/bin/marketwatch once`
- **Free cloud VM:** run it under `systemd` or `tmux`

## Ideas to extend it

- WebSocket price feed instead of polling
- SQLite price history and a small chart dashboard
- Volatility-based rules (rolling standard deviation)
- Docker image and `docker compose` file
- More exchanges (Kraken, Binance) as new `PriceSource` subclasses

## Disclaimer

This is an educational project, not financial advice. Prices come from third-party APIs and may be delayed or wrong.

## License

MIT
