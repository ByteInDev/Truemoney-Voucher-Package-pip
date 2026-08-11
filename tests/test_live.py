"""Live verification against the hosted backends.

Gated behind the ``LIVE=1`` environment variable — run with:

    set LIVE=1
    pytest tests/test_live.py
"""

from __future__ import annotations

import os

import pytest

from truemoney_voucher import PROVIDERS, TruemoneyApiError, create_client

pytestmark = pytest.mark.skipif(
    os.environ.get("LIVE") != "1",
    reason="set LIVE=1 to hit the hosted backends",
)

PROVIDER_NAMES = list(PROVIDERS)


@pytest.mark.parametrize("provider", PROVIDER_NAMES)
def test_status_and_info(provider: str) -> None:
    client = create_client(provider=provider)
    assert client.status() is True
    info = client.info()
    assert info["service"] == "truemoney-voucher"
    assert isinstance(info["routes"], list)


@pytest.mark.parametrize("provider", PROVIDER_NAMES)
def test_rejects_invalid_voucher_with_code_400(provider: str) -> None:
    client = create_client(provider=provider)
    with pytest.raises(TruemoneyApiError) as exc:
        client.redeem("123", "081")
    assert exc.value.code == 400


@pytest.mark.parametrize("provider", PROVIDER_NAMES)
def test_reaches_real_truemoney_upstream(provider: str) -> None:
    client = create_client(provider=provider)
    result = client.redeem("12345678901234", "0812345678")
    # A well-formed code must come back as TrueMoney's own envelope,
    # proving the proxy chain works end to end. The shared mock code has
    # been redeemed by earlier test runs (single-use), and upstream may
    # answer differently per request/region — any structured envelope is
    # an acceptable result as long as the transport itself worked.
    assert result.ok is True
    assert isinstance(result.status.code, str)
    assert result.status.code