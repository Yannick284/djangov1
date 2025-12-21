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
    y = d.year + (d.month - 1 + months) // 12
    m = (d.month - 1 + months) % 12 + 1
    return date(y, m, 1)


def iter_months(start: date, end: date):
    cur = month_start(start)
    last = month_start(end)
    while cur <= last:
        yield cur
        cur = add_months(cur, 1)


def monthly_payment(capital: Decimal, annual_rate: Decimal, years: int) -> Decimal:
    t = (annual_rate / Decimal("100")) / Decimal("12")
    n = years * 12
    if t == 0:
        return _q(capital / Decimal(n))
    m = capital * t / (Decimal("1") - (Decimal("1") + t) ** Decimal(-n))
    return _q(m)


def rent_for_month(periods: list[RentPeriod], m: date) -> tuple[Decimal, Decimal]:
    # retourne (rent_hc, charges) du mois
    for p in periods:
        if p.start_date <= m and (p.end_date is None or m <= month_start(p.end_date)):
            return (Decimal(p.rent_hc), Decimal(p.charges))
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
    # data
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

    start = prop.purchase_date
    for m in iter_months(start, end_date):
        r_hc, ch = rent_for_month(periods, m)
        r_hc = _q(Decimal(r_hc))
        ch = _q(Decimal(ch))

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
                rent_hc=r_hc,
                charges=ch,
                expenses=exp,
                loan_payment=_q(lp),
                insurance=_q(ins),
                net_cashflow=net,
                cum_cashflow=cum,
            )
        )

    return rows