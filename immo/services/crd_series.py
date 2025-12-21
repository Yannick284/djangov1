from datetime import date
from decimal import Decimal, ROUND_HALF_UP

TWOPLACES = Decimal("0.01")
def q(x): return x.quantize(TWOPLACES, rounding=ROUND_HALF_UP)

def crd_series_for_months(loan, months):
    capital = Decimal(loan.borrowed_capital)
    annual_rate = Decimal(loan.annual_rate)
    years = int(loan.years)
    n_total = years * 12
    t = (annual_rate / Decimal("100")) / Decimal("12")

    from .ledger import monthly_payment
    payment = Decimal(monthly_payment(capital, annual_rate, years))

    crd = capital
    out = {}
    i = 0

    start_m = date(loan.start_date.year, loan.start_date.month, 1)

    for m in months:
        if m < start_m:
            out[m.isoformat()] = None
            continue

        if i >= n_total:
            out[m.isoformat()] = str(q(Decimal("0")))
            continue

        interest = crd * t
        cap = payment - interest
        if cap < 0:
            cap = Decimal("0")

        crd -= cap
        out[m.isoformat()] = str(q(crd))
        i += 1

    return out