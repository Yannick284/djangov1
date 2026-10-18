from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
from typing import List, Optional

from dividends.models import Asset
from dividends.services.holdings import build_tx_index

@dataclass
class PerfRow:
    ticker: str
    qty: Decimal
    price: Decimal
    market: Decimal
    cost: Decimal
    pnl: Decimal
    pnl_pct: Decimal
    bar_pct: Decimal  # 0-100

@dataclass
class PerfSnap:
    rows: List[PerfRow]
    total_cost: Decimal
    total_market: Decimal
    total_pnl: Decimal
    total_pnl_pct: Decimal

def portfolio_performance(user) -> PerfSnap:
    tx_index = build_tx_index(user)

    assets = Asset.objects.filter(user=user, is_active=True).only("id", "ticker", "price")
    rows: List[PerfRow] = []

    total_cost = Decimal("0")
    total_market = Decimal("0")

    # pour scaler les barres
    max_abs_pnl = Decimal("0")

    for a in assets:
        pts = tx_index.get(a.id, [])
        if not pts:
            continue

        qty = pts[-1].shares if hasattr(pts[-1], "shares") else pts[-1][1]  # fallback si tu as tuple
        if qty <= 0:
            continue

        # cost basis = somme(qty_buy * price_buy) - somme(qty_sell * avg?) -> on fait simple: buy lots - sell lots au prix d'achat
        # IMPORTANT : si tes tx ont déjà un "cash" ou "amount", adapte ici.
        cost = Decimal("0")
        cur_qty = Decimal("0")
        for p in pts:
            q = getattr(p, "qty", None) or getattr(p, "delta", None) or getattr(p, "shares_delta", None) or getattr(p, "shares", None)
            px = getattr(p, "price", None)
            if q is None or px is None:
                continue
            q = Decimal(str(q))
            px = Decimal(str(px))
            # achats > 0
            if q > 0:
                cost += q * px
                cur_qty += q
            # ventes < 0 : on diminue juste la qty mais on ne recalcul pas proprement le PRU (simplifié)
            else:
                cur_qty += q

        # si tu veux un vrai PRU, faudra une logique FIFO ou average-cost.
        if cost <= 0:
            continue

        price = Decimal(str(getattr(a, "price", "0") or "0"))
        market = (qty * price).quantize(Decimal("0.01"))
        cost = cost.quantize(Decimal("0.01"))
        pnl = (market - cost).quantize(Decimal("0.01"))
        pnl_pct = (pnl / cost * Decimal("100")) if cost > 0 else Decimal("0")

        max_abs_pnl = max(max_abs_pnl, abs(pnl))

        total_cost += cost
        total_market += market

        rows.append(
            PerfRow(
                ticker=a.ticker,
                qty=qty,
                price=price,
                market=market,
                cost=cost,
                pnl=pnl,
                pnl_pct=pnl_pct,
                bar_pct=Decimal("0"),  # set après
            )
        )

    total_pnl = (total_market - total_cost).quantize(Decimal("0.01"))
    total_pnl_pct = (total_pnl / total_cost * Decimal("100")) if total_cost > 0 else Decimal("0")

    # bar scale: 100% = max_abs_pnl
    for r in rows:
        if max_abs_pnl > 0:
            r.bar_pct = (abs(r.pnl) / max_abs_pnl * Decimal("100")).quantize(Decimal("0.1"))
        else:
            r.bar_pct = Decimal("0")

    rows.sort(key=lambda r: r.market, reverse=True)

    return PerfSnap(
        rows=rows,
        total_cost=total_cost.quantize(Decimal("0.01")),
        total_market=total_market.quantize(Decimal("0.01")),
        total_pnl=total_pnl,
        total_pnl_pct=total_pnl_pct,
    )