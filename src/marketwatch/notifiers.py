"""Where alerts go: console, Discord webhook, Telegram bot."""

from __future__ import annotations

from typing import Any

import requests

TIMEOUT = 10


class NotifierError(RuntimeError):
    """A notification could not be delivered."""


class Notifier:
    name = "base"

    def send(self, text: str) -> None:
        raise NotImplementedError


class ConsoleNotifier(Notifier):
    name = "console"

    def send(self, text: str) -> None:
        print(f"ALERT  {text}", flush=True)


class DiscordNotifier(Notifier):
    name = "discord"

    def __init__(self, webhook_url: str, session: requests.Session | None = None) -> None:
        if not webhook_url:
            raise NotifierError("discord: webhook_url is empty (set DISCORD_WEBHOOK_URL)")
        self.webhook_url = webhook_url
        self.session = session or requests.Session()

    def send(self, text: str) -> None:
        try:
            resp = self.session.post(self.webhook_url, json={"content": text[:2000]}, timeout=TIMEOUT)
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise NotifierError(f"discord: {exc}") from exc


class TelegramNotifier(Notifier):
    name = "telegram"
    URL = "https://api.telegram.org/bot{token}/sendMessage"

    def __init__(self, bot_token: str, chat_id: str, session: requests.Session | None = None) -> None:
        if not bot_token or not chat_id:
            raise NotifierError("telegram: bot_token and chat_id are required")
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.session = session or requests.Session()

    def send(self, text: str) -> None:
        try:
            resp = self.session.post(
                self.URL.format(token=self.bot_token),
                data={"chat_id": self.chat_id, "text": text[:4096]},
                timeout=TIMEOUT,
            )
            resp.raise_for_status()
        except requests.RequestException as exc:
            # Don't leak the bot token (it is in the URL) into logs.
            raise NotifierError(f"telegram: request failed ({type(exc).__name__})") from None


def build_notifiers(settings: dict[str, Any], session: requests.Session | None = None) -> list[Notifier]:
    notifiers: list[Notifier] = []
    if settings.get("console"):
        notifiers.append(ConsoleNotifier())
    discord = settings.get("discord")
    if discord:
        notifiers.append(DiscordNotifier(discord.get("webhook_url", ""), session))
    telegram = settings.get("telegram")
    if telegram:
        notifiers.append(TelegramNotifier(telegram.get("bot_token", ""), str(telegram.get("chat_id", "")), session))
    if not notifiers:
        notifiers.append(ConsoleNotifier())
    return notifiers
