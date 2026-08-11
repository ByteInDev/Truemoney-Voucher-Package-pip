"""truemoney-voucher — Zero-dependency client for the Truemoney-Voucher REST APIs.

Pick any of the three hosted backends (Go / NestJS / FastAPI) with a single
option — or let the client pick the fastest healthy one automatically — and
redeem TrueMoney gift vouchers. Requires only the Python standard library.

Typical usage::

    from truemoney_voucher import create_client

    client = create_client()  # "auto" | "go" | "nestjs" | "fastapi"
    result = client.redeem("12345678901234", "0812345678")
    print(result.status.code)  # e.g. "VOUCHER_NOT_FOUND"

No construction needed? Use the static wrapper::

    from truemoney_voucher import Client

    result = Client.redeem("12345678901234", "0812345678")
"""

from .client import Client, TruemoneyClient, create_client
from .errors import TruemoneyApiError, TruemoneyError, TruemoneyTimeoutError
from .providers import PROVIDERS
from .types import RedeemResult, TrueMoneyStatus
from .version import __version__

__all__ = [
    "Client",
    "PROVIDERS",
    "RedeemResult",
    "TruemoneyApiError",
    "TruemoneyClient",
    "TruemoneyError",
    "TruemoneyTimeoutError",
    "TrueMoneyStatus",
    "__version__",
    "create_client",
]
