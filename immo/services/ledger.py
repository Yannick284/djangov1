from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
import calendar

from ..models import Property, Expense, RentPeriod, Loan


TWOPLACES = Decimal("0.01")


def _q(x: Decimal) -> Decimal:
    return x.quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def month_start(d: date) -> date:
    return date(d.year, d.month, 1)


def add_months(d: date, months: int) -> date:
    """
    Ajoute N mois à une date (en se plaçant au 1er du mois).
    """
    y = d.year + (d.month - 1 + months) // 12
    m = (d.month - 1 + months) % 12 + 1
    return date(y, m, 1)


def iter_months(start: date, end: date):
    """
    Génère: 2022-08-01, 2022-09-01, ... jusqu’à end (mois start).
    """
    cur = month_start(start)
    last = month_start(end)
    while cur <= last:
        yield cur
        cur = add_months(cur, 1)


def monthly_payment(capital: Decimal, annual_rate: Decimal, years: int) -> Decimal:
    """
    Mensualité “théorique” sans assurance.
    """
    t = (annual_rate / Decimal("100")) / Decimal("12")
    n = years * 12
    if t == 0:
        return _q(capital / Decimal(n))
    m = capital * t / (Decimal("1") - (Decimal("1") + t) ** Decimal(-n))
    return _q(m)


def _days_in_month(m: date) -> int:
    return calendar.monthrange(m.year, m.month)[1]


def rent_for_month(periods: list[RentPeriod], m: date) -> tuple[Decimal, Decimal]:
    """
    Retourne (rent_hc, charges) pour le mois m (m = 1er du mois).

    ✅ Prorata:
    - Si le bail commence le 13/10, alors pour Octobre on ne prend que 19 jours / 31 (ou 18 selon convention).
    - Même logique si end_date tombe au milieu du mois.
    """
    month_begin = month_start(m)
    month_end = add_months(month_begin, 1)  # 1er du mois suivant (borne exclue)
    dim = Decimal(_days_in_month(month_begin))

    for p in periods:
        # période active si chevauchement [month_begin, month_end)
        period_start = p.start_date
        period_end = (p.end_date if p.end_date else date.max)

        # si pas de chevauchement -> continue
        if period_end < month_begin or period_start >= month_end:
            continue

        # chevauchement effectif
        overlap_start = max(period_start, month_begin)
        overlap_end_excl = min(period_end, month_end)

        # nombre de jours inclus dans le mois
        days = (overlap_end_excl - overlap_start).days
        if days <= 0:
            continue

        frac = Decimal(days) / dim

        rent = Decimal(p.rent_hc) * frac
        ch = Decimal(p.charges) * frac
        return (_q(rent), _q(ch))

    return (Decimal("0"), Decimal("0"))


def expenses_for_month(expenses: list[Expense], m: date) -> Decimal:
    total = Decimal("0")
    for e in expenses:
        if e.date.year == m.year and e.date.month == m.month:
            total += Decimal(e.amount)
    return _q(total)


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


def build_ledger(prop: Property, end_date: date) -> list[LedgerRow]:
    """
    Ledger “comptable” mois par mois:
    - rent/charges (proratisés)
    - dépenses
    - mensualité prêt + assurance à partir de loan.start_date
    """
    periods = list(prop.rent_periods.order_by("start_date"))
    expenses = list(prop.expenses.all())

    loan_payment = Decimal("0")
    insurance = Decimal("0")
    loan_start = None

    try:
        loan: Loan = prop.loan
        loan_start = month_start(loan.start_date)
        loan_payment = monthly_payment(
            Decimal(loan.borrowed_capital),
            Decimal(loan.annual_rate),
            int(loan.years),
        )
        insurance = _q(Decimal(loan.insurance_monthly))
    except Loan.DoesNotExist:
        pass

    rows: list[LedgerRow] = []
    cum = Decimal("0")

    for m in iter_months(prop.purchase_date, end_date):
        r_hc, ch = rent_for_month(periods, m)
        exp = expenses_for_month(expenses, m)

        lp = Decimal("0")
        ins = Decimal("0")
        if loan_start and m >= loan_start:
            lp = loan_payment
            ins = insurance

        net = _q(r_hc + ch - exp - lp - ins)
        cum = _q(cum + net)

        rows.append(
            LedgerRow(
                month=m,
                rent_hc=_q(r_hc),
                charges=_q(ch),
                expenses=_q(exp),
                loan_payment=_q(lp),
                insurance=_q(ins),
                net_cashflow=net,
                cum_cashflow=cum,
            )
        )

    return rows