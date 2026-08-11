"""Error types raised by the client.

Every error extends :class:`TruemoneyError`, so a single ``except
TruemoneyError`` catches all failures.
"""

from __future__ import annotations

from typing import Any


class TruemoneyError(Exception):
    """Base error: network failure, non-JSON response or unexpected envelope."""

    def __init__(self, message: str, *, cause: BaseException | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.cause = cause


class TruemoneyApiError(TruemoneyError):
    """The API answered an error envelope (``{"code": ..., "message": ...}``).

    ``status`` is the HTTP status of the response, ``code``/``message`` come
    from the envelope body.
    """

    def __init__(
        self,
        status: int,
        *,
        code: int,
        message: str,
        envelope: dict[str, Any],
    ) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.envelope = envelope


class TruemoneyTimeoutError(TruemoneyError):
    """No response within the configured per-request timeout."""

    def __init__(self, timeout_ms: int) -> None:
        super().__init__(f"request timed out after {timeout_ms} ms")
        self.timeout_ms = timeout_ms
