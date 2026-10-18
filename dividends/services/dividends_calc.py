from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from dividends.models import DividendEvent, Transaction


def _d(x) -> Decimal:
    return x if isinstance(x, Decimal) else Decimal(str(x))


def shares_held_on(asset, on_date: date) -> Decimal:
    qty = Decimal("0")
    qs = asset.transactions.filter(date__lte=on_date).order_by("date", "id")
    for t in qs:
        typ = (t.type or "").lower()
        if typ == "buy":
            qty += _d(t.quantity)
        elif typ == "sell":
            qty -= _d(t.quantity)
    return max(qty, Decimal("0"))


@dataclass
class ExpectedDividend:
    event: DividendEvent
    shares: Decimal
    amount: Decimal


def expected_dividends(user, start: date, end: date):
    events = (
        DividendEvent.objects.filter(asset__user=user, ex_date__gte=start, ex_date__lte=end)
        .select_related("asset")
        .order_by("ex_date")
    )

    out: list[ExpectedDividend] = []
    total = Decimal("0")

    for ev in events:
        sh = shares_held_on(ev.asset, ev.ex_date)
        if sh <= 0:
            continue
        amt = sh * _d(ev.amount_per_share)
        total += amt
        out.append(ExpectedDividend(event=ev, shares=sh, amount=amt))

    return out, total