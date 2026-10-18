from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Dict, List

from dividends.models import Asset, Transaction


@dataclass(frozen=True)
class TxPoint:
    d: date
    qty: Decimal  # quantité détenue APRES cette transaction


def build_tx_index(user) -> Dict[int, List[TxPoint]]:
    """
    Index de transactions par asset, sous forme de points (date -> qty cumulée).
    Hypothèse: BUY ajoute, SELL enlève.
    """
    assets = Asset.objects.filter(user=user, is_active=True).only("id")
    asset_ids = list(assets.values_list("id", flat=True))

    tx = (
        Transaction.objects.filter(asset_id__in=asset_ids)
        .only("asset_id", "date", "type", "quantity")
        .order_by("asset_id", "date", "id")
    )

    out: Dict[int, List[TxPoint]] = {}
    running: Dict[int, Decimal] = {}

    for t in tx:
        qty = running.get(t.asset_id, Decimal("0"))

        if t.type == "BUY":
            qty += (t.quantity or Decimal("0"))
        elif t.type == "SELL":
            qty -= (t.quantity or Decimal("0"))

        if qty < 0:
            qty = Decimal("0")

        running[t.asset_id] = qty
        out.setdefault(t.asset_id, []).append(TxPoint(d=t.date, qty=qty))

    return out


def shares_asof(points: List[TxPoint], asof: date) -> Decimal:
    """
    Quantité détenue à une date asof via recherche binaire dans la série.
    """
    if not points:
        return Decimal("0")

    lo, hi = 0, len(points) - 1
    ans = -1
    while lo <= hi:
        mid = (lo + hi) // 2
        if points[mid].d <= asof:
            ans = mid
            lo = mid + 1
        else:
            hi = mid - 1

    if ans == -1:
        return Decimal("0")
    return points[ans].qty