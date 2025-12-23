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


D0 = Decimal("0")


def months_between(start: date, end: date) -> int:
    s = month_start(start)
    e = month_start(end)
    return (e.year - s.year) * 12 + (e.month - s.month)


def _d(v) -> Decimal:
    """Decimal safe"""
    if v is None or v == "":
        return D0
    return Decimal(str(v))


def property_summary(prop: Property, end_date: date):
    end_date = end_date or date.today()

    # ------------------------------------------------------------------
    # 0) COÛT D'ACQUISITION / APPORT
    # ------------------------------------------------------------------
    purchase_price = _d(prop.purchase_price)
    notary_fees = _d(prop.notary_fees)
    agency_fees = _d(prop.agency_fees)
    parking = _d(prop.parking)

    acquisition_total = purchase_price + notary_fees + agency_fees + parking

    borrowed = None
    try:
        loan: Loan = prop.loan
        borrowed = _d(loan.borrowed_capital)
    except Loan.DoesNotExist:
        loan = None
        borrowed = None

    if borrowed is not None and borrowed > 0:
        down_payment = acquisition_total - borrowed
    else:
        down_payment = acquisition_total

    # évite un apport négatif si données incohérentes
    if down_payment < 0:
        down_payment = D0

    # ------------------------------------------------------------------
    # 1) VALEUR DE MARCHÉ
    # - override manuel: valeur totale €
    # - sinon: dernier point €/m² + goodwill €/m², * surface, + parking
    # ------------------------------------------------------------------
    mv_est = None
    last_m2 = None
    last_m2_date = None

    if prop.market_value_est:
        mv_est = _d(prop.market_value_est)

    elif prop.surface_sqm:
        last_point = prop.market_points.filter(date__lte=end_date).order_by("-date").first()
        if last_point:
            last_m2 = _d(last_point.price_per_sqm)
            last_m2_date = last_point.date
            goodwill = _d(prop.goodwill_eur_per_sqm)

            mv_est = (last_m2 + goodwill) * _d(prop.surface_sqm) + parking

    # ------------------------------------------------------------------
    # 2) LOYERS / CHARGES / DÉPENSES
    # ------------------------------------------------------------------
    periods = list(prop.rent_periods.order_by("start_date"))
    expenses = list(prop.expenses.all())

    rent_total = D0
    charges_total = D0
    expenses_total = D0

    for m in iter_months(prop.purchase_date, end_date):
        r_hc, ch = rent_for_month(periods, m)  # <-- ton ledger fait la proration
        rent_total += _d(r_hc)
        charges_total += _d(ch)
        expenses_total += _d(expenses_for_month(expenses, m))

    # ------------------------------------------------------------------
    # 3) PRÊT (totaux + CRD)
    # ------------------------------------------------------------------
    loan_payment_total = D0
    insurance_total = D0
    capital_paid = D0
    interest_paid = D0
    crd_est = None
    m_payment = None

    if loan:
        n_months = months_between(loan.start_date, end_date)
        if n_months < 0:
            n_months = 0

        sched = balance_after_months(
            principal=_d(loan.borrowed_capital),
            annual_rate_pct=_d(loan.annual_rate),
            years=int(loan.years),
            months_elapsed=n_months,
        )

        m_payment = _d(sched.get("payment"))
        loan_payment_total = m_payment * Decimal(n_months)
        insurance_total = _d(loan.insurance_monthly) * Decimal(n_months)

        crd_est = sched.get("crd")
        capital_paid = _d(sched.get("capital_paid"))
        interest_paid = _d(sched.get("interest_paid"))

    # ------------------------------------------------------------------
    # 4) CASHFLOWS
    # ------------------------------------------------------------------
    cashflow_real = (rent_total + charges_total) - expenses_total - loan_payment_total - insurance_total
    cashflow_economic = cashflow_real + capital_paid

    # ✅ CORRECTION: cash investi réel = apport - cashflow cumulé
    cash_invested_real = down_payment - cashflow_real

    # ------------------------------------------------------------------
    # 5) VENTE
    # ------------------------------------------------------------------
    sale_info = None
    gain_loss = None

    if mv_est is not None and crd_est is not None:
        sale_info = net_vendeur(
            market_value=mv_est,
            crd=_d(crd_est),
            selling_fees_rate=_d(prop.selling_fees_rate),
        )
        gain_loss = _d(sale_info["net_vendeur"]) - cash_invested_real

    # ------------------------------------------------------------------
    # RETURN
    # ------------------------------------------------------------------
    return {
        "property": prop.name,
        "end_date": end_date.isoformat(),

        # Acquisition / apport
        "acquisition_total": str(acquisition_total),
        "borrowed_capital": str(borrowed) if borrowed is not None else None,
        "down_payment": str(down_payment),

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
        "goodwill_eur_per_sqm": str(_d(prop.goodwill_eur_per_sqm)),

        # Vente
        "selling_fees_rate": str(_d(prop.selling_fees_rate)),
        "selling_fees_est": str(sale_info["selling_fees"]) if sale_info else None,
        "net_vendeur": str(sale_info["net_vendeur"]) if sale_info else None,
        "gain_loss_if_sold": str(gain_loss) if gain_loss is not None else None,
    }