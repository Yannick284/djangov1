from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
import calendar


# ---------- Dates helpers ----------

def month_start(d: date) -> date:
    return date(d.year, d.month, 1)


def add_months(d: date, n: int) -> date:
    """
    Ajoute n mois à une date (en conservant un jour valide).
    Utilisé par breakeven.py => DOIT exister ici.
    """
    y = d.year + (d.month - 1 + n) // 12
    m = (d.month - 1 + n) % 12 + 1
    last_day = calendar.monthrange(y, m)[1]
    day = min(d.day, last_day)
    return date(y, m, day)


def iter_months(start: date, end: date):
    """
    Itère sur les 1ers du mois entre start et end (inclus).
    """
    cur = month_start(start)
    last = month_start(end)
    while cur <= last:
        yield cur
        cur = add_months(cur, 1)


def days_in_month(d: date) -> int:
    return calendar.monthrange(d.year, d.month)[1]


def overlap_days_in_month(month_1st: date, start: date | None, end: date | None) -> int:
    """
    Nombre de jours couverts dans le mois month_1st (1er du mois),
    pour une période [start, end] (end inclus), prorata au jour.
    Si end est None => période ouverte.
    """
    month_first = month_1st
    month_last = date(month_1st.year, month_1st.month, days_in_month(month_1st))

    if start is None:
        start = month_first
    if end is None:
        end = month_last

    s = max(start, month_first)
    e = min(end, month_last)

    if e < s:
        return 0

    return (e - s).days + 1  # inclusif


# ---------- Cash helpers ----------

def rent_for_month(periods, m: date) -> tuple[Decimal, Decimal]:
    """
    Retourne (rent_hc, charges) pour le mois m.
    -> PRORATA si période démarre/termine au milieu du mois.
    """
    rent = Decimal("0")
    charges = Decimal("0")
    dim = Decimal(str(days_in_month(m)))

    for p in periods:
        # p.start_date, p.end_date (nullable), p.rent_hc, p.charges
        od = overlap_days_in_month(
            m,
            getattr(p, "start_date", None),
            getattr(p, "end_date", None),
        )
        if od == 0:
            continue

        ratio = Decimal(str(od)) / dim
        rent += Decimal(str(p.rent_hc)) * ratio
        charges += Decimal(str(p.charges)) * ratio

    return rent, charges


def expenses_for_month(expenses, m: date) -> Decimal:
    """
    Simple: somme des dépenses dont la date tombe dans le mois.
    (si tu as une logique plus avancée, garde ta version)
    """
    total = Decimal("0")
    for e in expenses:
        d = getattr(e, "date", None)
        if not d:
            continue
        if d.year == m.year and d.month == m.month:
            total += Decimal(str(getattr(e, "amount", 0)))
    return total


# ---------- Ledger builder (si tu l’utilises) ----------

@dataclass
class LedgerRow:
    month: date
    rent_hc: Decimal
    charges: Decimal
    expenses: Decimal
    loan_payment: Decimal
    insurance: Decimal
    net_cashflow: Decimal
    cum_cashflow: Decimal


def build_ledger(prop, end_date: date):
    """
    Si tu utilises cette API, elle profite automatiquement du prorata rent_for_month.
    """
    periods = list(prop.rent_periods.order_by("start_date"))
    expenses = list(prop.expenses.all())

    # Loan (optionnel)
    loan = None
    try:
        loan = prop.loan
    except Exception:
        loan = None

    rows: list[LedgerRow] = []
    cum = Decimal("0")

    for m in iter_months(prop.purchase_date, end_date):
        r_hc, ch = rent_for_month(periods, m)
        exp = expenses_for_month(expenses, m)

        loan_payment = Decimal("0")
        insurance = Decimal("0")
        if loan and loan.start_date and month_start(loan.start_date) <= m:
            # ici: mensualité “constante” estimée côté services si tu veux,
            # sinon garde 0 et laisse summary faire le calcul via loan_schedule.
            insurance = Decimal(str(getattr(loan, "insurance_monthly", 0) or 0))

        net = (r_hc + ch) - exp - loan_payment - insurance
        cum += net

        rows.append(
            LedgerRow(
                month=m,
                rent_hc=r_hc,
                charges=ch,
                expenses=exp,
                loan_payment=loan_payment,
                insurance=insurance,
                net_cashflow=net,
                cum_cashflow=cum,
            )
        )

    return rows