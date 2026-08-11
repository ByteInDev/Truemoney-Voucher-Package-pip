"""Result types returned by the client."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TrueMoneyStatus:
    """The upstream ``status`` object inside TrueMoney's envelope."""

    message: str
    code: str


@dataclass
class RedeemResult:
    """Successful redeem call — the TrueMoney envelope, strongly typed."""

    ok: bool
    status: TrueMoneyStatus
    data: Any = field(default=None)
