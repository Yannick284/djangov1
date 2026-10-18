"""Retrouver un instrument : dictionnaire intégré, titre déjà suivi, ou ticker libre (Yahoo)."""
from __future__ import annotations

import re
from typing import Optional, Tuple

from dividends.models import Asset
from dividends.services.prices import guess_currency, lookup_instrument
from dividends.services.universe import UNIVERSE, UniverseItem

# Lettres, chiffres, point, tiret, ^ et = (ex. KO, TTE.PA, BRK-B, ^FCHI, EURUSD=X)
TICKER_RE = re.compile(r"^[A-Z0-9][A-Z0-9.\-^=]{0,19}$")


def item_from_asset(asset: Asset) -> UniverseItem:
    return UniverseItem(
        key=asset.ticker.lower(),
        label=asset.name or asset.ticker,
        ticker=asset.ticker,
        symbol=asset.price_symbol or asset.ticker,
        isin=asset.isin or "",
        kind=asset.asset_type or "stock",
        currency=asset.currency or "EUR",
        sector=asset.sector or "—",
    )


def find_known_item(user, ref: str) -> Optional[UniverseItem]:
    """Cherche par clé, ticker, symbole ou ISIN : d'abord le dictionnaire, puis les titres déjà suivis."""
    ref = (ref or "").strip()
    if not ref:
        return None
    low, up = ref.lower(), ref.upper()
    if low in UNIVERSE:
        return UNIVERSE[low]
    for it in UNIVERSE.values():
        if it.ticker.upper() == up or it.symbol.upper() == up or (it.isin and it.isin.upper() == up):
            return it
    asset = (
        Asset.objects.filter(user=user, ticker__iexact=ref).first()
        or Asset.objects.filter(user=user, price_symbol__iexact=ref).first()
        or (Asset.objects.filter(user=user, isin__iexact=ref).first() if len(ref) == 12 else None)
    )
    return item_from_asset(asset) if asset else None


def resolve_item(user, key: str = "", custom: str = "", verify: bool = True) -> Tuple[Optional[UniverseItem], str]:
    """
    Renvoie (instrument, message d'erreur). Priorité au ticker libre s'il est rempli.
    verify=False : ne contacte pas Yahoo (import de fichier) et déduit la devise du suffixe.
    """
    custom = (custom or "").strip().upper()
    if custom:
        if not TICKER_RE.match(custom):
            return None, "Ticker invalide : utilise le symbole Yahoo Finance (ex. KO, TTE.PA, BRK-B)."
        known = find_known_item(user, custom)
        if known:
            return known, ""
        if verify:
            info = lookup_instrument(custom)
            if not info:
                return None, f"Ticker introuvable chez Yahoo Finance : {custom}."
            currency = info["currency"]
        else:
            currency = guess_currency(custom)
        return UniverseItem(key=custom.lower(), label=custom, ticker=custom, symbol=custom, currency=currency), ""

    item = find_known_item(user, key)
    if not item:
        return None, "Instrument inconnu."
    return item, ""
