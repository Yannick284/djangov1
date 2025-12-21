from decimal import Decimal
from datetime import date

from .summary import property_summary
from .sale import net_vendeur


def sale_scenarios(prop, end_date: date, multipliers=None):
    end_date = end_date or date.today()

    if multipliers is None:
        multipliers = [
            Decimal("0.90"),
            Decimal("0.95"),
            Decimal("1.00"),
            Decimal("1.05"),
            Decimal("1.10"),
        ]

    # 1) Récupère le résumé (CRD, cash investi, etc.)
    s = property_summary(prop, end_date)
    if s.get("crd_est") is None:
        return None

    crd = Decimal(s["crd_est"])
    cash_invested = Decimal(s["cash_invested_real"])
    fee_rate = Decimal(prop.selling_fees_rate)

    # 2) Dernier point marché (source unique)
    last_point = prop.market_points.filter(date__lte=end_date).order_by("-date").first()
    if not last_point or not prop.surface_sqm:
        return None

    last_m2 = Decimal(last_point.price_per_sqm)
    goodwill = Decimal(getattr(prop, "goodwill_eur_per_sqm", 0) or 0)

    # €/m² ajusté
    m2_adjusted = last_m2 + goodwill

    # Valeur appartement
    flat_value = m2_adjusted * Decimal(prop.surface_sqm)

    # Parking à part
    parking_value = Decimal(getattr(prop, "parking", 0) or 0)

    # ✅ BASE SCÉNARIO = DERNIER POINT
    base_market_value = flat_value + parking_value

    # 3) Génération des scénarios
    rows = []
    for m in multipliers:
        mv = base_market_value * m

        sale = net_vendeur(
            market_value=mv,
            crd=crd,
            selling_fees_rate=fee_rate,
        )

        gain_loss = sale["net_vendeur"] - cash_invested

        rows.append({
            "multiplier": str(m),
            "market_value": str(mv),
            "selling_fees": str(sale["selling_fees"]),
            "net_vendeur": str(sale["net_vendeur"]),
            "gain_loss": str(gain_loss),
        })

    return {
        "base": {
            "date": last_point.date.isoformat(),
            "price_per_sqm_market": str(last_m2),
            "goodwill_eur_per_sqm": str(goodwill),
            "price_per_sqm_adjusted": str(m2_adjusted),
            "flat_value": str(flat_value),
            "parking_value": str(parking_value),
            "market_value_total": str(base_market_value),
        },
        "rows": rows,
    }