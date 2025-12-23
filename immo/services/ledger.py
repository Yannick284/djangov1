from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
import calendar

from ..models import Property, Expense, RentPeriod, Loan


import calendar
from datetime import date

def month_start(d: date) -> date:
    return d.replace(day=1)

def add_months(d: date, months: int) -> date:
    y = d.year + (d.month - 1 + months) // 12
    m = (d.month - 1 + months) % 12 + 1
    last_day = calendar.monthrange(y, m)[1]
    day = min(d.day, last_day)
    return date(y, m, day)

TWOPLACES = Decimal("0.01")


def _q(x: Decimal) -> Decimal:
    return x.quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def month_start(d: date) -> date:
    return date(d.year, d.month, 1)


def month_end(d: date) -> date:
    last_day = calendar.monthrange(d.year, d.month)[1]
    return date(d.year, d.month, last_day)


def iter_months(start: date, end: date):
    """Yield month starts from start..end inclusive (by month)."""
    m = month_start(start)
    end_m = month_start(end)
    while m <= end_m:
        yield m
        if m.month == 12:
            m = date(m.year + 1, 1, 1)
        else:
            m = date(m.year, m.month + 1, 1)


def _days_in_month(m: date) -> int:
    return calendar.monthrange(m.year, m.month)[1]


def _overlap_days(a_start: date, a_end: date, b_start: date, b_end: date) -> int:
    start = max(a_start, b_start)
    end = min(a_end, b_end)
    if end < start:
        return 0
    return (end - start).days + 1  # inclusive


def rent_for_month(periods: list[RentPeriod], m: date) -> tuple[Decimal, Decimal]:
    """
    Prorata journalier :
    - si le bail démarre le 13/10 => octobre = (nb jours du 13..31) / (nb jours du mois) * loyer
    - si fin en cours de mois => prorata pareil
    - si plusieurs periods se chevauchent (rare) => on somme les overlaps
    """
    m_start = month_start(m)
    m_end = month_end(m)
    total_days = Decimal(_days_in_month(m_start))

    rent = Decimal("0")
    charges = Decimal("0")

    for p in periods:
        p_start = p.start_date
        p_end = p.end_date or date.max

        days = _overlap_days(p_start, p_end, m_start, m_end)
        if days <= 0:
            continue

        ratio = Decimal(days) / total_days
        rent += Decimal(p.rent_hc) * ratio
        charges += Decimal(p.charges) * ratio

    return _q(rent), _q(charges)


def expenses_for_month(expenses: list[Expense], m: date) -> Decimal:
    m_start = month_start(m)
    m_end = month_end(m)
    s = Decimal("0")
    for e in expenses:
        if m_start <= e.date <= m_end:
            s += Decimal(e.amount)
    return _q(s)


def _months_between(start: date, end: date) -> int:
    """Number of whole months between month starts (end exclusive-ish for term checks)."""
    s = month_start(start)
    e = month_start(end)
    return (e.year - s.year) * 12 + (e.month - s.month)


def _loan_monthly_payment(principal: Decimal, annual_rate_pct: Decimal, years: int) -> Decimal:
    """
    Standard annuity payment (hors assurance).
    annual_rate_pct ex: 1.400
    """
    n = years * 12
    if n <= 0:
        return Decimal("0")

    r = (annual_rate_pct / Decimal("100")) / Decimal("12")  # monthly rate
    if r == 0:
        return principal / Decimal(n)

    one_plus_r_n = (Decimal("1") + r) ** Decimal(n)
    pmt = principal * (r * one_plus_r_n) / (one_plus_r_n - Decimal("1"))
    return pmt


def loan_for_month(loan: Loan | None, m: date) -> tuple[Decimal, Decimal]:
    """
    Returns (monthly_payment_hors_assurance, insurance_monthly) for month m.
    If month outside loan term => 0.
    """
    if not loan:
        return Decimal("0"), Decimal("0")

    m0 = month_start(loan.start_date)
    mm = month_start(m)

    elapsed = _months_between(m0, mm)
    if elapsed < 0:
        return Decimal("0"), Decimal("0")

    term_months = int(loan.years) * 12
    if elapsed >= term_months:
        return Decimal("0"), Decimal("0")

    pmt = _loan_monthly_payment(
        principal=Decimal(loan.borrowed_capital),
        annual_rate_pct=Decimal(loan.annual_rate),
        years=int(loan.years),
    )
    ins = Decimal(loan.insurance_monthly or 0)
    return _q(pmt), _q(ins)


@dataclass(frozen=True)
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
    periods = list(prop.rent_periods.order_by("start_date"))
    expenses = list(prop.expenses.all())

    try:
        loan = prop.loan
    except Loan.DoesNotExist:
        loan = None

    rows: list[LedgerRow] = []
    cum = Decimal("0")

    for m in iter_months(prop.purchase_date, end_date):
        r_hc, ch = rent_for_month(periods, m)
        exp = expenses_for_month(expenses, m)

        lp, ins = loan_for_month(loan, m)

        net = _q((r_hc + ch) - exp - lp - ins)
        cum = _q(cum + net)

        rows.append(
            LedgerRow(
                month=m,
                rent_hc=r_hc,
                charges=ch,
                expenses=exp,
                loan_payment=lp,
                insurance=ins,
                net_cashflow=net,
                cum_cashflow=cum,
            )
        )

    return rows