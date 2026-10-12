import pytest

from marketwatch.config import ConfigError, load_config, parse_config


def valid(**overrides):
    data = {
        "watchlist": [
            {
                "symbol": "BTC-USD",
                "source": "coinbase",
                "rules": [
                    {"type": "percent_change", "percent": 3, "window_minutes": 15},
                    {"type": "above", "price": 120000},
                ],
            }
        ]
    }
    data.update(overrides)
    return data


def test_parses_valid_config_with_defaults():
    cfg = parse_config(valid())
    assert cfg.interval_seconds == 60
    assert cfg.cooldown_minutes == 30
    assert cfg.notifiers == {"console": True}
    item = cfg.watchlist[0]
    assert item.key == "coinbase:BTC-USD"
    assert [r.type for r in item.rules] == ["percent_change", "above"]


def test_env_vars_are_expanded(monkeypatch):
    monkeypatch.setenv("HOOK", "https://example.test/hook")
    cfg = parse_config(valid(notifiers={"discord": {"webhook_url": "${HOOK}"}}))
    assert cfg.notifiers["discord"]["webhook_url"] == "https://example.test/hook"


def test_missing_env_var_becomes_empty_string(monkeypatch):
    monkeypatch.delenv("NOPE", raising=False)
    cfg = parse_config(valid(notifiers={"discord": {"webhook_url": "${NOPE}"}}))
    assert cfg.notifiers["discord"]["webhook_url"] == ""


@pytest.mark.parametrize(
    "rule",
    [
        {"type": "sideways"},
        {"type": "above"},
        {"type": "percent_change", "percent": 0, "window_minutes": 5},
        {"type": "percent_change", "percent": 3},
        {"type": "below", "price": "abc"},
    ],
)
def test_bad_rules_are_rejected(rule):
    data = valid()
    data["watchlist"][0]["rules"] = [rule]
    with pytest.raises(ConfigError):
        parse_config(data)


def test_empty_watchlist_rejected():
    with pytest.raises(ConfigError):
        parse_config({"watchlist": []})


def test_item_without_rules_rejected():
    with pytest.raises(ConfigError):
        parse_config({"watchlist": [{"symbol": "BTC-USD", "source": "coinbase"}]})


def test_too_fast_interval_rejected():
    with pytest.raises(ConfigError):
        parse_config(valid(interval_seconds=1))


def test_missing_file_has_helpful_message(tmp_path):
    with pytest.raises(ConfigError, match="config.example.yaml"):
        load_config(tmp_path / "config.yaml")
