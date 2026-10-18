# dividends/services/universe.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class UniverseItem:
    key: str                 # clé interne stable
    label: str               # nom affiché
    ticker: str              # affichage court (souvent Yahoo sans surprise)
    symbol: str              # symbole pricing (Yahoo / provider) -> EX: SAN.PA
    isin: str = ""           # optionnel (mais recommandé)
    kind: str = "stock"      # "stock" | "etf"
    currency: str = "EUR"
    country: str = "FR"
    exchange: str = "XPAR"   # Euronext Paris par défaut
    sector: str = "—"


def _k(s: str) -> str:
    return s.strip().lower()


def universe_choices() -> List[UniverseItem]:
    """
    Retourne une liste triée pour affichage (actions puis ETFs).
    """
    items = list(UNIVERSE.values())
    items.sort(key=lambda x: (x.kind, x.label))
    return items


# ---------------------------------------------------------------------
# UNIVERSE
# - ticker/symbol: pour ton pricing provider, mets YAHOO style: xxx.PA
# - ISIN: laisse vide si tu ne l’as pas (ça ne casse rien)
# ---------------------------------------------------------------------
UNIVERSE: Dict[str, UniverseItem] = {}

def _add(
    label: str,
    symbol: str,
    isin: str = "",
    kind: str = "stock",
    sector: str = "—",
    currency: str = "EUR",
    country: str = "FR",
    exchange: str = "XPAR",
    key: str | None = None,
):
    sym = symbol.strip()
    k = _k(key or sym)
    UNIVERSE[k] = UniverseItem(
        key=k,
        label=label.strip(),
        ticker=sym,
        symbol=sym,
        isin=isin.strip(),
        kind=kind,
        currency=currency,
        country=country,
        exchange=exchange,
        sector=sector,
    )

# =========================
# CAC 40 (et gros Euronext Paris) – symbols Yahoo ".PA"
# =========================
_add("Accor", "AC.PA", isin="", sector="Travel & Leisure")
_add("Air Liquide", "AI.PA", isin="FR0000120073", sector="Chemicals")
_add("Airbus", "AIR.PA", isin="", sector="Aerospace & Defense")
_add("Axa", "CS.PA", isin="", sector="Insurance")
_add("BNP Paribas", "BNP.PA", isin="", sector="Banks")
_add("Bouygues", "EN.PA", isin="", sector="Industrials")
_add("Capgemini", "CAP.PA", isin="", sector="IT Services")
_add("Carrefour", "CA.PA", isin="", sector="Retail")
_add("Crédit Agricole", "ACA.PA", isin="", sector="Banks")
_add("Danone", "BN.PA", isin="", sector="Food & Beverage")
_add("Dassault Systèmes", "DSY.PA", isin="", sector="Software")
_add("Engie", "ENGI.PA", isin="", sector="Utilities")
_add("EssilorLuxottica", "EL.PA", isin="", sector="Healthcare")
_add("Eurofins Scientific", "ERF.PA", isin="", sector="Healthcare")
_add("Hermès", "RMS.PA", isin="", sector="Luxury")
_add("Kering", "KER.PA", isin="", sector="Luxury")
_add("Legrand", "LR.PA", isin="", sector="Industrials")
_add("L'Oréal", "OR.PA", isin="", sector="Consumer")
_add("LVMH", "MC.PA", isin="", sector="Luxury")
_add("Michelin", "ML.PA", isin="", sector="Automotive")
_add("Orange", "ORA.PA", isin="", sector="Telecom")
_add("Pernod Ricard", "RI.PA", isin="", sector="Beverages")
_add("Publicis", "PUB.PA", isin="", sector="Media")
_add("Renault", "RNO.PA", isin="", sector="Automotive")
_add("Safran", "SAF.PA", isin="", sector="Aerospace & Defense")
_add("Saint-Gobain", "SGO.PA", isin="", sector="Materials")
_add("Sanofi", "SAN.PA", isin="FR0000120578", sector="Pharma")
_add("Schneider Electric", "SU.PA", isin="", sector="Industrials")
_add("Société Générale", "GLE.PA", isin="", sector="Banks")
_add("Stellantis", "STLAP.PA", isin="", sector="Automotive")
_add("STMicroelectronics", "STMPA.PA", isin="", sector="Semiconductors")
_add("Teleperformance", "TEP.PA", isin="", sector="Business Services")
_add("Thales", "HO.PA", isin="", sector="Defense")
_add("TotalEnergies", "TTE.PA", isin="", sector="Energy")
_add("Unibail-Rodamco-Westfield", "URW.PA", isin="", sector="Real Estate")
_add("Veolia", "VIE.PA", isin="", sector="Utilities")
_add("Vinci", "DG.PA", isin="", sector="Industrials")
_add("Worldline", "WLN.PA", isin="", sector="Payments")

# Quelques grosses FR / Euronext utiles
_add("Alstom", "ALO.PA", isin="", sector="Industrials")
_add("Edenred", "EDEN.PA", isin="", sector="Payments")
_add("Eramet", "ERA.PA", isin="", sector="Materials")
_add("Getlink", "GET.PA", isin="", sector="Industrials")
_add("Rexel", "RXL.PA", isin="", sector="Industrials")
_add("Sodexo", "SW.PA", isin="", sector="Services")
_add("TF1", "TFI.PA", isin="", sector="Media")
_add("Ubisoft", "UBI.PA", isin="", sector="Gaming")

# =========================
# ETFs (focus PEA + gros ETFs Europe)
# Note: beaucoup ont un ticker Yahoo ".PA" (Euronext Paris)
# =========================
# MSCI World PEA (très utilisé)
_add("Amundi MSCI World (PEA)", "CW8.PA", isin="FR0011869353", kind="etf", sector="ETF — World")
_add("Amundi MSCI World (PEA) - (alt)", "EWLD.PA", isin="FR0011869304", kind="etf", sector="ETF — World")

# S&P 500 / Nasdaq PEA
_add("Amundi PEA S&P 500", "500.PA", isin="FR0013412285", kind="etf", sector="ETF — US")
_add("Amundi PEA Nasdaq-100", "PANX.PA", isin="", kind="etf", sector="ETF — US Tech")

# Europe / Zone Euro
_add("Amundi Stoxx Europe 600", "MEUD.PA", isin="", kind="etf", sector="ETF — Europe")
_add("Amundi Euro Stoxx 50", "C50.PA", isin="", kind="etf", sector="ETF — Eurozone")
_add("Lyxor Euro Stoxx 50 (PEA)", "MSE.PA", isin="", kind="etf", sector="ETF — Eurozone")

# Emerging Markets (souvent hors PEA, mais utile)
_add("iShares Core MSCI EM IMI", "EIMI.L", isin="IE00BKM4GZ66", kind="etf", sector="ETF — EM", currency="USD", country="IE", exchange="XLON")
_add("Vanguard FTSE EM", "VFEM.L", isin="IE00B3VVMM84", kind="etf", sector="ETF — EM", currency="USD", country="IE", exchange="XLON")

# Small caps / facteurs
_add("Amundi MSCI Europe Small Cap", "ESE.PA", isin="", kind="etf", sector="ETF — Europe Small")
_add("Amundi MSCI World Momentum", "WDMO.PA", isin="", kind="etf", sector="ETF — Factor")

# Thématiques (optionnel)
_add("Amundi Global Clean Energy", "CLIM.PA", isin="", kind="etf", sector="ETF — Thematic")
_add("Amundi Global Water", "CWEA.PA", isin="", kind="etf", sector="ETF — Thematic")

# Obligataires (si tu veux)
_add("Amundi Euro Govt Bond 1-3", "E13.PA", isin="", kind="etf", sector="ETF — Bonds")
_add("Amundi Euro Corp Bond", "ECRP.PA", isin="", kind="etf", sector="ETF — Bonds")

# Or (souvent ETC, pas ETF UCITS, mais demandé parfois)
_add("Gold (ETC) - Xetra", "4GLD.DE", isin="", kind="etf", sector="ETC — Gold", currency="EUR", country="DE", exchange="XETRA")

# =========================
# US Mega caps (si tu veux suivre en watchlist)
# (pas Euronext, mais Yahoo symbol OK)
# =========================
_add("Apple", "AAPL", isin="US0378331005", kind="stock", sector="US Tech", currency="USD", country="US", exchange="NASDAQ")
_add("Microsoft", "MSFT", isin="US5949181045", kind="stock", sector="US Tech", currency="USD", country="US", exchange="NASDAQ")
_add("NVIDIA", "NVDA", isin="US67066G1040", kind="stock", sector="US Tech", currency="USD", country="US", exchange="NASDAQ")
_add("Amazon", "AMZN", isin="US0231351067", kind="stock", sector="US Consumer", currency="USD", country="US", exchange="NASDAQ")
_add("Meta", "META", isin="US30303M1027", kind="stock", sector="US Tech", currency="USD", country="US", exchange="NASDAQ")
_add("Alphabet (A)", "GOOGL", isin="US02079K3059", kind="stock", sector="US Tech", currency="USD", country="US", exchange="NASDAQ")
_add("Tesla", "TSLA", isin="US88160R1014", kind="stock", sector="US Auto", currency="USD", country="US", exchange="NASDAQ")