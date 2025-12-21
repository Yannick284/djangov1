from datetime import date
from decimal import Decimal
from .summary import property_summary
from .loan_schedule import balance_after_months  # si tu l'utilises déjà

def add_years(d: date, years: int) -> date:
    try:
        return d.replace(year=d.year + years)
    except ValueError:
        # 29/02 -> 28/02
        return d.replace(month=2, day=28, year=d.year + years)

def months_between(start: date, end: date) -> int:
    return (end.year - start.year) * 12 + (end.month - start.month) + 1  # inclusif

def time_sale_scenarios(prop, end_date, growth_pct: Decimal, years_list=(1,2,3,4,5)):
    """
    growth_pct: ex 0.02 pour 2%/an
    Utilise la valeur marché actuelle (dernier point du graphe + goodwill) comme base.
    """
    s0 = property_summary(prop, end_date)

    # valeur actuelle base (déjà cohérente avec dernier point + goodwill chez toi)
    if not s0.get("market_value_est") or not s0.get("crd_est"):
        return None

    base_mv = Decimal(str(s0["market_value_est"]))  # total €
    fee_rate = Decimal(str(s0.get("selling_fees_rate") or prop.selling_fees_rate or 0))
    cash0 = Decimal(str(s0.get("cash_invested_real") or 0))

    rows = []
    for y in years_list:
        sell_date = add_years(end_date, int(y))

        # projection valeur marché
        mv = base_mv * (Decimal("1") + growth_pct) ** Decimal(str(y))
        fees = mv * fee_rate / Decimal("100")

        # CRD à la date future (si prêt)
        crd = None
        try:
            loan = prop.loan
            n_months = months_between(loan.start_date, sell_date)
            sched = balance_after_months(
                principal=Decimal(loan.borrowed_capital),
                annual_rate_pct=Decimal(loan.annual_rate),
                years=int(loan.years),
                months_elapsed=n_months,
            )
            crd = Decimal(str(sched["crd"]))
        except Exception:
            crd = None

        # si pas de CRD -> on peut quand même afficher mv, mais pas net vendeur/gain_loss fiables
        if crd is None:
            net_vendeur = None
            gain_loss = None
        else:
            net_vendeur = mv - fees - crd
            gain_loss = net_vendeur - cash0  # MVP: cash investi constant

        rows.append({
            "years": y,
            "sell_date": sell_date.isoformat(),
            "market_value": str(mv),
            "market_value_total": str(mv),  # alias pour éviter KeyError si ton template/view attend encore ce nom
            "crd": str(crd) if crd is not None else None,
            "cash_invested": str(cash0),
            "net_vendeur": str(net_vendeur) if net_vendeur is not None else None,
            "gain_loss": str(gain_loss) if gain_loss is not None else None,
        })

    return {"rows": rows}