"""Small fakes shared by the tests (no network access needed)."""

import requests

from marketwatch.notifiers import Notifier, NotifierError
from marketwatch.sources import PriceSource


class FakeResponse:
    def __init__(self, payload=None, status=200):
        self._payload = payload
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def json(self):
        if self._payload is None:
            raise ValueError("no json body")
        return self._payload


class FakeSession:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def get(self, url, params=None, timeout=None):
        self.calls.append(("get", url, params))
        return self.response

    def post(self, url, json=None, data=None, timeout=None):
        self.calls.append(("post", url, json, data))
        return self.response


class ScriptedSource(PriceSource):
    """Returns prices (or raises exceptions) from a pre-set list."""

    name = "scripted"

    def __init__(self, prices):
        super().__init__(session=object())
        self.prices = list(prices)

    def fetch(self, symbol):
        item = self.prices.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class RecordingNotifier(Notifier):
    name = "recording"

    def __init__(self):
        self.messages = []

    def send(self, text):
        self.messages.append(text)


class FailingNotifier(Notifier):
    name = "failing"

    def send(self, text):
        raise NotifierError("boom")


class Clock:
    def __init__(self, start=0.0):
        self.t = start

    def __call__(self):
        return self.t
