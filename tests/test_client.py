"""Offline unit tests — the network is always mocked, nothing leaves the machine."""

from __future__ import annotations

import json
import urllib.error
from typing import Any

import pytest

from truemoney_voucher import (
    PROVIDERS,
    TruemoneyApiError,
    TruemoneyError,
    TruemoneyTimeoutError,
    create_client,
)


class FakeResponse:
    def __init__(self, body: bytes, status: int = 200) -> None:
        self._body = body
        self.status = status

    def read(self) -> bytes:
        return self._body

    def getcode(self) -> int:
        return self.status

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *exc: Any) -> None:
        return None


class FakeHTTPError(urllib.error.HTTPError):
    """HTTPError whose ``read()`` returns a preset body (no real socket)."""

    def __init__(self, status: int, body: bytes) -> None:
        super().__init__(url="http://example.test", code=status, msg="error", hdrs={}, fp=None)
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> FakeHTTPError:
        return self

    def __exit__(self, *exc: Any) -> None:
        return None


def fake_urlopen(responses: dict[str, Any]):
    """Return a urlopen that answers by URL path, capturing the request."""

    def opener(request: Any, timeout: float | None = None) -> Any:
        captured["request"] = request
        captured["timeout"] = timeout
        response = responses.get(request.selector)
        if isinstance(response, BaseException):
            raise response
        return response

    captured: dict[str, Any] = {}
    return opener, captured


def envelope(code: str, message: str = "OK") -> bytes:
    return json.dumps({"status": {"message": message, "code": code}, "data": None}).encode()


class TestRedeem:
    def test_success_returns_typed_result(self) -> None:
        opener, captured = fake_urlopen(
            {"/truemoney/ABC123/0812345678": FakeResponse(envelope("SUCCESS"))}
        )  # type: ignore[call-arg]
        client = create_client(provider="fastapi", urlopen=opener)

        result = client.redeem("ABC123", "0812345678")

        assert result.ok is True
        assert result.status.code == "SUCCESS"
        assert result.status.message == "OK"
        assert result.data is None
        assert captured["request"].full_url.startswith(PROVIDERS["fastapi"])

    def test_error_envelope_raises_api_error(self) -> None:
        body = json.dumps({"code": 400, "message": "Bad Request"}).encode()
        opener, _ = fake_urlopen({"/truemoney/123/081": FakeResponse(body)})  # type: ignore[call-arg]
        client = create_client(provider="fastapi", urlopen=opener)

        with pytest.raises(TruemoneyApiError) as exc:
            client.redeem("123", "081")

        assert exc.value.code == 400
        assert exc.value.status == 200
        assert exc.value.envelope == {"code": 400, "message": "Bad Request"}

    def test_http_error_with_envelope_raises_api_error(self) -> None:
        body = json.dumps({"code": 404, "message": "Not Found"}).encode()
        opener, _ = fake_urlopen({"/truemoney/ABC123/0812345678": FakeHTTPError(404, body)})  # type: ignore[call-arg]
        client = create_client(provider="fastapi", urlopen=opener)

        with pytest.raises(TruemoneyApiError) as exc:
            client.redeem("ABC123", "0812345678")

        assert exc.value.code == 404
        assert exc.value.status == 404

    def test_spring_error_body_raises_api_error(self) -> None:
        body = json.dumps(
            {
                "timestamp": 1,
                "status": 400,
                "error": "Bad Request",
                "path": "/campaign/vouchers/x/redeem",
            }
        ).encode()
        opener, _ = fake_urlopen({"/truemoney/ABC123/0812345678": FakeResponse(body)})  # type: ignore[call-arg]
        client = create_client(provider="fastapi", urlopen=opener)

        with pytest.raises(TruemoneyApiError) as exc:
            client.redeem("ABC123", "0812345678")

        assert exc.value.code == 400
        assert exc.value.status in (200, 400)

    def test_non_json_body_raises(self) -> None:
        opener, _ = fake_urlopen({"/truemoney/ABC/0812345678": FakeResponse(b"<html>boom</html>")})  # type: ignore[call-arg]
        client = create_client(provider="fastapi", urlopen=opener)

        with pytest.raises(TruemoneyError):
            client.redeem("ABC", "0812345678")

    def test_empty_body_raises(self) -> None:
        opener, _ = fake_urlopen({"/truemoney/ABC/0812345678": FakeResponse(b"")})  # type: ignore[call-arg]
        client = create_client(provider="fastapi", urlopen=opener)

        with pytest.raises(TruemoneyError):
            client.redeem("ABC", "0812345678")

    def test_timeout_raises_timeout_error(self) -> None:
        opener, _ = fake_urlopen(
            {"/truemoney/ABC/0812345678": urllib.error.URLError(TimeoutError("timed out"))}
        )  # type: ignore[call-arg]
        client = create_client(provider="fastapi", urlopen=opener, timeout_ms=5_000)

        with pytest.raises(TruemoneyTimeoutError) as exc:
            client.redeem("ABC", "0812345678")

        assert exc.value.timeout_ms == 5_000

    def test_connection_failure_raises_base_error(self) -> None:
        opener, _ = fake_urlopen(
            {"/truemoney/ABC/0812345678": urllib.error.URLError("connection refused")}
        )  # type: ignore[call-arg]
        client = create_client(provider="fastapi", urlopen=opener)

        with pytest.raises(TruemoneyError) as exc:
            client.redeem("ABC", "0812345678")

        assert "connection refused" in exc.value.message

    def test_os_error_raises_base_error(self) -> None:
        opener, _ = fake_urlopen({"/truemoney/ABC/0812345678": ConnectionResetError("reset")})  # type: ignore[call-arg]
        client = create_client(provider="fastapi", urlopen=opener)

        with pytest.raises(TruemoneyError):
            client.redeem("ABC", "0812345678")

    def test_full_campaign_url_is_percent_encoded(self) -> None:
        code = "https://gift.truemoney.com/campaign/?v=AB CD"
        opener, captured = fake_urlopen(
            {
                "/truemoney/https%3A%2F%2Fgift.truemoney.com%2Fcampaign%2F%3Fv%3DAB%20CD/0812345678": FakeResponse(
                    envelope("VOUCHER_NOT_FOUND")
                )
            }
        )  # type: ignore[call-arg]
        client = create_client(provider="fastapi", urlopen=opener)

        client.redeem(code, "0812345678")

        assert "https%3A%2F%2F" in captured["request"].full_url


class TestStatusAndInfo:
    def test_status_true_on_2xx(self) -> None:
        opener, _ = fake_urlopen({"/status": FakeResponse(b"")})  # type: ignore[call-arg]
        assert create_client(provider="fastapi", urlopen=opener).status() is True

    def test_status_false_on_5xx(self) -> None:
        opener, _ = fake_urlopen({"/status": FakeHTTPError(503, b"")})  # type: ignore[call-arg]
        assert create_client(provider="fastapi", urlopen=opener).status() is False

    def test_info_returns_service_dict(self) -> None:
        info = {"service": "truemoney-voucher", "routes": ["GET|POST /status"]}
        opener, _ = fake_urlopen({"/": FakeResponse(json.dumps(info).encode())})  # type: ignore[call-arg]
        assert create_client(provider="fastapi", urlopen=opener).info() == info


class TestConfiguration:
    def test_unknown_provider_raises_value_error(self) -> None:
        with pytest.raises(ValueError):
            create_client(provider="pypi")

    def test_base_url_wins_over_provider(self) -> None:
        opener, captured = fake_urlopen({"/status": FakeResponse(b"")})  # type: ignore[call-arg]
        client = create_client(provider="go", base_url="https://example.test", urlopen=opener)

        client.status()

        assert captured["request"].full_url.startswith("https://example.test")

    def test_custom_headers_and_user_agent(self) -> None:
        opener, captured = fake_urlopen({"/status": FakeResponse(b"")})  # type: ignore[call-arg]
        client = create_client(
            provider="fastapi",
            urlopen=opener,
            user_agent="my-app/1.0",
            headers={"X-Trace": "abc"},
        )

        client.status()

        headers = {k.lower(): v for k, v in captured["request"].headers.items()}
        assert headers["user-agent"] == "my-app/1.0"
        assert headers["x-trace"] == "abc"
        assert captured["request"].get_method() == "GET"

    def test_timeout_ms_passed_as_seconds(self) -> None:
        opener, captured = fake_urlopen({"/status": FakeResponse(b"")})  # type: ignore[call-arg]
        client = create_client(provider="fastapi", urlopen=opener, timeout_ms=15_000)

        client.status()

        assert captured["timeout"] == 15.0
