"""The TruemoneyClient — a zero-dependency, stdlib-only API client."""

from __future__ import annotations

import json
import socket
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, ClassVar

from .errors import TruemoneyApiError, TruemoneyError, TruemoneyTimeoutError
from .providers import PROVIDERS
from .types import RedeemResult, TrueMoneyStatus
from .version import __version__

DEFAULT_TIMEOUT_MS = 30_000
AUTO_PROBE_TIMEOUT_MS = 3_000
AUTO_TTL_MS = 60_000

#: Callable compatible with ``urllib.request.urlopen`` (inject for tests).
Urlopen = Callable[..., Any]


def _is_error_envelope(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and isinstance(value.get("code"), int)
        and isinstance(value.get("message"), str)
    )


def _is_truemoney_envelope(value: Any) -> bool:
    return isinstance(value, dict) and isinstance(value.get("status"), dict)


def _is_spring_error_envelope(value: Any) -> bool:
    """Upstream Spring-style error body some backends pass through unchanged.

    ``{"timestamp": ..., "status": 400, "error": "Bad Request", "path": ...}``
    — normalize it into a :class:`TruemoneyApiError` instead of surfacing
    it as an "unexpected response".
    """

    return (
        isinstance(value, dict)
        and isinstance(value.get("status"), int)
        and isinstance(value.get("error"), str)
    )


class TruemoneyClient:
    """Client for the Truemoney-Voucher API (Go / NestJS / FastAPI ports).

    All three backends share the same HTTP contract. ``provider`` picks
    which one to call — or ``"auto"`` (the default), which probes all
    three backends, picks the fastest healthy one and automatically
    fails over on network errors. Point ``base_url`` at your own
    deployment to bypass that entirely.
    """

    def __init__(
        self,
        *,
        provider: str = "auto",
        base_url: str | None = None,
        timeout_ms: int = DEFAULT_TIMEOUT_MS,
        urlopen: Urlopen | None = None,
        user_agent: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        if provider != "auto" and provider not in PROVIDERS and base_url is None:
            raise ValueError(
                f"unknown provider {provider!r} — choose from {', '.join(PROVIDERS)} or 'auto'"
            )
        self._provider = provider
        self._base_url = base_url.rstrip("/") if base_url else None
        self._timeout_ms = timeout_ms
        self._urlopen = urlopen or urllib.request.urlopen
        self._user_agent = user_agent or f"truemoney-voucher/{__version__}"
        self._headers = dict(headers or {})
        self._auto_ranking: list[str] = []
        self._auto_selected_at = 0.0

    @property
    def explicit_base_url(self) -> str | None:
        """Base URL of an explicitly selected backend (``None`` for auto)."""
        if self._base_url:
            return self._base_url
        if self._provider == "auto":
            return None
        return PROVIDERS[self._provider]

    def redeem(self, code: str, mobile: str) -> RedeemResult:
        """Redeem a voucher to a Thai mobile number.

        Accepts a raw gift code or a full campaign URL (the URL is
        percent-encoded into the path, which the backends serve without
        normalizing ``%2F``).

        Returns the TrueMoney status envelope on success, raises
        :class:`TruemoneyApiError` for validation/routing errors and
        :class:`TruemoneyTimeoutError` when the request times out.

        With ``provider="auto"`` the redeems are retried on the next
        healthy backend when the first one fails with a network error.
        Validation errors (``TruemoneyApiError``) never trigger failover.
        """
        errors: list[Exception] = []
        for base in self._resolve_bases():
            try:
                return self._redeem_at(base, code, mobile)
            except TruemoneyApiError:
                raise
            except (TruemoneyError, TruemoneyTimeoutError) as error:
                if self._provider != "auto":
                    raise
                # Network-level failure: invalidate the cached selection
                # and try the next healthy backend. Redeem is single-use,
                # so a retry can never double-redeem — the worst case is
                # TARGET_USER_REDEEMED.
                self._auto_ranking = []
                errors.append(error)
        raise errors[-1]

    def status(self) -> bool:
        """Liveness probe. ``True`` on any 2xx, ``False`` otherwise.

        In auto mode all three backends are probed; ``True`` when at
        least one is healthy. Never raises, so it is safe for uptime
        checks.
        """
        if self._provider != "auto" or self._base_url:
            status, _ = self._request(self._first_base(), "GET", "/status")
            return 200 <= status < 300
        try:
            return len(self._rank_providers()) > 0
        except Exception:
            return False

    def info(self) -> dict[str, Any]:
        """Service info + available routes from ``GET /``."""
        _, payload = self._request(self._first_base(), "GET", "/")
        if not isinstance(payload, dict):
            raise TruemoneyError("unexpected service info response")
        return payload

    def _redeem_at(self, base: str, code: str, mobile: str) -> RedeemResult:
        path = f"/truemoney/{_quote(code)}/{_quote(mobile)}"
        status, payload = self._request(base, "GET", path)

        if _is_error_envelope(payload):
            raise TruemoneyApiError(
                status,
                code=payload["code"],
                message=payload["message"],
                envelope=payload,
            )
        if _is_spring_error_envelope(payload):
            raise TruemoneyApiError(
                status,
                code=payload["status"],
                message=payload["error"],
                envelope=payload,
            )
        if not _is_truemoney_envelope(payload):
            raise TruemoneyError(
                f"unexpected response (HTTP {status}): {json.dumps(payload)[:200]}"
            )

        raw_status = payload["status"]
        return RedeemResult(
            ok=True,
            status=TrueMoneyStatus(
                message=str(raw_status.get("message", "")),
                code=str(raw_status.get("code", "")),
            ),
            data=payload.get("data"),
        )

    def _resolve_bases(self) -> list[str]:
        """Ordered base URLs to try: explicit target, or auto ranking."""
        if self._base_url:
            return [self._base_url]
        if self._provider != "auto":
            return [PROVIDERS[self._provider]]
        ranking = self._rank_providers()
        if not ranking:
            raise TruemoneyError("auto provider: no healthy backend reachable")
        return [PROVIDERS[name] for name in ranking]

    def _first_base(self) -> str:
        base = self._resolve_bases()[0]
        if not base:
            raise TruemoneyError("no backend available")
        return base

    def _rank_providers(self) -> list[str]:
        """Healthy backends ordered by measured latency (cached for 60 s)."""
        now = time.monotonic()
        if self._auto_ranking and now - self._auto_selected_at < AUTO_TTL_MS:
            return list(self._auto_ranking)

        with ThreadPoolExecutor(max_workers=len(PROVIDERS)) as pool:
            results = list(
                pool.map(
                    lambda item: self._probe(item[1], item[0]),
                    PROVIDERS.items(),
                )
            )
        healthy = sorted(
            (result for result in results if result is not None),
            key=lambda result: result[1],
        )
        self._auto_ranking = [name for name, _ in healthy]
        self._auto_selected_at = now
        return list(self._auto_ranking)

    def _probe(self, base: str, name: str) -> tuple[str, float] | None:
        """Probe ``GET /status``; ``(name, latency)`` or ``None`` if unhealthy."""
        start = time.perf_counter()
        try:
            request = urllib.request.Request(
                base + "/status",
                method="GET",
                headers={"Accept": "application/json", "User-Agent": self._user_agent},
            )
            with self._urlopen(request, timeout=AUTO_PROBE_TIMEOUT_MS / 1000) as response:
                response.read()
                if not 200 <= response.status < 300:
                    return None
        except Exception:
            return None
        return (name, time.perf_counter() - start)

    def _request(self, base: str, method: str, path: str) -> tuple[int, Any]:
        request = urllib.request.Request(
            base + path,
            method=method,
            headers={
                "Accept": "application/json",
                "User-Agent": self._user_agent,
                **self._headers,
            },
        )

        try:
            with self._urlopen(request, timeout=self._timeout_ms / 1000) as response:
                body = response.read()
                status = getattr(response, "status", None) or response.getcode()
        except urllib.error.HTTPError as error:
            body = error.read()
            status = error.code
        except urllib.error.URLError as error:
            if isinstance(error.reason, socket.timeout):
                raise TruemoneyTimeoutError(self._timeout_ms) from error
            raise TruemoneyError(f"request failed: {error.reason}") from error
        except socket.timeout as error:
            raise TruemoneyTimeoutError(self._timeout_ms) from error
        except OSError as error:
            raise TruemoneyError(f"request failed: {error}") from error

        text = body.decode("utf-8", errors="replace") if body else ""
        payload: Any = None
        if text:
            try:
                payload = json.loads(text)
            except json.JSONDecodeError:
                payload = None
        return status, payload


def create_client(
    *,
    provider: str = "auto",
    base_url: str | None = None,
    timeout_ms: int = DEFAULT_TIMEOUT_MS,
    urlopen: Urlopen | None = None,
    user_agent: str | None = None,
    headers: dict[str, str] | None = None,
) -> TruemoneyClient:
    """Create a :class:`TruemoneyClient` for one of the hosted backends.

    ``provider`` defaults to ``"auto"`` — the fastest healthy backend
    wins, with automatic failover on network errors. Pass an explicit
    provider name to pin one, or ``base_url`` for your own deployment.

    Example::

        from truemoney_voucher import create_client

        client = create_client()  # auto: probes, picks fastest healthy
        result = client.redeem("CODE1234", "0812345678")
    """
    return TruemoneyClient(
        provider=provider,
        base_url=base_url,
        timeout_ms=timeout_ms,
        urlopen=urlopen,
        user_agent=user_agent,
        headers=headers,
    )


class Client:
    """Ready-to-use static client wrapping a shared auto-configured instance.

    No construction needed — parity with the npm SDK::

        from truemoney_voucher import Client

        result = Client.redeem("12345678901234", "0812345678")
        alive = Client.status()

    Use :meth:`configure` to swap in a custom instance (e.g. pinned
    provider or own ``base_url``).
    """

    _instance: ClassVar[TruemoneyClient] = TruemoneyClient()

    @classmethod
    def redeem(cls, code: str, mobile: str) -> RedeemResult:
        """Redeem through the (auto-selected) fastest healthy backend."""
        return cls._instance.redeem(code, mobile)

    @classmethod
    def status(cls) -> bool:
        """Liveness probe across the hosted backends."""
        return cls._instance.status()

    @classmethod
    def info(cls) -> dict[str, Any]:
        """Service info of the selected backend."""
        return cls._instance.info()

    @classmethod
    def configure(cls, **kwargs: Any) -> None:
        """Recreate the shared instance with custom options (auto by default)."""
        cls._instance = TruemoneyClient(**kwargs)


def _quote(value: str) -> str:
    """Percent-encode a path segment (UTF-8, like JS ``encodeURIComponent``)."""
    from urllib.parse import quote

    return quote(value, safe="")