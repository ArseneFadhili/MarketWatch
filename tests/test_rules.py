from marketwatch.config import Rule
from marketwatch.rules import PriceHistory, evaluate

PCT = Rule(type="percent_change", percent=3, window_minutes=15)


def history_of(*samples):
    return PriceHistory(list(samples))


def test_above_fires_at_or_over_target():
    rule = Rule(type="above", price=100)
    assert evaluate(rule, "X", 100, PriceHistory(), 0) is not None
    assert evaluate(rule, "X", 99.99, PriceHistory(), 0) is None


def test_below_fires_at_or_under_floor():
    rule = Rule(type="below", price=50)
    alert = evaluate(rule, "X", 49, PriceHistory(), 0)
    assert alert is not None and "below" in alert.message
    assert evaluate(rule, "X", 51, PriceHistory(), 0) is None


def test_percent_change_up():
    h = history_of((0, 100.0), (60, 104.0))
    alert = evaluate(PCT, "BTC-USD", 104.0, h, 60)
    assert alert is not None
    assert "up 4.00%" in alert.message and "15 min" in alert.message


def test_percent_change_down():
    h = history_of((0, 100.0), (60, 95.0))
    alert = evaluate(PCT, "BTC-USD", 95.0, h, 60)
    assert alert is not None and "down 5.00%" in alert.message


def test_small_move_does_not_fire():
    h = history_of((0, 100.0), (60, 101.0))
    assert evaluate(PCT, "BTC-USD", 101.0, h, 60) is None


def test_first_sample_has_nothing_to_compare_to():
    h = history_of((0, 100.0))
    assert evaluate(PCT, "BTC-USD", 100.0, h, 0) is None


def test_samples_outside_window_are_ignored():
    # The old low price is 30 minutes old; only the recent one counts.
    h = history_of((0, 50.0), (1700, 100.0), (1800, 101.0))
    assert evaluate(PCT, "BTC-USD", 101.0, h, 1800) is None


def test_prune_drops_old_but_keeps_newest():
    h = history_of((0, 1.0), (100, 2.0), (200, 3.0))
    h.prune(150)
    assert h.to_list() == [[200, 3.0]]
    h2 = history_of((0, 1.0))
    h2.prune(500)
    assert len(h2) == 1


def test_history_round_trips_through_lists():
    h = history_of((1.0, 2.0), (3.0, 4.0))
    assert PriceHistory.from_list(h.to_list()).to_list() == h.to_list()
