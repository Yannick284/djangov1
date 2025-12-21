# from decimal import Decimal, ROUND_HALF_UP

# TWOPLACES = Decimal("0.01")
# def q(x): return x.quantize(TWOPLACES, rounding=ROUND_HALF_UP)

# def approximate_schedule_with_payment(
#     capital: Decimal,
#     annual_rate: Decimal,
#     years: int,
#     monthly_payment: Decimal,
#     months_elapsed: int,
# ):
#     n = years * 12
#     t = (annual_rate / Decimal("100")) / Decimal("12")

#     crd = capital
#     capital_paid = Decimal("0")
#     interest_paid = Decimal("0")

#     for _ in range(min(months_elapsed, n)):
#         interest = crd * t
#         cap = monthly_payment - interest
#         if cap < 0:  # taux délirant / paiement trop faible
#             cap = Decimal("0")

#         crd -= cap
#         capital_paid += cap
#         interest_paid += interest

#     return {
#         "crd": q(crd),
#         "capital_paid": q(capital_paid),
#         "interest_paid": q(interest_paid),
#     }