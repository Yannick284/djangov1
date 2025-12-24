from datetime import date
from decimal import Decimal

from ..models import Property, Loan
from .ledger import iter_months, rent_for_month, expenses_for_month
from .loan_schedule import balance_after_months
from .sale import net_vendeur


def property_summary(prop: Property, end_date: date):
    """
    Résumé financier global d’un bien immobilier.
    Tous les montants sont calculés du point de vue INVESTISSEUR.
    """

    end_date = end_date or date.today()

    # ============================================================
    # 1️⃣ VALEUR DE MARCHÉ ACTUELLE
    # ============================================================

    mv_est = None
    last_m2 = None
    last_m2_date = None

    # Priorité 1 : valeur forcée manuellement
    if prop.market_value_est:
        mv_est = Decimal(prop.market_value_est)

    # Sinon : dernier point €/m² × surface + goodwill + parking
    elif prop.surface_sqm:
        last_point = prop.market_points.filter(
            date__lte=end_date
        ).order_by("-date").first()

        if last_point:
            last_m2 = Decimal(last_point.price_per_sqm)
            last_m2_date = last_point.date

            goodwill = Decimal(prop.goodwill_eur_per_sqm or 0)
            parking = Decimal(prop.parking or 0)

            mv_est = (
                (last_m2 + goodwill) * Decimal(prop.surface_sqm)
                + parking
            )

    # ============================================================
    # 2️⃣ CASH : LOYERS / CHARGES / DÉPENSES (AVEC PRORATA)
    # ============================================================

    rent_total = Decimal("0")
    charges_total = Decimal("0")
    expenses_total = Decimal("0")

    periods = list(prop.rent_periods.order_by("start_date"))
    expenses = list(prop.expenses.all())

    # On parcourt chaque mois depuis l’achat
    for m in iter_months(prop.purchase_date, end_date):
        rent, charges = rent_for_month(periods, m)  # proratisé
        rent_total += rent
        charges_total += charges
        expenses_total += expenses_for_month(expenses, m)

    # ============================================================
    # 3️⃣ PRÊT : CRD, INTÉRÊTS, CAPITAL REMBOURSÉ
    # ============================================================

    loan_payment_total = Decimal("0")
    insurance_total = Decimal("0")
    capital_paid = Decimal("0")
    interest_paid = Decimal("0")
    crd_est = None
    monthly_payment = None

    try:
        loan: Loan = prop.loan

        # Nombre de mois réellement écoulés depuis le début du prêt
        months_elapsed = (
            (end_date.year - loan.start_date.year) * 12
            + (end_date.month - loan.start_date.month)
        )

        sched = balance_after_months(
            principal=Decimal(loan.borrowed_capital),
            annual_rate_pct=Decimal(loan.annual_rate),
            years=int(loan.years),
            months_elapsed=months_elapsed,
        )

        monthly_payment = sched["payment"]
        loan_payment_total = monthly_payment * months_elapsed
        insurance_total = Decimal(loan.insurance_monthly or 0) * months_elapsed

        crd_est = sched["crd"]
        capital_paid = sched["capital_paid"]
        interest_paid = sched["interest_paid"]

    except Loan.DoesNotExist:
        pass

    # ============================================================
    # 4️⃣ CASHFLOW
    # ============================================================

    cashflow_real = (
        rent_total
        + charges_total
        - expenses_total
        - loan_payment_total
        - insurance_total
    )

    cashflow_economic = cashflow_real + capital_paid

    # ============================================================
    # 5️⃣ 💥 CASH INVESTI RÉEL (POINT CLÉ)
    # ============================================================

    # ➜ Cash réellement sorti à l’achat (apport implicite)
    acquisition_cost = (
        Decimal(prop.purchase_price or 0)
        + Decimal(prop.notary_fees or 0)
        + Decimal(prop.agency_fees or 0)
        + Decimal(prop.parking or 0)
    )

    borrowed = Decimal("0")
    try:
        borrowed = Decimal(prop.loan.borrowed_capital)
    except Loan.DoesNotExist:
        pass

    equity_at_purchase = acquisition_cost - borrowed

    # ➜ Cash investi total = apport + cashflow négatif cumulé
    cash_invested_real = equity_at_purchase - cashflow_real

    # ============================================================
    # 6️⃣ SCÉNARIO DE VENTE
    # ============================================================

    gain_loss = None
    sale_info = None

    if mv_est is not None and crd_est is not None:
        sale_info = net_vendeur(
            market_value=mv_est,
            crd=crd_est,
            selling_fees_rate=Decimal(prop.selling_fees_rate),
        )
        gain_loss = sale_info["net_vendeur"] - cash_invested_real

    # ============================================================
    # 7️⃣ RETURN
    # ============================================================

    return {
        "rent_total": str(rent_total),
        "charges_total": str(charges_total),
        "expenses_total": str(expenses_total),

        "monthly_payment_est": str(monthly_payment) if monthly_payment else None,
        "loan_payments_total": str(loan_payment_total),
        "insurance_total": str(insurance_total),
        "capital_paid_est": str(capital_paid),
        "interest_paid_est": str(interest_paid),
        "crd_est": str(crd_est) if crd_est else None,

        "cashflow_real": str(cashflow_real),
        "cashflow_economic": str(cashflow_economic),
        "cash_invested_real": str(cash_invested_real),

        "market_value_est": str(mv_est) if mv_est else None,
        "market_price_per_sqm_last": str(last_m2) if last_m2 else None,
        "market_price_point_date": last_m2_date.isoformat() if last_m2_date else None,

        "selling_fees_rate": str(prop.selling_fees_rate),
        "selling_fees_est": str(sale_info["selling_fees"]) if sale_info else None,
        "net_vendeur": str(sale_info["net_vendeur"]) if sale_info else None,
        "gain_loss_if_sold": str(gain_loss) if gain_loss else None,
    }