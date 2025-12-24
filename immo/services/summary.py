from datetime import date
from decimal import Decimal

from ..models import Property, Loan
from .ledger import iter_months, rent_for_month, expenses_for_month
from .loan_schedule import balance_after_months
from .sale import net_vendeur


def month_diff(start: date, end: date) -> int:
    """Nombre de mois écoulés entre deux dates (au niveau mois, pas au jour près)."""
    return (end.year - start.year) * 12 + (end.month - start.month)


def property_summary(prop: Property, end_date: date):
    """
    Résumé financier d’un bien.

    Règles voulues :
    - Le PRÊT court depuis loan.start_date (ex: 26/08/2022) -> CRD OK.
    - Le CASHFLOW INVESTISSEUR démarre au début de location (ex: 13/10/2025).
      Avant location = résidence principale => cashflow neutre (on ignore).
    - Cash investi réel = apport initial + (-cashflow réel cumulé depuis location).
    """
    end_date = end_date or date.today()

    # ============================================================
    # 1) VALEUR DE MARCHÉ
    # ============================================================
    mv_est = None
    last_m2 = None
    last_m2_date = None

    if prop.market_value_est:
        mv_est = Decimal(prop.market_value_est)
    elif prop.surface_sqm:
        last_point = prop.market_points.filter(date__lte=end_date).order_by("-date").first()
        if last_point:
            last_m2 = Decimal(last_point.price_per_sqm)
            last_m2_date = last_point.date

            goodwill = Decimal(prop.goodwill_eur_per_sqm or 0)
            parking = Decimal(prop.parking or 0)

            mv_est = (last_m2 + goodwill) * Decimal(prop.surface_sqm) + parking

    # ============================================================
    # 2) DATES DE RÉFÉRENCE
    # ============================================================
    periods = list(prop.rent_periods.order_by("start_date"))
    expenses = list(prop.expenses.all())

    # Date “investisseur” (début du cashflow locatif)
    rent_start = periods[0].start_date if periods else None

    # ============================================================
    # 3) CASHFLOW (UNIQUEMENT DEPUIS rent_start)
    # ============================================================
    rent_total = Decimal("0")
    charges_total = Decimal("0")
    expenses_total = Decimal("0")

    loan_payment_total = Decimal("0")
    insurance_total = Decimal("0")

    # Si pas encore loué, cashflow investisseur = 0 par définition (RP neutre)
    if rent_start and rent_start <= end_date:
        for m in iter_months(rent_start, end_date):
            # rent_for_month gère déjà le prorata si start_date = 13/10
            r, ch = rent_for_month(periods, m)
            rent_total += Decimal(r)
            charges_total += Decimal(ch)
            expenses_total += Decimal(expenses_for_month(expenses, m))

        # On compte aussi les mensualités/assurance uniquement sur la période “investisseur”
        try:
            loan: Loan = prop.loan
            months_cf = month_diff(rent_start, end_date) + 1  # +1 pour inclure le mois courant dans la somme

            # mensualité théorique (constante) via ton schedule
            months_elapsed_for_payment = month_diff(loan.start_date, loan.start_date)  # 0
            sched0 = balance_after_months(
                principal=Decimal(loan.borrowed_capital),
                annual_rate_pct=Decimal(loan.annual_rate),
                years=int(loan.years),
                months_elapsed=months_elapsed_for_payment,
            )
            monthly_payment = Decimal(sched0["payment"])

            loan_payment_total = monthly_payment * Decimal(months_cf)
            insurance_total = Decimal(loan.insurance_monthly or 0) * Decimal(months_cf)

        except Loan.DoesNotExist:
            monthly_payment = None
    else:
        monthly_payment = None

    cashflow_real = (rent_total + charges_total) - expenses_total - loan_payment_total - insurance_total

    # ============================================================
    # 4) PRÊT (CRD, capital, intérêts) DEPUIS loan.start_date
    # ============================================================
    capital_paid = Decimal("0")
    interest_paid = Decimal("0")
    crd_est = None

    try:
        loan: Loan = prop.loan

        months_elapsed = month_diff(loan.start_date, end_date)
        if months_elapsed < 0:
            months_elapsed = 0

        sched = balance_after_months(
            principal=Decimal(loan.borrowed_capital),
            annual_rate_pct=Decimal(loan.annual_rate),
            years=int(loan.years),
            months_elapsed=months_elapsed,
        )

        # mensualité affichée = celle du prêt
        monthly_payment = Decimal(sched["payment"])
        crd_est = Decimal(sched["crd"])
        capital_paid = Decimal(sched["capital_paid"])
        interest_paid = Decimal(sched["interest_paid"])

    except Loan.DoesNotExist:
        pass

    cashflow_economic = cashflow_real + capital_paid  # info “éco” (mais attention : capital_paid est depuis start prêt)

    # ============================================================
    # 5) CASH INVESTI RÉEL
    # ============================================================
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

    equity_at_purchase = acquisition_cost - borrowed  # ≈ apport + frais payés comptant

    # Investisseur : apport + cashflow négatif cumulé depuis location
    cash_invested_real = equity_at_purchase - cashflow_real

    # ============================================================
    # 6) VENTE
    # ============================================================
    sale_info = None
    gain_loss = None

    if mv_est is not None and crd_est is not None:
        sale_info = net_vendeur(
            market_value=mv_est,
            crd=crd_est,
            selling_fees_rate=Decimal(prop.selling_fees_rate or 0),
        )
        gain_loss = Decimal(sale_info["net_vendeur"]) - cash_invested_real

    # ============================================================
    # 7) RETURN
    # ============================================================
    return {
        # Dates utiles pour debug
        "rent_start_date": rent_start.isoformat() if rent_start else None,

        # Cash (depuis location)
        "rent_total": str(rent_total),
        "charges_total": str(charges_total),
        "expenses_total": str(expenses_total),

        # Prêt (état réel depuis start prêt)
        "monthly_payment_est": str(monthly_payment) if monthly_payment is not None else None,
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

        # Vente
        "selling_fees_rate": str(prop.selling_fees_rate or 0),
        "selling_fees_est": str(sale_info["selling_fees"]) if sale_info else None,
        "net_vendeur": str(sale_info["net_vendeur"]) if sale_info else None,
        "gain_loss_if_sold": str(gain_loss) if gain_loss is not None else None,
    }