"""Import CSV de transactions (achats / ventes) depuis un fichier de courtier ou un tableur."""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Dict, List

from django.db import transaction as db_transaction

from dividends.models import Asset, Transaction
from dividends.services.instruments import resolve_item

MAX_BYTES = 1_000_000
MAX_ROWS = 5000

# Noms de colonnes acceptés (insensible à la casse et aux accents), français et anglais
HEADERS = {
    "date": {"date", "date operation", "date opération", "date de l'operation", "date de l'opération"},
    "type": {"type", "sens", "operation", "opération", "side"},
    "ticker": {"ticker", "symbole", "symbol", "isin", "code", "valeur", "titre"},
    "quantity": {"quantite", "quantité", "qty", "quantity", "nombre", "nb"},
    "price": {"prix", "price", "cours", "prix unitaire", "prix d'execution", "prix d'exécution"},
    "fees": {"frais", "fees", "commission", "commissions"},
}
BUY_WORDS = {"achat", "buy", "a", "b", "acquisition", "souscription"}
SELL_WORDS = {"vente", "sell", "v", "s", "cession"}

TEMPLATE_CSV = (
    "date;type;ticker;quantite;prix;frais\r\n"
    "2024-03-15;achat;SAN.PA;10;92,50;1,90\r\n"
    "2024-09-02;achat;KO;5;61,20;0\r\n"
    "2025-01-20;vente;SAN.PA;4;95,10;1,90\r\n"
)


@dataclass
class ImportResult:
    created: int = 0
    skipped_duplicates: int = 0
    errors: List[str] = field(default_factory=list)
    new_assets: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def _norm(s: str) -> str:
    return (s or "").strip().strip("﻿").lower()


def _dec(raw: str) -> Decimal:
    s = (raw or "").strip().replace(" ", "").replace(" ", "")
    if "," in s and "." in s:  # 1.234,56 ou 1,234.56 : le dernier séparateur est le décimal
        s = s.replace(".", "").replace(",", ".") if s.rfind(",") > s.rfind(".") else s.replace(",", "")
    else:
        s = s.replace(",", ".")
    return Decimal(s)


def _date(raw: str) -> date:
    s = (raw or "").strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"date illisible « {s} » (attendu : AAAA-MM-JJ ou JJ/MM/AAAA)")


def parse_rows(content: bytes) -> tuple[list[dict], list[str]]:
    """Lit le CSV et renvoie (lignes normalisées, erreurs de structure)."""
    if len(content) > MAX_BYTES:
        return [], ["Fichier trop volumineux (1 Mo maximum)."]
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = content.decode("latin-1")

    sample = text[:2000]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=";,\t")
    except csv.Error:
        class dialect(csv.excel):  # noqa: N801 (classe locale : ne pas modifier csv.excel lui-même)
            delimiter = ";"
    reader = csv.reader(io.StringIO(text), dialect)
    rows = [r for r in reader if any(c.strip() for c in r)]
    if not rows:
        return [], ["Le fichier est vide."]

    header = [_norm(h) for h in rows[0]]
    index: Dict[str, int] = {}
    for key, names in HEADERS.items():
        for i, h in enumerate(header):
            if h in names:
                index.setdefault(key, i)
    missing = [k for k in ("date", "type", "ticker", "quantity", "price") if k not in index]
    if missing:
        labels = {"date": "date", "type": "type", "ticker": "ticker", "quantity": "quantité", "price": "prix"}
        return [], ["Colonnes manquantes : " + ", ".join(labels[m] for m in missing) + ". Utilise le modèle proposé."]
    if len(rows) - 1 > MAX_ROWS:
        return [], [f"Trop de lignes ({MAX_ROWS} maximum)."]

    out = []
    for n, r in enumerate(rows[1:], start=2):
        def cell(k):
            i = index.get(k)
            return r[i].strip() if i is not None and i < len(r) else ""
        out.append({"line": n, **{k: cell(k) for k in HEADERS}})
    return out, []


def import_transactions(user, content: bytes) -> ImportResult:
    """Tout ou rien : si une ligne est invalide, rien n'est enregistré."""
    result = ImportResult()
    rows, errors = parse_rows(content)
    if errors:
        result.errors = errors
        return result

    parsed = []
    for r in rows:
        try:
            d = _date(r["date"])
            word = _norm(r["type"])
            if word in BUY_WORDS:
                kind = Transaction.BUY
            elif word in SELL_WORDS:
                kind = Transaction.SELL
            else:
                raise ValueError(f"type « {r['type']} » inconnu (achat ou vente)")
            qty, price = _dec(r["quantity"]), _dec(r["price"])
            fees = _dec(r["fees"]) if r["fees"] else Decimal("0")
            if qty <= 0 or price <= 0 or fees < 0:
                raise ValueError("quantité et prix doivent être positifs")
            item, err = resolve_item(user, custom=r["ticker"].upper(), verify=False)
            if not item:
                raise ValueError(err or "instrument inconnu")
            parsed.append((r["line"], d, kind, qty, price, fees, item))
        except (ValueError, InvalidOperation) as e:
            result.errors.append(f"Ligne {r['line']} : {e}")

    if result.errors:
        return result

    parsed.sort(key=lambda p: (p[1], p[0]))

    with db_transaction.atomic():
        assets: Dict[str, Asset] = {}
        held: Dict[str, Decimal] = {}
        for line, d, kind, qty, price, fees, item in parsed:
            asset = assets.get(item.ticker)
            if asset is None:
                asset, created = Asset.objects.get_or_create(
                    user=user,
                    ticker=item.ticker,
                    defaults={"currency": item.currency, "sector": item.sector, "isin": item.isin, "price_symbol": item.symbol, "is_active": True},
                )
                if not asset.is_active:
                    asset.is_active = True
                    asset.save(update_fields=["is_active"])
                if created:
                    result.new_assets.append(item.ticker)
                assets[item.ticker] = asset
                held[item.ticker] = sum(
                    (t.quantity if t.type == Transaction.BUY else -t.quantity for t in asset.transactions.all()),
                    Decimal("0"),
                )

            if Transaction.objects.filter(asset=asset, date=d, type=kind, quantity=qty, price=price).exists():
                result.skipped_duplicates += 1
                continue

            if kind == Transaction.SELL and qty > held[item.ticker]:
                result.errors.append(f"Ligne {line} : vente de {qty} {item.ticker} alors que tu n'en détiens que {held[item.ticker]}.")
                continue

            Transaction.objects.create(asset=asset, type=kind, date=d, quantity=qty, price=price, fees=fees)
            held[item.ticker] += qty if kind == Transaction.BUY else -qty
            result.created += 1

        if result.errors:
            db_transaction.set_rollback(True)
            result.created = 0
            result.new_assets = []
    return result
