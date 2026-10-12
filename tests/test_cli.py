from marketwatch import cli
from marketwatch.sources import PriceSourceError


def test_missing_config_exits_2(tmp_path, capsys):
    assert cli.main(["-c", str(tmp_path / "nope.yaml"), "once"]) == 2
    assert "config file not found" in capsys.readouterr().err


def test_price_command_prints_price(monkeypatch, capsys):
    class Fake:
        def fetch(self, symbol):
            return 1234.5

    monkeypatch.setattr(cli, "build_sources", lambda: {"coinbase": Fake()})
    assert cli.main(["price", "BTC-USD"]) == 0
    assert capsys.readouterr().out.strip() == "1,234.50"


def test_price_command_reports_errors(monkeypatch, capsys):
    class Broken:
        def fetch(self, symbol):
            raise PriceSourceError("coinbase: down")

    monkeypatch.setattr(cli, "build_sources", lambda: {"coinbase": Broken()})
    assert cli.main(["price", "BTC-USD"]) == 1
    assert "coinbase: down" in capsys.readouterr().err


def test_test_alert_uses_console(tmp_path, capsys):
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        "notifiers:\n  console: true\nwatchlist:\n"
        "  - symbol: BTC-USD\n    source: coinbase\n    rules:\n      - {type: above, price: 1}\n"
    )
    assert cli.main(["-c", str(cfg), "test-alert"]) == 0
    assert "sent via console" in capsys.readouterr().out
