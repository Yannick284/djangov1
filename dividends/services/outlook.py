"""Vues « à venir » : revenu estimé sur 12 mois et prochains versements."""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import List, Tuple

from django.utils import timezone

from dividends.services.forecast_year import ForecastEvent, build_year_events


def _events_between(user, start: date, end_excl: date, growth_pct: Decimal) -> List[ForecastEvent]:
    events: List[ForecastEvent] = []
    for year in range(start.year, end_excl.year + 1):
        events += build_year_events(user, year, growth_pct=growth_pct)
    return [e for e in events if start <= e.display_date < end_excl]


def next_12_months(user, growth_pct: Decimal = Decimal("0")) -> Tuple[Decimal, List[dict]]:
    """Total estimé et détail mois par mois, du mois courant inclus aux 11 mois suivants."""
    today = timezone.localdate()
    first = date(today.year, today.month, 1)
    end = date(first.year + 1, first.month, 1)
    events = _events_between(user, first, end, growth_pct)

    months = []
    for i in range(12):
        y = first.year + (first.month - 1 + i) // 12
        m = (first.month - 1 + i) % 12 + 1
        total = sum((e.estimated_amount for e in events if e.display_date.year == y and e.display_date.month == m), Decimal("0"))
        months.append({"year": y, "month": m, "total": total})
    return sum((m["total"] for m in months), Decimal("0")), months


def upcoming_payments(user, days: int = 7, growth_pct: Decimal = Decimal("0")) -> List[ForecastEvent]:
    """Versements attendus entre aujourd'hui et dans `days` jours (inclus)."""
    today = timezone.localdate()
    events = _events_between(user, today, today + timedelta(days=days + 1), growth_pct)
    return sorted(events, key=lambda e: (e.display_date, e.ticker))


def payments_on(user, day: date, growth_pct: Decimal = Decimal("0")) -> List[ForecastEvent]:
    return [e for e in _events_between(user, day, day + timedelta(days=1), growth_pct)]
