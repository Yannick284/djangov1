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
    asset.last_price_asof = q.asof
    asset.last_price_source = q.source
    asset.save(update_fields=["last_price", "last_price_asof", "last_price_source"])
    return True

EUR_SUFFIXES = (".PA", ".DE", ".AS", ".MI", ".MC", ".BR", ".LS", ".F", ".HE", ".VI", ".IR")


def guess_currency(symbol: str) -> str:
    """Devise probable d'après le suffixe de bourse Yahoo (utilisé quand Yahoo ne la donne pas)."""
    s = (symbol or "").upper()
    if s.endswith(EUR_SUFFIXES):
        return "EUR"
    if s.endswith(".L"):
        return "GBP"
    if s.endswith(".SW"):
        return "CHF"
    return "USD"


def lookup_instrument(symbol: str) -> dict | None:
    """
    Vérifie qu'un symbole existe chez Yahoo et renvoie {"price", "currency", "asof"}.
    Renvoie None si introuvable ou si Yahoo ne répond pas.
    """
    try:
        q = get_quote(symbol)
    except Exception:
        return None
    if not q:
        return None
    currency = ""
    try:
        currency = (yf.Ticker(symbol).fast_info.get("currency") or "").upper()
    except Exception:
        pass
    return {"price": q.price, "currency": currency or guess_currency(symbol), "asof": q.asof}
