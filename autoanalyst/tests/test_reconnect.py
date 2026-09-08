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
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import autoanalyst as aa  # noqa: E402


class FakeClient:
    """Stand-in for TelegramClient covering only what run_session uses."""

    def __init__(self, die_with=None, hang_start=False):
        self._die_with = die_with
        self._hang_start = hang_start
        self._disconnected = None
        self.disconnect_calls = 0

    async def start(self):
        if self._hang_start:
            # Mimics start() retrying forever during a prolonged outage.
            await asyncio.Event().wait()
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


def test_build_client_retries_connections_forever(monkeypatch, tmp_path):
    """The default connection_retries=5 is exactly what killed the add-on."""
    from telethon import helpers

    # retry_range must read None as infinite rather than as zero retries.
    infinite = helpers.retry_range(None)
    assert [next(infinite) for _ in range(5)] == [1, 2, 3, 4, 5]

    monkeypatch.setattr(aa, "TELEGRAM_API_ID", 12345)
    monkeypatch.setattr(aa, "TELEGRAM_API_HASH", "0" * 32)
    monkeypatch.chdir(tmp_path)  # build_client() writes a session file to cwd

    async def check():
        client = aa.build_client()
        try:
            assert client._connection_retries is None
            assert client._retry_delay == 5
            assert client._sender._retries is None
        finally:
            await client.disconnect()

    asyncio.run(check())


def test_run_session_raises_when_connection_dies(monkeypatch):
    """The regression: an unexpected disconnect must surface, not hang forever."""
    boom = ConnectionError("Connection to Telegram failed 5 time(s)")
    client = FakeClient(die_with=boom)

    async def check():
        stop_event = asyncio.Event()
        with pytest.raises(ConnectionError) as excinfo:
            await asyncio.wait_for(aa.run_session(stop_event), timeout=5)
        assert excinfo.value is boom
        assert client.disconnect_calls == 1, "client must be cleaned up"

    monkeypatch.setattr(aa, "build_client", lambda: client)
    asyncio.run(check())


def test_run_session_returns_cleanly_on_shutdown_request(monkeypatch):
    """Shutdown must not be mistaken for a failure."""
    client = FakeClient()

    async def check():
        stop_event = asyncio.Event()
        asyncio.get_running_loop().call_later(0.01, stop_event.set)
        await asyncio.wait_for(aa.run_session(stop_event), timeout=5)
        assert client.disconnect_calls == 1

    monkeypatch.setattr(aa, "build_client", lambda: client)
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


def test_shutdown_interrupts_backoff_wait(monkeypatch):
    """SIGTERM during a backoff wait must not be ignored until it expires."""
    monkeypatch.setattr(aa, "RECONNECT_BACKOFF_MIN", 30)
    monkeypatch.setattr(aa, "RECONNECT_BACKOFF_MAX", 30)
    monkeypatch.setattr(
        aa, "build_client", lambda: FakeClient(die_with=ConnectionError("dropped"))
    )

    async def check():
        asyncio.get_running_loop().call_later(0.05, os.kill, os.getpid(), signal.SIGTERM)
        await asyncio.wait_for(aa.run(), timeout=20)

    original = signal.getsignal(signal.SIGTERM)
    started = time.monotonic()
    try:
        asyncio.run(check())
    finally:
        signal.signal(signal.SIGTERM, original)
    elapsed = time.monotonic() - started

    assert elapsed < 10, f"shutdown waited out the 30s backoff ({elapsed:.1f}s)"


def test_shutdown_interrupts_endless_connect(monkeypatch):
    """A shutdown request must interrupt start()'s now-infinite retry loop."""
    client = FakeClient(hang_start=True)
    monkeypatch.setattr(aa, "build_client", lambda: client)

    async def check():
        stop_event = asyncio.Event()
        asyncio.get_running_loop().call_later(0.05, stop_event.set)
        await asyncio.wait_for(aa.run_session(stop_event), timeout=5)

    asyncio.run(check())
    assert client.disconnect_calls == 1, "client must still be cleaned up"


def test_non_recoverable_error_exits_instead_of_retrying(monkeypatch):
    """A revoked session must exit so HA shows the add-on as failed."""
    monkeypatch.setattr(aa, "RECONNECT_BACKOFF_MIN", 0.01)
    fatal = RuntimeError("AUTH_KEY_UNREGISTERED")
    attempts = []

    def fatal_client():
        client = FakeClient(die_with=fatal)
        attempts.append(client)
        return client

    monkeypatch.setattr(aa, "build_client", fatal_client)

    async def check():
        with pytest.raises(RuntimeError) as excinfo:
            await asyncio.wait_for(aa.run(), timeout=5)
        assert excinfo.value is fatal

    original = signal.getsignal(signal.SIGTERM)
    try:
        asyncio.run(check())
    finally:
        signal.signal(signal.SIGTERM, original)

    assert len(attempts) == 1, f"must not retry a permanent failure, tried {len(attempts)}"
