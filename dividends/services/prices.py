from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from datetime import datetime
from django.utils import timezone

import yfinance as yf


@dataclass
class PriceQuote:
    symbol: str
    price: Decimal
    asof: datetime
    source: str


def get_quote(symbol: str) -> PriceQuote | None:
    """
    Source unique et stable pour récupérer un prix.
    Yahoo via yfinance (gère cookies/consent mieux que requests).
    """
    symbol = (symbol or "").strip()
    if not symbol:
        return None

    t = yf.Ticker(symbol)
    hist = t.history(period="7d")  # marge (week-end / jours fériés)
    if hist is None or hist.empty:
        return None

    close = hist["Close"].dropna()
    if close.empty:
        return None

    price = Decimal(str(close.iloc[-1]))
    if price <= 0:
        return None

    return PriceQuote(symbol=symbol, price=price, asof=timezone.now(), source="yfinance")


def update_asset_price(asset) -> bool:
    sym = (getattr(asset, "price_symbol", "") or "").strip()
    if not sym:
        return False

    q = get_quote(sym)
    if not q:
        return False

    asset.last_price = q.price.quantize(Decimal("0.01"))  # 2 décimales
    asset.last_price_updated_at = q.asof
    asset.save(update_fields=["last_price", "last_price_asof"])
    return True