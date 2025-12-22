from datetime import date
from decimal import Decimal

from ..models import Property, Loan
from .ledger import (
    iter_months,
    month_start,
    rent_for_month,
    expenses_for_month,
)
from .sale import net_vendeur
from .loan_schedule import balance_after_months


def months_between(start: date, end: date) -> int:
    s = month_start(start)
    e = month_start(end)
    return (e.year - s.year) * 12 + (e.month - s.month)


def property_summary(prop: Property, end_date: date):
    end_date = end_date or date.today()

    # ------------------------------------------------------------------
    # VALEUR DE MARCHÉ = DERNIER POINT DU GRAPHE × SURFACE (+ goodwill + parking)
    # ------------------------------------------------------------------
    mv_est = None
    last_m2 = None
    last_m2_date = None

    if prop.surface_sqm:
        last_point = (
            prop.market_points
            .filter(date__lte=end_date)
            .order_by("-date")
            .first()
        )

        if last_point:
            last_m2 = Decimal(last_point.price_per_sqm)
            last_m2_date = last_point.date

            goodwill = Decimal(prop.goodwill_eur_per_sqm or 0)
            parking = Decimal(prop.parking or 0)

            mv_est = (last_m2 + goodwill) * Decimal(prop.surface_sqm) + parking

    # ------------------------------------------------------------------
    # LOYERS / CHARGES / DÉPENSES
    # ------------------------------------------------------------------
    periods = list(prop.rent_periods.order_by("start_date"))
    expenses = list(prop.expenses.all())

    rent_total = Decimal("0")
    charges_total = Decimal("0")
    expenses_total = Decimal("0")

    for m in iter_months(prop.purchase_date, end_date):
        r_hc, ch = rent_for_month(periods, m)
        rent_total += Decimal(r_hc)
        charges_total += Decimal(ch)
        expenses_total += Decimal(expenses_for_month(expenses, m))

    # ------------------------------------------------------------------
    # PRÊT
    # ------------------------------------------------------------------
    loan_payment_total = Decimal("0")
    insurance_total = Decimal("0")
    capital_paid = Decimal("0")
    interest_paid = Decimal("0")
    crd_est = None
    m_payment = None

    try:
        loan: Loan = prop.loan
        n_months = months_between(loan.start_date, end_date)

        sched = balance_after_months(
            principal=Decimal(loan.borrowed_capital),
            annual_rate_pct=Decimal(loan.annual_rate),
            years=int(loan.years),
            months_elapsed=n_months,
        )

        m_payment = sched["payment"]
        loan_payment_total = m_payment * Decimal(n_months)
        insurance_total = Decimal(loan.insurance_monthly) * Decimal(n_months)

        crd_est = sched["crd"]
        capital_paid = sched["capital_paid"]
        interest_paid = sched["interest_paid"]

    except Loan.DoesNotExist:
        pass

    # ------------------------------------------------------------------
    # CASHFLOWS
    # ------------------------------------------------------------------
    cashflow_real = (
        (rent_total + charges_total)
        - expenses_total
        - loan_payment_total
        - insurance_total
    )

    cashflow_economic = cashflow_real + capital_paid
    cash_invested_real = -cashflow_real

    # ------------------------------------------------------------------
    # VENTE
    # ------------------------------------------------------------------
    sale_info = None
    gain_loss = None

    if mv_est is not None and crd_est is not None:
        sale_info = net_vendeur(
            market_value=mv_est,
            crd=Decimal(crd_est),
            selling_fees_rate=Decimal(prop.selling_fees_rate),
        )
        gain_loss = sale_info["net_vendeur"] - cash_invested_real

    # ------------------------------------------------------------------
    # RETURN
    # ------------------------------------------------------------------
    return {
        "property": prop.name,
        "end_date": end_date.isoformat(),

        # Loyers / charges
        "rent_total": str(rent_total),
        "charges_total": str(charges_total),
        "expenses_total": str(expenses_total),

        # Prêt
        "monthly_payment_est": str(m_payment) if m_payment else None,
        "loan_payments_total": str(loan_payment_total),
        "insurance_total": str(insurance_total),
        "capital_paid_est": str(capital_paid),
        "interest_paid_est": str(interest_paid),
        "crd_est": str(crd_est) if crd_est is not None else None,

        # Cashflows
        "cashflow_real": str(cashflow_real),
        "cashflow_economic": str(cashflow_economic),
        "cash_invested_real": str(cash_invested_real),

        # Marché
        "market_value_est": str(mv_est) if mv_est is not None else None,
        "market_price_per_sqm_last": str(last_m2) if last_m2 is not None else None,
        "market_price_point_date": last_m2_date.isoformat() if last_m2_date else None,
        "goodwill_eur_per_sqm": str(prop.goodwill_eur_per_sqm),

        # Vente
        "selling_fees_rate": str(prop.selling_fees_rate),
        "selling_fees_est": str(sale_info["selling_fees"]) if sale_info else None,
        "net_vendeur": str(sale_info["net_vendeur"]) if sale_info else None,
        "gain_loss_if_sold": str(gain_loss) if gain_loss is not None else None,
    }