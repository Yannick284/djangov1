from datetime import date
from decimal import Decimal
from .summary import property_summary
from .ledger import month_start, add_months

def projected_market_value(current_value: Decimal, annual_growth_rate: Decimal, months_ahead: int) -> Decimal:
    # annual_growth_rate en % (ex: 1.0)
    g = (annual_growth_rate / Decimal("100")) / Decimal("12")
    return current_value * (Decimal("1") + g) ** Decimal(months_ahead)

def breakeven_date(prop, as_of: date, horizon_months: int = 120, annual_growth_rate: Decimal = Decimal("0.0")):
    """
    Cherche la première date future (mois) où gain_loss_if_sold >= 0.
    """
    if prop.market_value_est is None:
        return None

    as_of = month_start(as_of)
    base_value = Decimal(prop.market_value_est)

    for i in range(0, horizon_months + 1):
        d = add_months(as_of, i)

        # on “injecte” une valeur marché projetée pour ce mois
        mv = projected_market_value(base_value, annual_growth_rate, i)

        # hack MVP: on ne modifie pas le modèle, on calcule le summary puis on recalculera la vente
        s = property_summary(prop, d)

        crd = s.get("crd_est")
        cash_invested = Decimal(s["cash_invested_real"])

        if crd is None:
            continue

        crd = Decimal(crd)
        fees = mv * Decimal(prop.selling_fees_rate) / Decimal("100")
        net_vendeur = mv - fees - crd
        gain_loss = net_vendeur - cash_invested

        if gain_loss >= 0:
            return {
                "date": d.isoformat(),
                "months_ahead": i,
                "market_value": str(mv),
                "net_vendeur": str(net_vendeur),
                "gain_loss": str(gain_loss),
            }

    return None