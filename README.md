<br>

<div align="center">

# Truemoney-Voucher (pip)

**Zero-dependency client for the Truemoney-Voucher REST APIs** — redeem TrueMoney gift vouchers from pip, uv, poetry or any Python runtime

![License: MIT](https://img.shields.io/badge/license-MIT-yellow.svg)
![Python](https://img.shields.io/badge/Python-%3E%3D3.10-3776AB?logo=python&logoColor=white)
![Zero dependencies](https://img.shields.io/badge/dependencies-0-6DA55F)
![PyPI version](https://img.shields.io/pypi/v/truemoney-voucher)

**English** - [Thai](README.th.md)

</div>

---

A zero-dependency client for the [Truemoney-Voucher](https://github.com/ByteInDev) API family — three backend ports share the same HTTP contract, **and the client picks the fastest healthy one for you**:

| Provider | Backend | Hosted at |
| --- | --- | --- |
| `auto` (default) | probes all three, uses the fastest healthy one | failover on network errors |
| `go` | [Go](https://github.com/ByteInDev/Truemoney-Voucher-Go) (uTLS `HelloFirefox_148` + HTTP/2 framer) | https://truemoney-voucher-go.vercel.app |
| `nestjs` | [NestJS](https://github.com/ByteInDev/Truemoney-Voucher-NestJS) (cycletls Firefox 148 fingerprint) | https://truemoney-voucher-nestjs.vercel.app |
| `fastapi` | [FastAPI](https://github.com/ByteInDev/Truemoney-Voucher-FastAPI) (curl_cffi Firefox 147 fingerprint) | https://truemoney-voucher-fastapi.vercel.app |

## Features

| Ability | Details |
| ------- | ------- |
| Redeem | `Client.redeem(code, mobile)` — raw code **or** full `gift.truemoney.com` campaign URL |
| Auto provider | default `'auto'` probes all backends, picks the fastest healthy one, fails over on network errors |
| Static API | `from truemoney_voucher import Client` — no construction, no config, just `Client.redeem(...)` |
| Zero dependencies | Python standard library only — `urllib` + `threading`, no install deps |
| Universal runtime | CPython >= 3.10 (tested through 3.14), stdlib-only — no compiled extensions |
| Typed errors | `TruemoneyApiError`, `TruemoneyTimeoutError`, `TruemoneyError` with envelope access |

## Quick Start

Install with any Python package manager:

```bash
pip install truemoney-voucher
# or
uv add truemoney-voucher
# or
poetry add truemoney-voucher
```

No setup needed — `Client` is a ready-to-use static wrapper around an auto-configured instance:

```python
from truemoney_voucher import Client

# auto: probes the three hosted backends and uses the fastest healthy one
result = Client.redeem("12345678901234", "0812345678")
print(result.status.code)  # e.g. "VOUCHER_NOT_FOUND", "TARGET_USER_REDEEMED"

# Liveness probe:
alive = Client.status()

# Service info:
info = Client.info()
```

### Pin a provider (or configure your own)

```python
from truemoney_voucher import create_client

# Pin one backend explicitly:
client = create_client(provider="nestjs")  # "go" | "nestjs" | "fastapi"

# Or bring your own deployment (overrides `provider`):
custom = create_client(
    base_url="https://api.example.com",
    timeout_ms=15_000,
)

# Client.configure() re-creates the shared instance the same way:
Client.configure(provider="fastapi")
```

## API Reference

### Static `Client` (no construction)

| Method | Description |
| --- | --- |
| `Client.redeem(code, mobile)` | Redeem a raw code or full campaign URL through the fastest healthy backend |
| `Client.status()` | `True` when at least one hosted backend answers 2xx on `/status` |
| `Client.info()` | Service info + routes of the selected backend |
| `Client.configure(**kwargs)` | Replace the shared instance (auto by default) |

### `create_client(**kwargs) => TruemoneyClient`

| Option | Type | Default | Description |
| --- | --- | --- | --- |
| `provider` | `str` | `'auto'` | Which hosted backend to call — `'auto'` probes and picks the fastest healthy one |
| `base_url` | `str \| None` | provider URL | Full base URL (wins over `provider`) |
| `timeout_ms` | `int` | `30_000` | Per-request timeout |
| `urlopen` | `callable` | `urllib.request.urlopen` | Custom opener (tests, proxies) |
| `user_agent` | `str \| None` | `truemoney-voucher/1.1.0` | `User-Agent` header |
| `headers` | `dict[str, str]` | — | Extra headers on every request |

### Auto provider

- On the first call (or after a 60 s cache TTL) all three backends are probed in parallel (thread pool, `GET /status`, 3 s probe timeout) and ranked by latency.
- Redeem, `status()` and `info()` go to the fastest healthy backend; the ranking is cached for 60 seconds.
- If a redeem fails with a **network error**, the client automatically retries the next healthy backend. Validation errors (`TruemoneyApiError`) never trigger failover — a failed redeem can't be double-redeemed, so the worst case is `TARGET_USER_REDEEMED`.
- `client.explicit_base_url` returns the base URL of an explicitly selected backend (`None` for auto).

### `client.redeem(code, mobile) => RedeemResult`

Accepts a raw gift code **or** a full campaign URL (percent-encoded into the
path — the backends preserve `%2F`, matching the reference CLI).

- Returns `RedeemResult(ok=True, status=TrueMoneyStatus(message, code), data=...)` when the upstream call succeeds.
- Raises `TruemoneyApiError` on validation/routing errors (`{ code, message }` envelopes, or upstream Spring-style error bodies, which are normalized).

### `client.status() => bool`

`True` on any 2xx, `False` otherwise — never raises, safe for uptime checks.
In auto mode, `True` when at least one backend is healthy.

### `client.info() => dict`

Service name, deployed version (where exposed), and the route list.

### Errors

| Error | When |
| --- | --- |
| `TruemoneyApiError` | API answered `{ code, message }` (validation 400, not found 404, …) or a Spring-style error body. Exposes `status`, `code`, `envelope`. |
| `TruemoneyTimeoutError` | No response within `timeout_ms`. |
| `TruemoneyError` | Network failure, non-JSON response, unexpected envelope. |

All errors extend `TruemoneyError`:

```python
from truemoney_voucher import TruemoneyApiError

try:
    Client.redeem(code, mobile)
except TruemoneyApiError as err:
    print(err.code, err.message)  # 400 "Bad Request"
```

## TrueMoney status codes

When the upstream call succeeds, `result.status.code` carries TrueMoney's answer:

| Code | Meaning |
| ---- | ------- |
| `SUCCESS` | Money received successfully |
| `TARGET_USER_REDEEMED` | You already redeemed this voucher |
| `VOUCHER_OUT_OF_STOCK` | Someone else already took it |
| `VOUCHER_EXPIRED` | The wallet voucher has expired |
| `VOUCHER_NOT_FOUND` | Voucher not found in the system |
| `CANNOT_GET_OWN_VOUCHER` | Cannot redeem your own voucher |
| `TARGET_USER_NOT_FOUND` | Phone number not found in the system |
| `INTERNAL_ERROR` | Voucher not found, or the URL is wrong |

## Testing

```bash
pip install -e ".[dev]"
pytest tests/test_client.py tests/test_auto_client.py   # offline unit tests
set LIVE=1 && pytest tests/test_live.py                 # live checks against the three hosted backends
```

The live suite runs `status`/`info` and an invalid-voucher check against all
three Vercel deployments, plus a real upstream call.

## Contributing

Contributions are welcome! Please:

1. Open an issue first for significant changes
2. Keep `pytest tests` green
3. Bump `version` in `pyproject.toml` together with `src/truemoney_voucher/version.py`

## Disclaimer

> **For educational use or where the provider permits it.**
> Redeeming is irreversible and governed by TrueMoney's Terms of Service.
> Voucher codes are cash-equivalent — never log full codes.

## License

Licensed under the [MIT License](./LICENSE) © 2026 ByteInDev