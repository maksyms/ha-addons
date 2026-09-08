"""Regression tests for Telegram reconnect handling.

Covers the 2026-09-03 outage: Telethon exhausted its reconnect retries and
pushed a ConnectionError into `client.disconnected`, which nothing awaited, so
the process stayed alive holding a dead connection and HA never restarted it.
"""

import asyncio
import collections
import logging
import os
import signal
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import autoanalyst as aa  # noqa: E402


class FakeClient:
    """Stand-in for TelegramClient covering only what run_session uses."""

    def __init__(self, die_with=None):
        self._die_with = die_with
        self._disconnected = None
        self.disconnect_calls = 0

    async def start(self):
        self._disconnected = asyncio.get_running_loop().create_future()
        if self._die_with is not None:
            asyncio.get_running_loop().call_later(0.01, self._die)

    def _die(self):
        if not self._disconnected.done():
            self._disconnected.set_exception(self._die_with)

    @property
    def disconnected(self):
        # Mirrors Telethon: a fresh shield wrapper on every access.
        return asyncio.shield(self._disconnected)

    async def get_me(self):
        return type("Me", (), {"first_name": "Test", "id": 1})()

    def on(self, _event):
        return lambda fn: fn

    async def disconnect(self):
        self.disconnect_calls += 1
        if self._disconnected is not None and not self._disconnected.done():
            self._disconnected.set_result(None)


def test_telethon_disconnected_is_a_fresh_wrapper_each_access():
    """Guards run_session's "capture it once" assumption against the real lib."""
    from telethon.network.mtprotosender import MTProtoSender

    async def check():
        loggers = collections.defaultdict(lambda: logging.getLogger(__name__))
        sender = MTProtoSender(None, loggers=loggers)

        # A live connection holds a *pending* _disconnected; asyncio.shield()
        # short-circuits on already-completed futures, so force the pending
        # state to exercise the case run_session actually meets.
        inner = asyncio.get_running_loop().create_future()
        sender._MTProtoSender__disconnected = inner

        first, second = sender.disconnected, sender.disconnected
        assert first is not second, "capture-once no longer needed; simplify run_session"
        # Cancelling one wrapper must leave Telethon's own future untouched.
        first.cancel()
        assert not second.cancelled()
        assert not inner.cancelled()
        inner.set_result(None)

    asyncio.run(check())


def test_run_session_raises_when_connection_dies():
    """The regression: an unexpected disconnect must surface, not hang forever."""
    boom = ConnectionError("Connection to Telegram failed 5 time(s)")
    client = FakeClient(die_with=boom)

    async def check():
        stop_event = asyncio.Event()
        with pytest.raises(ConnectionError) as excinfo:
            await asyncio.wait_for(aa.run_session(stop_event), timeout=5)
        assert excinfo.value is boom
        assert client.disconnect_calls == 1, "client must be cleaned up"

    aa.build_client = lambda: client
    asyncio.run(check())


def test_run_session_returns_cleanly_on_shutdown_request():
    """Shutdown must not be mistaken for a failure."""
    client = FakeClient()

    async def check():
        stop_event = asyncio.Event()
        asyncio.get_running_loop().call_later(0.01, stop_event.set)
        await asyncio.wait_for(aa.run_session(stop_event), timeout=5)
        assert client.disconnect_calls == 1

    aa.build_client = lambda: client
    asyncio.run(check())


def test_run_reconnects_after_dropped_connections(monkeypatch):
    """run() must keep rebuilding sessions instead of exiting on first failure."""
    monkeypatch.setattr(aa, "RECONNECT_BACKOFF_MIN", 0.01)
    monkeypatch.setattr(aa, "RECONNECT_BACKOFF_MAX", 0.02)

    attempts = []

    def flaky_client():
        client = FakeClient(die_with=ConnectionError("dropped"))
        attempts.append(client)
        if len(attempts) == 3:
            # Third outage: ask for shutdown so the test terminates.
            asyncio.get_running_loop().call_later(0.02, os.kill, os.getpid(), signal.SIGTERM)
        return client

    monkeypatch.setattr(aa, "build_client", flaky_client)

    async def check():
        await asyncio.wait_for(aa.run(), timeout=10)

    original = signal.getsignal(signal.SIGTERM)
    try:
        asyncio.run(check())
    finally:
        signal.signal(signal.SIGTERM, original)

    assert len(attempts) >= 3, f"expected repeated reconnects, got {len(attempts)}"
    assert all(c.disconnect_calls == 1 for c in attempts)
