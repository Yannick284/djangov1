from decimal import Decimal
from django.db.models import Sum
from django.db.models.functions import Coalesce

from dividends.models import DividendEvent, DividendPayment
from dividends.services.holdings import quantity_at_date


def expected_dividends_year(user, year):
    """
    Somme des dividendes attendus sur l'année (events pay_date dans l'année, non reçus).
    """
    total = Decimal("0")

    events = (
        DividendEvent.objects
        .filter(asset__user=user, pay_date__year=year)
        .exclude(status="received")
        .select_related("asset")
        .order_by("pay_date")
    )

    for ev in events:
        qty = quantity_at_date(ev.asset, ev.ex_date)
        total += (qty or Decimal("0")) * (ev.amount_per_share or Decimal("0"))

    return total


def received_dividends_year(user, year):
    """
    Somme des paiements réels sur l'année (net).
    """
    return (
        DividendPayment.objects
        .filter(asset__user=user, date__year=year)
        .aggregate(total=Coalesce(Sum("gross_amount"), Decimal("0")))["total"]
        or Decimal("0")
    )


def next_dividend_events(user, limit=5):
    """
    Prochains versements à venir (triés par pay_date).
    """
    return (
        DividendEvent.objects
        .filter(asset__user=user)
        .exclude(status="received")
        .order_by("pay_date")[:limit]
    )
    
from decimal import Decimal
from dividends.services.holdings import quantity_at_date

def upcoming_events_with_estimates(user, limit=10):
    """
    Retourne une liste de dicts avec qty détenue à l'ex-date et montant estimé.
    """
    events = (
        DividendEvent.objects
        .filter(asset__user=user)
        .exclude(status="received")
        .select_related("asset")
        .order_by("pay_date")[:limit]
    )

    rows = []
    for ev in events:
        qty = quantity_at_date(ev.asset, ev.ex_date) or Decimal("0")
        est = qty * (ev.amount_per_share or Decimal("0"))
        rows.append({
            "event": ev,
            "qty": qty,
            "estimated_amount": est,
        })

    return rows