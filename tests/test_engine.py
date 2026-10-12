from helpers import Clock, FailingNotifier, RecordingNotifier, ScriptedSource
from marketwatch.config import parse_config
from marketwatch.engine import Tracker
from marketwatch.sources import PriceSourceError


def make_config(tmp_path, cooldown=30):
    return parse_config(
        {
            "interval_seconds": 60,
            "cooldown_minutes": cooldown,
            "state_file": str(tmp_path / "state.json"),
            "watchlist": [
                {
                    "symbol": "BTC-USD",
                    "source": "scripted",
                    "rules": [{"type": "percent_change", "percent": 3, "window_minutes": 15}],
                }
            ],
        }
    )


def make_tracker(tmp_path, prices, notifiers=None, cooldown=30, persist=False):
    clock = Clock()
    notifier = RecordingNotifier()
    tracker = Tracker(
        make_config(tmp_path, cooldown),
        {"scripted": ScriptedSource(prices)},
        notifiers if notifiers is not None else [notifier],
        clock=clock,
        persist=persist,
    )
    return tracker, clock, notifier


def test_alert_fires_on_big_move(tmp_path):
    tracker, clock, notifier = make_tracker(tmp_path, [100.0, 104.0])
    assert tracker.check_once() == []  # first sample: nothing to compare
    clock.t = 60
    alerts = tracker.check_once()
    assert len(alerts) == 1
    assert "up 4.00%" in notifier.messages[0]


def test_cooldown_suppresses_repeat_then_allows_again(tmp_path):
    tracker, clock, notifier = make_tracker(tmp_path, [100.0, 104.0, 106.0, 110.0, 115.0])
    tracker.check_once()
    clock.t = 60
    assert len(tracker.check_once()) == 1
    clock.t = 120
    assert tracker.check_once() == []  # still moving, but inside cooldown
    clock.t = 1860  # 30 minutes later; old samples have left the 15-minute window
    assert tracker.check_once() == []  # nothing recent to compare against yet
    clock.t = 1920
    assert len(tracker.check_once()) == 1  # cooldown over, 110 -> 115 is +4.5%
    assert len(notifier.messages) == 2


def test_failed_fetch_is_skipped_not_fatal(tmp_path):
    tracker, clock, notifier = make_tracker(tmp_path, [PriceSourceError("down"), 100.0])
    assert tracker.check_once() == []
    clock.t = 60
    assert tracker.check_once() == []
    assert notifier.messages == []


def test_unknown_source_is_skipped(tmp_path):
    tracker = Tracker(make_config(tmp_path), {}, [RecordingNotifier()], persist=False)
    assert tracker.check_once() == []


def test_broken_notifier_does_not_stop_others(tmp_path):
    good = RecordingNotifier()
    tracker, clock, _ = make_tracker(tmp_path, [100.0, 105.0], notifiers=[FailingNotifier(), good])
    tracker.check_once()
    clock.t = 60
    assert len(tracker.check_once()) == 1
    assert len(good.messages) == 1


def test_state_survives_restart(tmp_path):
    tracker, clock, _ = make_tracker(tmp_path, [100.0, 104.0], persist=True)
    tracker.check_once()
    clock.t = 60
    tracker.check_once()

    restarted, _, _ = make_tracker(tmp_path, [], persist=True)
    assert "scripted:BTC-USD" in restarted.histories
    assert restarted.last_alert  # cooldown is remembered across restarts


def test_corrupt_state_file_is_ignored(tmp_path):
    (tmp_path / "state.json").write_text("{not json")
    tracker, _, _ = make_tracker(tmp_path, [100.0], persist=True)
    assert tracker.histories == {}
    tracker.check_once()  # and it recovers by rewriting the file
    assert (tmp_path / "state.json").read_text().startswith("{")
