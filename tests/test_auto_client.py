"""Auto provider + static Client suites — parity with the npm SDK tests."""

from __future__ import annotations

import json
import re
import time
import urllib.error
from typing import Any

import pytest

from truemoney_voucher import (
    PROVIDERS,
    Client,
    TruemoneyApiError,
    TruemoneyClient,
    create_client,
)

GO = PROVIDERS["go"]
NEST = PROVIDERS["nestjs"]
FAST = PROVIDERS["fastapi"]

#: Simulated latency per backend (ms) — spaced widely to stay deterministic.
LATENCY: dict[str, float] = {GO: 100.0, NEST: 10.0, FAST: 50.0}


class FakeResponse:
    def __init__(self, body: bytes, status: int = 200) -> None:
        self._body = body
        self.status = status

    def read(self) -> bytes:
        return self._body

    def getcode(self) -> int:
        return self.status

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *exc: Any) -> None:
        return None


def envelope(code: str = "SUCCESS", message: str = "OK") -> bytes:
    return json.dumps({"status": {"message": message, "code": code}, "data": None}).encode()


def auto_urlopen(*, fail_redeem: tuple[str, ...] = (), probe_status: int = 200):
    """urlopen that simulates per-backend latency; returns (opener, call log)."""

    def opener(request: Any, timeout: float | None = None) -> Any:
        raw = request.full_url
        calls.append(raw)
        base = re.match(r"^https?://[^/]+", raw).group(0)
        delay = LATENCY.get(base)
        if delay:
            time.sleep(delay / 1000)
        if "/truemoney/" in raw:
            if base in fail_redeem:
                raise urllib.error.URLError("connection refused")
            return FakeResponse(envelope())
        return FakeResponse(b"", probe_status)

    calls: list[str] = []
    return opener, calls


def redeem_calls(log: list[str]) -> list[str]:
    return [u for u in log if "/truemoney/" in u]


class TestAutoProvider:
    def test_picks_the_fastest_healthy_provider(self) -> None:
        opener, log = auto_urlopen()
        client = create_client(provider="auto", urlopen=opener)

        result = client.redeem("ABC123", "0812345678")

        assert result.status.code == "SUCCESS"
        assert redeem_calls(log)[0].startswith(NEST)
        # one probe round for the three backends, then a single redeem
        assert len(log) == 4

    def test_explicit_provider_pins_backend(self) -> None:
        opener, log = auto_urlopen()
        client = create_client(provider="go", urlopen=opener)

        client.redeem("ABC123", "0812345678")

        assert redeem_calls(log)[0].startswith(GO)
        assert len(log) == 1  # no probes

    def test_explicit_base_url_beats_provider(self) -> None:
        opener, log = auto_urlopen()
        client = create_client(provider="go", base_url="https://example.test", urlopen=opener)

        client.status()

        assert log[0].startswith("https://example.test")

    def test_explicit_base_url_property(self) -> None:
        assert create_client(provider="fastapi").explicit_base_url == FAST
        assert create_client(base_url="https://example.test").explicit_base_url == "https://example.test"
        assert create_client().explicit_base_url is None  # auto

    def test_reuses_the_cached_ranking_within_ttl(self) -> None:
        opener, log = auto_urlopen()
        client = create_client(provider="auto", urlopen=opener)

        client.redeem("ABC123", "0812345678")
        client.redeem("DEF456", "0812345679")

        # exactly one probe round (3 backends) — the ranking is cached
        assert len(log) == 3 + 2
        assert all(u.startswith(NEST) for u in redeem_calls(log))

    def test_reprobes_after_ttl_expiry(self) -> None:
        opener, log = auto_urlopen()
        client = create_client(provider="auto", urlopen=opener)

        client.redeem("ABC123", "0812345678")
        # expire the cache by rewinding the monotonic clock past the 60 s TTL
        client._auto_selected_at = time.monotonic() - 61_000  # type: ignore[attr-defined]
        client.redeem("DEF456", "0812345679")

        assert len(log) == (3 + 1) + (3 + 1)

    def test_fails_over_to_next_healthy_provider_on_network_error(self) -> None:
        opener, log = auto_urlopen(fail_redeem=(NEST,))
        client = create_client(provider="auto", urlopen=opener)

        result = client.redeem("ABC123", "0812345678")

        assert result.status.code == "SUCCESS"
        calls = redeem_calls(log)
        assert calls[0].startswith(NEST)
        assert calls[1].startswith(FAST)  # next by latency

    def test_does_not_fail_over_on_api_errors(self) -> None:
        def envelope_api_error() -> bytes:
            return json.dumps({"code": 400, "message": "Bad Request"}).encode()

        orig_envelope = envelope

        def opener(request: Any, timeout: float | None = None) -> Any:
            raw = request.full_url
            calls.append(raw)
            if "/truemoney/" in raw:
                return FakeResponse(envelope_api_error())
            return FakeResponse(b"", 200)

        calls: list[str] = []
        client = create_client(provider="auto", urlopen=opener)

        with pytest.raises(TruemoneyApiError) as exc:
            client.redeem("ABC123", "0812345678")

        assert exc.value.code == 400
        assert len(redeem_calls(calls)) == 1  # never retried

    def test_status_true_when_any_backend_healthy(self) -> None:
        opener, _ = auto_urlopen()
        assert create_client(provider="auto", urlopen=opener).status() is True

    def test_status_false_when_all_backends_unreachable(self) -> None:
        opener, _ = auto_urlopen(probe_status=503)  # non-2xx probes are unhealthy

        def broken(request: Any, timeout: float | None = None) -> Any:
            raise urllib.error.URLError("connection refused")

        assert create_client(provider="auto", urlopen=broken).status() is False


class TestStaticClient:
    def test_redeems_through_shared_instance(self) -> None:
        opener, log = auto_urlopen()
        Client.configure(urlopen=opener, timeout_ms=5_000)

        result = Client.redeem("ABC123", "0812345678")

        assert result.status.code == "SUCCESS"
        calls = redeem_calls(log)
        assert calls and calls[0].startswith(NEST)

    def test_configure_replaces_instance(self) -> None:
        opener, log = auto_urlopen()
        Client.configure(provider="fastapi", urlopen=opener)

        Client.redeem("ABC123", "0812345678")

        assert redeem_calls(log)[0].startswith(FAST)

    def test_status_via_static_client(self) -> None:
        opener, _ = auto_urlopen()
        Client.configure(urlopen=opener)
        assert Client.status() is True