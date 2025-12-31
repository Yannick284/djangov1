from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import List


def month_grid(year: int, month: int, events: List):
    """
    events: list d'objets ayant .display_date et .estimated_amount
    Retourne grid[weeks][days] avec total_estimated + events
    """
    first = date(year, month, 1)
    next_month = date(year + (month == 12), 1 if month == 12 else month + 1, 1)
    last = next_month - timedelta(days=1)

    start = first - timedelta(days=first.weekday())
    end = last + timedelta(days=(6 - last.weekday()))

    by_day = {}
    for e in events:
        by_day.setdefault(e.display_date, []).append(e)

    weeks = []
    cur = start
    while cur <= end:
        week = []
        for _ in range(7):
            day_events = by_day.get(cur, [])
            total = sum((ev.estimated_amount for ev in day_events), Decimal("0.00"))
            week.append(
                {
                    "d": cur,
                    "in_month": cur.month == month,
                    "events": day_events,
                    "total_estimated": total,
                }
            )
            cur += timedelta(days=1)
        weeks.append(week)

    return weeks