from decimal import Decimal

def net_vendeur(
    market_value: Decimal,
    crd: Decimal,
    selling_fees_rate: Decimal,
):
    selling_fees = market_value * selling_fees_rate / Decimal("100")
    return {
        "selling_fees": selling_fees,
        "net_vendeur": market_value - selling_fees - crd,
    }