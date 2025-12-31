from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Dict, List, Tuple

from django.utils import timezone

from dividends.models import Asset, DividendEvent
from dividends.services.holdings import build_tx_index, shares_asof


def _safe_date(y: int, m: int, d: int) -> date:
    # évite les soucis de 29/30/31
    if m == 2 and d > 28:
        d = 28
    if d > 28:
        d = min(d, 28)
    return date(y, m, d)


@dataclass
class ForecastEvent:
    asset_id: int
    ticker: str
    currency: str
    ex_date: date
    pay_date: date | None
    display_date: date
    amount_per_share: Decimal
    shares: Decimal
    estimated_amount: Decimal
    status: str  # "received" | "regular"


def build_year_events(user, year: int, growth_pct: Decimal = Decimal("0")) -> List[ForecastEvent]:
    """
    Logique:
    - On utilise comme "base" le dernier year dispo (<= year-1) PAR ASSET.
    - On projette les dates (ex/pay) sur l'année cible.
    - On applique la croissance: aps * (1+g)^(year-base_year_asset)
    - Montant = aps * shares détenues à ex_date (année cible)
    - Status:
        - si year < this_year => received
        - si year > this_year => regular
        - si year == this_year => received si display_date <= today sinon regular
    - On skip si shares == 0 (pas détenu à ex_date)
    """
    today = timezone.localdate()
    this_year = today.year

    growth = (growth_pct / Decimal("100")) if growth_pct else Decimal("0")

    assets = Asset.objects.filter(user=user, is_active=True).only("id", "ticker", "currency")
    asset_by_id = {a.id: a for a in assets}
    asset_ids = list(asset_by_id.keys())
    if not asset_ids:
        return []

    # On charge tous les events "historiques" jusqu'à year-1 (pour pouvoir projeter très loin)
    hist_events = (
        DividendEvent.objects.filter(asset_id__in=asset_ids, ex_date__year__lte=year - 1)
        .only("asset_id", "ex_date", "pay_date", "amount_per_share", "currency")
        .order_by("asset_id", "ex_date")
    )

    # base_year par asset = dernier ex_date.year
    base_year_by_asset: Dict[int, int] = {}
    events_by_asset_year: Dict[tuple[int, int], List[DividendEvent]] = {}

    for e in hist_events:
        y = e.ex_date.year
        key = (e.asset_id, y)
        events_by_asset_year.setdefault(key, []).append(e)
        base_year_by_asset[e.asset_id] = y  # comme c'est trié asc, la dernière écrase = max

    tx_index = build_tx_index(user)

    out: List[ForecastEvent] = []

    for asset_id in asset_ids:
        base_year = base_year_by_asset.get(asset_id)
        if not base_year:
            continue

        base_list = events_by_asset_year.get((asset_id, base_year), [])
        if not base_list:
            continue

        years_diff = year - base_year
        if years_diff < 0:
            continue

        factor = (Decimal("1") + growth) ** Decimal(str(years_diff)) if years_diff else Decimal("1")

        a = asset_by_id[asset_id]
        pts = tx_index.get(asset_id, [])

        for e in base_list:
            ex = _safe_date(year, e.ex_date.month, e.ex_date.day)
            pay = _safe_date(year, e.pay_date.month, e.pay_date.day) if e.pay_date else None
            display = pay or ex

            sh = shares_asof(pts, ex)
            if sh <= 0:
                continue

            aps = (e.amount_per_share or Decimal("0")) * factor
            amt = (aps * sh).quantize(Decimal("0.01"))

            if year < this_year:
                status = "received"
            elif year > this_year:
                status = "regular"
            else:
                status = "received" if display <= today else "regular"

            out.append(
                ForecastEvent(
                    asset_id=asset_id,
                    ticker=a.ticker,
                    currency=(e.currency or a.currency or "EUR"),
                    ex_date=ex,
                    pay_date=pay,
                    display_date=display,
                    amount_per_share=aps.quantize(Decimal("0.0001")),
                    shares=sh,
                    estimated_amount=amt,
                    status=status,
                )
            )

    # tri chrono
    out.sort(key=lambda x: (x.display_date, x.ticker))
    return out


def year_histogram(events: List[ForecastEvent], year: int) -> Tuple[List[dict], Decimal, Decimal]:
    """
    Retourne months = [{"label","total","received","regular","pct_total","pct_received"}, ...]
    + total_year + max_month
    pct_* calculés sur max_month (0..100) pour le rendu CSS.
    """
    labels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

    total = [Decimal("0.00")] * 12
    received = [Decimal("0.00")] * 12
    regular = [Decimal("0.00")] * 12

    for e in events:
        if e.display_date.year != year:
            continue
        i = e.display_date.month - 1
        total[i] += e.estimated_amount
        if e.status == "received":
            received[i] += e.estimated_amount
        else:
            regular[i] += e.estimated_amount

    total_year = sum(total, Decimal("0.00"))
    max_month = max(total) if total else Decimal("0.00")
    if max_month <= 0:
        max_month = Decimal("0.00")

    months: List[dict] = []
    for i in range(12):
        if max_month > 0:
            pct_total = int((total[i] / max_month * 100).quantize(Decimal("1")))
            pct_received = int((received[i] / max_month * 100).quantize(Decimal("1")))
        else:
            pct_total = 0
            pct_received = 0

        months.append(
            {
                "label": labels[i],
                "total": total[i],
                "received": received[i],
                "regular": regular[i],
                "pct_total": max(0, min(100, pct_total)),
                "pct_received": max(0, min(100, pct_received)),
            }
        )

    return months, total_year, max_month