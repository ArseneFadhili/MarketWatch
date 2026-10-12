import pytest

from helpers import FakeResponse, FakeSession
from marketwatch.notifiers import (
    ConsoleNotifier,
    DiscordNotifier,
    NotifierError,
    TelegramNotifier,
    build_notifiers,
)


def test_discord_posts_json_content():
    session = FakeSession(FakeResponse({}, status=204))
    DiscordNotifier("https://discord.test/hook", session).send("hello")
    kind, url, payload, _ = session.calls[0]
    assert (kind, url, payload) == ("post", "https://discord.test/hook", {"content": "hello"})


def test_discord_truncates_to_message_limit():
    session = FakeSession(FakeResponse({}, status=204))
    DiscordNotifier("https://discord.test/hook", session).send("x" * 5000)
    assert len(session.calls[0][2]["content"]) == 2000


def test_discord_http_error_raises():
    with pytest.raises(NotifierError):
        DiscordNotifier("https://discord.test/hook", FakeSession(FakeResponse({}, status=404))).send("hi")


def test_discord_requires_url():
    with pytest.raises(NotifierError):
        DiscordNotifier("")


def test_telegram_posts_form_data():
    session = FakeSession(FakeResponse({"ok": True}))
    TelegramNotifier("TOKEN", "123", session).send("hello")
    _, url, _, data = session.calls[0]
    assert url == "https://api.telegram.org/botTOKEN/sendMessage"
    assert data == {"chat_id": "123", "text": "hello"}


def test_telegram_error_does_not_leak_token():
    with pytest.raises(NotifierError) as exc:
        TelegramNotifier("SECRET", "1", FakeSession(FakeResponse({}, status=401))).send("hi")
    assert "SECRET" not in str(exc.value)


def test_telegram_requires_credentials():
    with pytest.raises(NotifierError):
        TelegramNotifier("", "1")


def test_console_prints(capsys):
    ConsoleNotifier().send("moved")
    assert "moved" in capsys.readouterr().out


def test_build_notifiers_from_settings():
    names = [
        n.name
        for n in build_notifiers(
            {
                "console": True,
                "discord": {"webhook_url": "https://d.test/h"},
                "telegram": {"bot_token": "t", "chat_id": 9},
            }
        )
    ]
    assert names == ["console", "discord", "telegram"]


def test_build_notifiers_defaults_to_console():
    assert [n.name for n in build_notifiers({})] == ["console"]
