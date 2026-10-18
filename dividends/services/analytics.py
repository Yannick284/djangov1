from decimal import Decimal
from django.db.models import Prefetch

from dividends.models import Asset, Transaction


def _d(x) -> Decimal:
    return x if isinstance(x, Decimal) else Decimal(str(x))


def current_quantity(asset: Asset) -> Decimal:
    qty = Decimal("0")
    for t in asset.transactions.all():
        if t.type == Transaction.BUY:
            qty += _d(t.quantity)
        elif t.type == Transaction.SELL:
            qty -= _d(t.quantity)
    return qty


def portfolio_allocation(user):
    """
    Retourne:
    - rows: [{asset, qty, price, value, weight}]
    - total_value
    - top1, top3 (weights)
    - missing_prices: assets avec qty>0 mais pas de last_price
    """
    assets = (
        Asset.objects.filter(user=user, is_active=True)
        .prefetch_related("transactions")
        .order_by("id")
    )

    rows = []
    missing_prices = []
    total_value = Decimal("0")

    for a in assets:
        qty = current_quantity(a)
        if qty <= 0:
            continue

        price = a.last_price  # DecimalField
        if price is None:
            missing_prices.append(a)
            continue

        value = qty * _d(price)
        total_value += value

        rows.append({
            "asset": a,
            "qty": qty,
            "price": _d(price),
            "value": value,
        })

    # weights + tri
    rows.sort(key=lambda r: r["value"], reverse=True)
    for r in rows:
        r["weight"] = (r["value"] / total_value) if total_value > 0 else Decimal("0")

    top1 = rows[0]["weight"] if rows else Decimal("0")
    top3 = sum([r["weight"] for r in rows[:3]], Decimal("0"))

    return {
        "rows": rows,
        "total_value": total_value,
        "top1": top1,
        "top3": top3,
        "missing_prices": missing_prices,
    }