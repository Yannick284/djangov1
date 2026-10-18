from datetime import date
from decimal import Decimal, ROUND_HALF_UP

TWOPLACES = Decimal("0.01")

def q(x: Decimal) -> Decimal:
    return x.quantize(TWOPLACES, rounding=ROUND_HALF_UP)

def monthly_rate(annual_rate_pct: Decimal) -> Decimal:
    return (annual_rate_pct / Decimal("100")) / Decimal("12")

def payment_amount(principal: Decimal, annual_rate_pct: Decimal, years: int) -> Decimal:
    r = monthly_rate(annual_rate_pct)
    n = years * 12
    if r == 0:
        return q(principal / Decimal(n))
    # M = P * r / (1 - (1+r)^-n)
    denom = (Decimal("1") - (Decimal("1") + r) ** Decimal(-n))
    return q(principal * r / denom)

def balance_after_months(
    principal: Decimal,
    annual_rate_pct: Decimal,
    years: int,
    months_elapsed: int,
):
    """
    Amortissement “banque-like”:
    - intérêts arrondis au centime
    - capital = mensualité - intérêts
    - CRD mis à jour, arrondi
    """
    n = years * 12
    m = min(months_elapsed, n)
    r = monthly_rate(annual_rate_pct)
    pay = payment_amount(principal, annual_rate_pct, years)

    crd = q(principal)
    cap_paid = Decimal("0")
    int_paid = Decimal("0")

    for i in range(m):
        interest = q(crd * r)
        principal_part = q(pay - interest)
        if principal_part < 0:
            principal_part = Decimal("0.00")

        # dernière échéance: on évite CRD négatif
        if principal_part > crd:
            principal_part = crd
            pay = q(interest + principal_part)

        crd = q(crd - principal_part)
        cap_paid += principal_part
        int_paid += interest

        if crd <= 0:
            crd = Decimal("0.00")
            break

    return {
        "payment": pay,
        "crd": q(crd),
        "capital_paid": q(cap_paid),
        "interest_paid": q(int_paid),
    }