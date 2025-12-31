from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Dict, List, Tuple, Optional

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from dividends.models import Asset, Transaction
from dividends.services.universe import UNIVERSE, universe_choices, UniverseItem
from .services.calendar_view import month_grid
from .services.forecast_year import build_year_events, year_histogram


# =========================
# Helpers
# =========================
def _get_int(request, key: str, default: int) -> int:
    raw = request.GET.get(key, None)
    if raw is None:
        return default
    try:
        return int(str(raw))
    except (TypeError, ValueError):
        return default


def _get_decimal(request, key: str, default: str = "0") -> Decimal:
    raw = request.GET.get(key, default)
    try:
        return Decimal(str(raw))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal(default)


def _dec(raw, default: str = "0") -> Decimal:
    try:
        return Decimal(str(raw))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal(default)


def _d0(x) -> Decimal:
    return Decimal(str(x or 0))


def _safe_div(a: Decimal, b: Decimal) -> Decimal:
    return (a / b) if b and b != 0 else Decimal("0")


def _pct(x: Decimal) -> Decimal:
    return x * Decimal("100")


def _money(x: Decimal) -> Decimal:
    return x.quantize(Decimal("0.01"))


def _quant2(x: Decimal) -> Decimal:
    return x.quantize(Decimal("0.01"))


def _parse_date(s: str) -> Optional[date]:
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return None


def _redirect_dashboard_with_qs(request):
    """Retour dashboard en conservant y/g si présents."""
    y = request.GET.get("y")
    g = request.GET.get("g")
    qs = []
    if y:
        qs.append(f"y={y}")
    if g:
        qs.append(f"g={g}")
    url = reverse("dividends-dashboard")
    return redirect(url + (("?" + "&".join(qs)) if qs else ""))


def _apply_universe_to_asset(asset: Asset, item: UniverseItem) -> bool:
    """
    Force la cohérence DB :
    - ticker = item.ticker (ex: SAN.PA)
    - symbol = item.symbol (ex: SAN.PA)
    - isin = item.isin
    - currency/sector si vides
    Retourne True si modifié.
    """
    changed = False

    # ticker / symbol / isin : c’est le coeur de ton sync_prices
    if getattr(asset, "ticker", "") != item.ticker:
        asset.ticker = item.ticker
        changed = True

    if hasattr(asset, "symbol") and getattr(asset, "symbol", "") != item.symbol:
        asset.symbol = item.symbol
        changed = True

    if hasattr(asset, "isin") and item.isin and getattr(asset, "isin", "") != item.isin:
        asset.isin = item.isin
        changed = True

    # champs secondaires
    if hasattr(asset, "currency") and (not asset.currency):
        asset.currency = item.currency
        changed = True

    if hasattr(asset, "sector") and (not asset.sector or asset.sector == "—") and item.sector:
        asset.sector = item.sector
        changed = True

    return changed


# =========================
# Dividends breakdown + heatmap
# =========================
def _build_dividend_breakdown(events, year: int) -> dict:
    by_ticker = defaultdict(
        lambda: {
            "total": Decimal("0"),
            "received": Decimal("0"),
            "regular": Decimal("0"),
            "by_month": defaultdict(lambda: Decimal("0")),
        }
    )

    total = Decimal("0")
    received = Decimal("0")
    regular = Decimal("0")

    for e in events:
        d = getattr(e, "display_date", None)
        if not d or d.year != year:
            continue

        ticker = getattr(e, "ticker", "—") or "—"
        amt = _d0(getattr(e, "estimated_amount", 0))
        status = (getattr(e, "status", "") or "").lower()

        total += amt
        by_ticker[ticker]["total"] += amt
        by_ticker[ticker]["by_month"][d.month] += amt

        if status == "received":
            received += amt
            by_ticker[ticker]["received"] += amt
        else:
            regular += amt
            by_ticker[ticker]["regular"] += amt

    tickers_sorted = sorted(by_ticker.keys(), key=lambda t: by_ticker[t]["total"], reverse=True)

    max_cell = Decimal("0")
    raw_rows = []
    for t in tickers_sorted:
        cells = []
        for m in range(1, 13):
            v = by_ticker[t]["by_month"].get(m, Decimal("0"))
            max_cell = max(max_cell, v)
            cells.append(v)
        raw_rows.append({"ticker": t, "total": by_ticker[t]["total"], "cells": cells})

    denom = max_cell if max_cell > 0 else Decimal("1")

    heat_rows = []
    for r in raw_rows:
        cells2 = []
        for v in r["cells"]:
            intensity = int((_safe_div(v, denom) * Decimal("100")).quantize(Decimal("1")))
            cells2.append({"v": _money(v), "i": intensity})
        heat_rows.append({"ticker": r["ticker"], "total": _money(r["total"]), "cells2": cells2})

    return {
        "div_total": _money(total),
        "div_received": _money(received),
        "div_regular": _money(regular),
        "heat_rows": heat_rows,
        "max_cell": _money(max_cell),
    }


# =========================
# Perf snapshot (PRU vs market) + donut
# =========================
@dataclass
class PerfRow:
    asset_id: int
    ticker: str
    sector: str
    qty: Decimal

    avg_cost: Decimal
    mkt_price: Decimal

    cost_total: Decimal
    market_total: Decimal

    pru: Decimal
    price: Decimal
    unit_diff: Decimal

    pnl: Decimal
    pnl_pct: Decimal

    bar_pct: int
    is_neg: bool


def _build_perf_snapshot(user) -> dict:
    assets = (
        Asset.objects.filter(user=user, is_active=True)
        .only("id", "ticker", "sector", "last_price", "currency")
        .order_by("ticker")
    )
    asset_by_id = {a.id: a for a in assets}
    asset_ids = list(asset_by_id.keys())

    txs = (
        Transaction.objects.filter(asset_id__in=asset_ids)
        .only("asset_id", "type", "date", "quantity", "price", "fees")
        .order_by("date", "id")
    )

    pos_qty: Dict[int, Decimal] = {aid: Decimal("0") for aid in asset_ids}
    pos_cost: Dict[int, Decimal] = {aid: Decimal("0") for aid in asset_ids}  # coût restant (qty * PMP)
    realized: Dict[int, Decimal] = {aid: Decimal("0") for aid in asset_ids}  # ✅ P&L réalisé cumulé

    for t in txs:
        aid = t.asset_id
        q = _d0(t.quantity)
        p = _d0(t.price)
        f = _d0(getattr(t, "fees", 0))

        if q <= 0:
            continue

        if t.type == Transaction.BUY:
            pos_qty[aid] += q
            # ✅ frais inclus dans le PRU (PMP)
            pos_cost[aid] += (q * p) + f

        elif t.type == Transaction.SELL:
            qty_before = pos_qty[aid]
            if qty_before <= 0:
                continue

            avg = (pos_cost[aid] / qty_before) if qty_before > 0 else Decimal("0")
            sell_qty = min(q, qty_before)

            # ✅ gain réalisé = (sell - PMP) * qty - fees
            realized[aid] += (p - avg) * sell_qty - f

            # On retire du coût restant la part vendue au PMP
            pos_qty[aid] -= sell_qty
            pos_cost[aid] -= (sell_qty * avg)

            # petite protection numérique
            if pos_qty[aid] <= 0:
                pos_qty[aid] = Decimal("0")
                pos_cost[aid] = Decimal("0")

    rows: List[PerfRow] = []
    total_cost = Decimal("0")
    total_market = Decimal("0")
    total_realized = Decimal("0")  # ✅
    tmp: List[Tuple[PerfRow, Decimal]] = []

    for aid in asset_ids:
        a = asset_by_id[aid]
        qty = pos_qty.get(aid, Decimal("0"))
        cost_total = pos_cost.get(aid, Decimal("0"))
        if qty <= 0:
            continue

        avg_cost = (cost_total / qty) if qty > 0 else Decimal("0")
        mkt_price = _d0(a.last_price)

        market_total = qty * mkt_price
        pnl = market_total - cost_total
        pnl_pct = (pnl / cost_total * Decimal("100")) if cost_total > 0 else Decimal("0")

        pru = _quant2(avg_cost)
        price = _quant2(mkt_price)
        unit_diff = _quant2(price - pru)

        row = PerfRow(
            asset_id=aid,
            ticker=a.ticker,
            sector=(a.sector or "—"),
            qty=qty,
            avg_cost=_quant2(avg_cost),
            mkt_price=_quant2(mkt_price),
            cost_total=_quant2(cost_total),
            market_total=_quant2(market_total),
            pru=pru,
            price=price,
            unit_diff=unit_diff,
            pnl=_quant2(pnl),
            pnl_pct=pnl_pct.quantize(Decimal("0.1")),
            bar_pct=0,
            is_neg=(pnl < 0),
        )

        tmp.append((row, abs(pnl_pct)))
        total_cost += cost_total
        total_market += market_total
        total_realized += realized.get(aid, Decimal("0"))  # ✅

    max_abs_pct = max((x[1] for x in tmp), default=Decimal("0"))
    if max_abs_pct <= 0:
        max_abs_pct = Decimal("1")

    for row, abs_pct in tmp:
        bar = int((abs_pct / max_abs_pct * Decimal("100")).quantize(Decimal("1")))
        row.bar_pct = max(4, min(100, bar))
        rows.append(row)

    total_pnl = total_market - total_cost  # latent total
    total_pnl_pct = (total_pnl / total_cost * Decimal("100")) if total_cost > 0 else Decimal("0")

    # donut unchanged...
    sector_totals: Dict[str, Decimal] = {}
    for r in rows:
        sector_totals[r.sector] = sector_totals.get(r.sector, Decimal("0")) + r.market_total

    sector_items = []
    sector_total = sum(sector_totals.values(), Decimal("0"))
    palette = ["#4EC1B6", "#8B5CF6", "#F59E0B", "#60A5FA", "#F472B6", "#34D399", "#A3A3A3"]

    running = Decimal("0")
    grad_parts = []
    for i, (sector, val) in enumerate(sorted(sector_totals.items(), key=lambda kv: kv[1], reverse=True)):
        pct = (val / sector_total * Decimal("100")) if sector_total > 0 else Decimal("0")
        color = palette[i % len(palette)]
        start = running
        end = running + pct
        running = end
        grad_parts.append(f"{color} {start:.4f}% {end:.4f}%")
        sector_items.append(
            {"name": sector, "value": _quant2(val), "pct": pct.quantize(Decimal("0.1")), "color": color}
        )

    donut_bg = "conic-gradient(" + ", ".join(grad_parts) + ")" if grad_parts else "none"

    return {
        "asof": timezone.localtime(timezone.now()).strftime("%Y-%m-%d %H:%M"),
        "rows": rows,
        "total_cost": _quant2(total_cost),
        "total_market": _quant2(total_market),
        "total_pnl": _quant2(total_pnl),  # latent
        "total_pnl_pct": total_pnl_pct.quantize(Decimal("0.1")),
        "total_realized": _quant2(total_realized),  # ✅ ajouté
        "sectors": sector_items,
        "donut_bg": donut_bg,
    }

# =========================
# Holdings helper (SELL validation)
# =========================
def _shares_held_now(user, asset_id: int) -> Decimal:
    qty = Decimal("0")
    txs = (
        Transaction.objects.filter(asset_id=asset_id, asset__user=user)
        .only("type", "quantity", "date", "id")
        .order_by("date", "id")
    )
    for t in txs:
        q = _d0(t.quantity)
        if t.type == Transaction.BUY:
            qty += q
        elif t.type == Transaction.SELL:
            qty -= q
    return max(qty, Decimal("0"))


# =========================
# Views
# =========================
@login_required
def dividends_dashboard(request):
    today = timezone.localdate()
    year = _get_int(request, "y", today.year)
    growth = _get_decimal(request, "g", "0")

    events = build_year_events(request.user, year, growth_pct=growth)
    hist_months, hist_total, _ = year_histogram(events, year)

    perf = _build_perf_snapshot(request.user)

    div = _build_dividend_breakdown(events, year)
    y_cost = _pct(_safe_div(_d0(div["div_total"]), _d0(perf["total_cost"]))).quantize(Decimal("0.1"))
    y_market = _pct(_safe_div(_d0(div["div_total"]), _d0(perf["total_market"]))).quantize(Decimal("0.1"))
    pnl_vs_received = _money(_d0(perf["total_pnl"]) + _d0(div["div_received"]))
    finance = {**div, "yield_cost_pct": y_cost, "yield_market_pct": y_market, "pnl_vs_received": pnl_vs_received}

    universe = universe_choices()
    active_assets = Asset.objects.filter(user=request.user, is_active=True).only("ticker", "symbol").order_by("ticker")

    # ✅ SELL choices = uniquement les positions détenues (qty > 0)
    # On mappe UniverseItem par ticker ET par symbol (au cas où tu as des restes en DB)
    u_by_ticker = {it.ticker: it for it in universe}
    u_by_symbol = {it.symbol: it for it in universe}

    sell_choices = []
    for r in perf["rows"]:
        it = u_by_ticker.get(r.ticker) or u_by_symbol.get(r.ticker)
        sell_choices.append(
            {
                "key": (it.key if it else ""),
                "label": (f"{it.label} — {it.ticker}" if it else r.ticker),
                "ticker": r.ticker,
                "qty": r.qty,
            }
        )

    return render(
        request,
        "dividends/dividends_dashboard.html",
        {
            "today": today,
            "hist_year": year,
            "growth": growth,
            "hist_months": hist_months,
            "hist_total": hist_total,
            "prev_y": year - 1,
            "next_y": year + 1,
            "perf": perf,
            "finance": finance,
            "universe": universe,
            "active_assets": active_assets,
            "sell_choices": sell_choices,
        },
    )


@login_required
def dividends_calendar(request):
    today = timezone.localdate()
    year = _get_int(request, "y", today.year)
    month = _get_int(request, "m", today.month)
    growth = _get_decimal(request, "g", "0")

    events_year = build_year_events(request.user, year, growth_pct=growth)

    start = date(year, month, 1)
    end = date(year + (month == 12), 1 if month == 12 else month + 1, 1)

    events_month = [e for e in events_year if start <= e.display_date < end]
    month_total_estimated = sum((e.estimated_amount for e in events_month), Decimal("0.00"))

    grid = month_grid(year, month, events_month)

    prev_y, prev_m = (year - 1, 12) if month == 1 else (year, month - 1)
    next_y, next_m = (year + 1, 1) if month == 12 else (year, month + 1)

    return render(
        request,
        "dividends/calendar.html",
        {
            "grid": grid,
            "year": year,
            "month": month,
            "today": today,
            "growth": growth,
            "prev_y": prev_y,
            "prev_m": prev_m,
            "next_y": next_y,
            "next_m": next_m,
            "month_total_estimated": month_total_estimated,
        },
    )


@login_required
def portfolio(request):
    return redirect("dividends-dashboard")


@login_required
@require_GET
def api_month_details(request):
    try:
        y = int(request.GET.get("y"))
        m = int(request.GET.get("m"))
    except (TypeError, ValueError):
        return JsonResponse({"ok": False, "error": "bad params"}, status=400)

    growth = _get_decimal(request, "g", "0")

    events = build_year_events(request.user, y, growth_pct=growth)
    month_events = [e for e in events if e.display_date.year == y and e.display_date.month == m]

    payload = []
    for e in month_events:
        payload.append(
            {
                "ticker": e.ticker,
                "status": e.status,
                "ex_date": e.ex_date.isoformat(),
                "pay_date": e.pay_date.isoformat() if e.pay_date else None,
                "amount_per_share": str(e.amount_per_share),
                "shares": str(e.shares),
                "amount": str(e.estimated_amount),
                "currency": e.currency or "EUR",
            }
        )

    total = sum((Decimal(item["amount"]) for item in payload), Decimal("0.00"))
    return JsonResponse({"ok": True, "year": y, "month": m, "total": str(total), "count": len(payload), "events": payload})


# =========================
# Universe: add/remove asset
# =========================
@login_required
@require_POST
def toggle_asset_from_universe(request):
    action = (request.POST.get("action") or "add").strip().lower()
    key = (request.POST.get("universe_key") or "").strip().lower()

    item = UNIVERSE.get(key)
    if not item:
        messages.error(request, "Instrument inconnu.")
        return _redirect_dashboard_with_qs(request)

    asset, _created = Asset.objects.get_or_create(
        user=request.user,
        ticker=item.ticker,
        defaults={
            "currency": getattr(item, "currency", "EUR"),
            "sector": getattr(item, "sector", "—"),
            "is_active": True,
        },
    )

    if action == "remove":
        asset.is_active = False
        asset.save(update_fields=["is_active"])
        messages.success(request, f"Retiré: {item.label} ({item.ticker})")
        return _redirect_dashboard_with_qs(request)

    # add / reactivate + coherence fields
    if not asset.is_active:
        asset.is_active = True

    changed = _apply_universe_to_asset(asset, item)
    # is_active peut avoir changé aussi
    asset.save()
    messages.success(request, f"Ajouté: {item.label} ({item.ticker})")
    return _redirect_dashboard_with_qs(request)


# =========================
# Universe: add BUY transaction
# =========================
@login_required
@require_POST
def add_buy_from_universe(request):
    key = (request.POST.get("universe_key") or "").strip().lower()
    qty = _dec(request.POST.get("qty"), "0")
    price = _dec(request.POST.get("price"), "0")
    d = _parse_date(request.POST.get("date") or "")

    if not key or key not in UNIVERSE:
        messages.error(request, "Instrument invalide.")
        return _redirect_dashboard_with_qs(request)
    if qty <= 0 or price <= 0:
        messages.error(request, "Quantité et prix doivent être > 0.")
        return _redirect_dashboard_with_qs(request)
    if not d:
        messages.error(request, "Date invalide (format: YYYY-MM-DD).")
        return _redirect_dashboard_with_qs(request)

    item = UNIVERSE[key]
    asset, _ = Asset.objects.get_or_create(
        user=request.user,
        ticker=item.ticker,
        defaults={
            "currency": getattr(item, "currency", "EUR"),
            "sector": getattr(item, "sector", "—"),
            "is_active": True,
        },
    )

    # reactivate + cohérence symbol/isin/ticker (pour sync_prices)
    if not asset.is_active:
        asset.is_active = True
    _apply_universe_to_asset(asset, item)
    asset.save()

    Transaction.objects.create(asset=asset, type=Transaction.BUY, date=d, quantity=qty, price=price)
    messages.success(request, f"Achat ajouté: {item.label} ({item.ticker}) — {qty} @ {price} le {d}")
    return _redirect_dashboard_with_qs(request)


# =========================
# Universe: add SELL transaction (oversell protection)
# =========================
@login_required
@require_POST
def add_sell_from_universe(request):
    key = (request.POST.get("universe_key") or "").strip().lower()
    qty = _dec(request.POST.get("qty"), "0")
    price = _dec(request.POST.get("price"), "0")
    d = _parse_date(request.POST.get("date") or "")

    if not key or key not in UNIVERSE:
        messages.error(request, "Instrument invalide.")
        return _redirect_dashboard_with_qs(request)
    if qty <= 0 or price <= 0:
        messages.error(request, "Quantité et prix doivent être > 0.")
        return _redirect_dashboard_with_qs(request)
    if not d:
        messages.error(request, "Date invalide (format: YYYY-MM-DD).")
        return _redirect_dashboard_with_qs(request)

    item = UNIVERSE[key]
    try:
        asset = Asset.objects.get(user=request.user, ticker=item.ticker)
    except Asset.DoesNotExist:
        messages.error(request, "Impossible de vendre : asset non trouvé.")
        return _redirect_dashboard_with_qs(request)

    # cohérence symbol/isin (utile si asset ancien)
    _apply_universe_to_asset(asset, item)
    if not asset.is_active:
        asset.is_active = True
    asset.save()

    held = _shares_held_now(request.user, asset.id)
    if qty > held:
        messages.error(request, f"Vente refusée : tu veux vendre {qty} mais tu ne détiens que {held}.")
        return _redirect_dashboard_with_qs(request)

    Transaction.objects.create(asset=asset, type=Transaction.SELL, date=d, quantity=qty, price=price)
    messages.success(request, f"Vente ajoutée: {item.label} ({item.ticker}) — {qty} @ {price} le {d}")
    return _redirect_dashboard_with_qs(request)

from collections import defaultdict
from decimal import Decimal
from dividends.models import Transaction

def realized_pnl_by_month(asset: Asset):
    txs = asset.transactions.all().order_by("date", "id")

    qty = Decimal("0")
    pmp = Decimal("0")
    realized_by_ym = defaultdict(lambda: Decimal("0"))

    for tx in txs:
        q = Decimal(tx.quantity)
        px = Decimal(tx.price)
        fees = Decimal(tx.fees or 0)

        if tx.type == Transaction.BUY:
            new_qty = qty + q
            total_cost = (qty * pmp) + (q * px) + fees
            qty = new_qty
            pmp = total_cost / qty

        else:  # SELL
            pnl = (px - pmp) * q - fees
            ym = tx.date.strftime("%Y-%m")
            realized_by_ym[ym] += pnl
            qty -= q
            if qty == 0:
                pmp = Decimal("0")

    return dict(realized_by_ym)





# dividends/views.py (ajoute en bas, ou où tu veux)
from decimal import Decimal
from collections import defaultdict

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone

from dividends.models import Asset
from dividends.services.pnl import compute_position, realized_pnl_by_month


def _q2(x: Decimal) -> Decimal:
    return (x or Decimal("0")).quantize(Decimal("0.01"))


@login_required
def portfolio_view(request):
    assets = (
        Asset.objects.filter(user=request.user, is_active=True)
        .only("id", "ticker", "sector", "currency", "last_price", "last_price_asof")
        .order_by("ticker")
    )

    rows = []
    totals = {
        "cost_basis": Decimal("0"),
        "market_value": Decimal("0"),
        "unrealized": Decimal("0"),
        "realized": Decimal("0"),
    }

    realized_months = defaultdict(lambda: Decimal("0"))

    for a in assets:
        pos = compute_position(a)
        if pos.qty <= 0:
            continue

        rows.append(
            {
                "id": a.id,
                "ticker": a.ticker,
                "sector": a.sector or "—",
                "qty": pos.qty,
                "pmp": _q2(pos.pmp),
                "last_price": _q2(Decimal(a.last_price or 0)),
                "cost_basis": _q2(pos.cost_basis),
                "market_value": _q2(pos.market_value),
                "unrealized": _q2(pos.unrealized_pnl),
                "realized": _q2(pos.realized_pnl),
            }
        )

        totals["cost_basis"] += pos.cost_basis
        totals["market_value"] += pos.market_value
        totals["unrealized"] += pos.unrealized_pnl
        totals["realized"] += pos.realized_pnl

        for ym, pnl in realized_pnl_by_month(a).items():
            realized_months[ym] += pnl

    # tri des mois
    months_sorted = sorted(realized_months.items(), key=lambda kv: kv[0])
    months_rows = [{"ym": ym, "pnl": _q2(pnl)} for ym, pnl in months_sorted]

    ctx = {
        "asof": timezone.localtime(timezone.now()).strftime("%Y-%m-%d %H:%M"),
        "rows": rows,
        "totals": {k: _q2(v) for k, v in totals.items()},
        "months_rows": months_rows,
    }
    return render(request, "dividends/portfolio.html", ctx)