# dividends/services/pnl.py
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, Tuple

from dividends.models import Asset, Transaction


ZERO = Decimal("0")


@dataclass
class Position:
    qty: Decimal
    pmp: Decimal
    cost_basis: Decimal
    market_value: Decimal
    unrealized_pnl: Decimal
    realized_pnl: Decimal


def compute_position(asset: Asset) -> Position:
    """
    PMP (AVCO) :
    - BUY : recalcul PMP
    - SELL : realized += (sell - pmp) * qty - fees ; qty baisse ; pmp inchangé tant que qty>0
    """
    txs = asset.transactions.all().only("type", "date", "quantity", "price", "fees").order_by("date", "id")

    qty = ZERO
    pmp = ZERO
    realized = ZERO

    for tx in txs:
        q = Decimal(tx.quantity or 0)
        px = Decimal(tx.price or 0)
        fees = Decimal(tx.fees or 0)

        if q <= 0:
            continue

        if tx.type == Transaction.BUY:
            new_qty = qty + q
            total_cost = (qty * pmp) + (q * px) + fees
            qty = new_qty
            pmp = (total_cost / qty) if qty > 0 else ZERO

        elif tx.type == Transaction.SELL:
            if q > qty:
                # Si tu préfères, tu peux "continue" au lieu de raise.
                raise ValueError(f"[{asset.ticker}] oversell: sell {q} > held {qty} on {tx.date}")

            realized += (px - pmp) * q - fees
            qty -= q
            if qty == 0:
                pmp = ZERO

    last_price = Decimal(asset.last_price or 0)
    market_value = qty * last_price
    cost_basis = qty * pmp
    unrealized = market_value - cost_basis

    return Position(
        qty=qty,
        pmp=pmp,
        cost_basis=cost_basis,
        market_value=market_value,
        unrealized_pnl=unrealized,
        realized_pnl=realized,
    )


def realized_pnl_by_month(asset: Asset) -> Dict[str, Decimal]:
    """
    P&L réalisé mensuel basé sur PMP, date = date de vente.
    Return: {"YYYY-MM": pnl_decimal}
    """
    txs = asset.transactions.all().only("type", "date", "quantity", "price", "fees").order_by("date", "id")

    qty = ZERO
    pmp = ZERO
    out = defaultdict(lambda: ZERO)

    for tx in txs:
        q = Decimal(tx.quantity or 0)
        px = Decimal(tx.price or 0)
        fees = Decimal(tx.fees or 0)
        if q <= 0:
            continue

        if tx.type == Transaction.BUY:
            new_qty = qty + q
            total_cost = (qty * pmp) + (q * px) + fees
            qty = new_qty
            pmp = (total_cost / qty) if qty > 0 else ZERO

        elif tx.type == Transaction.SELL:
            if q > qty:
                raise ValueError(f"[{asset.ticker}] oversell: sell {q} > held {qty} on {tx.date}")

            pnl = (px - pmp) * q - fees
            ym = tx.date.strftime("%Y-%m")
            out[ym] += pnl

            qty -= q
            if qty == 0:
                pmp = ZERO

    return dict(out)