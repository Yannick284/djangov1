"""Synchronisation des dividendes déclarés (par action) depuis Yahoo, pour un seul titre."""
from __future__ import annotations

from decimal import Decimal

from django.db import IntegrityError, transaction

from dividends.models import Asset, DividendEvent


def sync_asset_dividends(asset: Asset, years: int = 5) -> int:
    """Crée les DividendEvent manquants. Renvoie le nombre créé (0 si rien ou si Yahoo échoue)."""
    import yfinance as yf

    sym = (asset.price_symbol or asset.ticker or "").strip()
    if not sym:
        return 0
    try:
        series = yf.Ticker(sym).dividends
    except Exception:
        return 0
    if series is None or getattr(series, "empty", True):
        return 0

    created = 0
    for dt, amt in series.tail(years * 10).items():
        try:
            amount = Decimal(str(amt))
        except Exception:
            continue
        try:
            with transaction.atomic():
                _obj, was_created = DividendEvent.objects.get_or_create(
                    asset=asset,
                    ex_date=dt.date(),
                    amount_per_share=amount,
                    defaults={"currency": asset.currency or "EUR", "source": "yfinance", "status": "declared"},
                )
                created += int(was_created)
        except IntegrityError:
            continue
    return created
