from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
import calendar

from ..models import RentPeriod, Property


D0 = Decimal("0.00")


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


def month_start(d: date) -> date:
    return date(d.year, d.month, 1)


def add_months(d: date, n: int) -> date:
    y = d.year + (d.month - 1 + n) // 12
    m = (d.month - 1 + n) % 12 + 1
    return date(y, m, 1)


def iter_month_starts(start: date, end: date):
    cur = month_start(start)
    last = month_start(end)
    while cur <= last:
        yield cur
        cur = add_months(cur, 1)


def _days_in_month(m: date) -> int:
    return calendar.monthrange(m.year, m.month)[1]


def _overlap_days(a_start: date, a_end: date, b_start: date, b_end: date) -> int:
    start = max(a_start, b_start)
    end = min(a_end, b_end)
    if end < start:
        return 0
    return (end - start).days + 1  # inclusif


def rent_for_month(prop: Property, month: date) -> tuple[Decimal, Decimal]:
    """
    Retourne (rent_hc, charges) proratisés au jour près selon RentPeriod.
    Convention: si une période couvre partiellement un mois => prorata = (jours_couverts / jours_du_mois) * montant_mensuel
    """
    m0 = month_start(month)
    m_end = date(month.year, month.month, _days_in_month(month))

    rent = D0
    charges = D0

    qs = prop.rent_periods.all()  # related_name supposé "rent_periods"
    for rp in qs:
        sd = rp.start_date
        ed = rp.end_date or date(9999, 12, 31)

        # pas d'overlap => ignore
        days = _overlap_days(sd, ed, m0, m_end)
        if days <= 0:
            continue

        dim = Decimal(str(_days_in_month(month)))
        factor = Decimal(str(days)) / dim

        rent += (Decimal(rp.rent_hc) * factor)
        charges += (Decimal(rp.charges or 0) * factor)

    return (rent, charges)


def expenses_for_month(prop: Property, month: date) -> Decimal:
    # Si tu as un modèle de dépenses plus tard, tu brancheras ici.
    return D0


def loan_payment_for_month(prop: Property, month: date) -> tuple[Decimal, Decimal]:
    """
    Retourne (mensualité hors assurance, assurance).
    Ici: on prend ce que tu as dans Loan (estimation), sinon 0.
    """
    try:
        loan = prop.loan
    except Exception:
        return (D0, D0)

    # si le prêt commence après le mois => 0
    if loan.start_date and month_start(loan.start_date) > month_start(month):
        return (D0, D0)

    # si tu as déjà une fonction de calcul de mensualité ailleurs, remplace ici
    monthly = getattr(loan, "monthly_payment_est", None)
    if monthly is None:
        # fallback: si tu stockes pas la mensualité, mets 0 ici (ou calcule-la dans un service dédié)
        monthly = D0
    else:
        monthly = Decimal(str(monthly))

    insurance = Decimal(str(getattr(loan, "insurance_monthly", 0) or 0))
    return (monthly, insurance)


def build_ledger(prop: Property, end_date: date) -> list[LedgerRow]:
    rows: list[LedgerRow] = []
    cum = D0

    for m in iter_month_starts(prop.purchase_date, end_date):
        rent_hc, charges = rent_for_month(prop, m)
        expenses = expenses_for_month(prop, m)
        loan_payment, insurance = loan_payment_for_month(prop, m)

        net = rent_hc + charges - expenses - loan_payment - insurance
        cum += net

        rows.append(
            LedgerRow(
                month=m,
                rent_hc=rent_hc,
                charges=charges,
                expenses=expenses,
                loan_payment=loan_payment,
                insurance=insurance,
                net_cashflow=net,
                cum_cashflow=cum,
            )
        )

    return rows