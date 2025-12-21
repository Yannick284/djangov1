# immo/services/months.py
from __future__ import annotations
from datetime import date
from typing import Iterator

def month_start(d: date) -> date:
    return d.replace(day=1)

def add_months(d: date, months: int) -> date:
    y = d.year + (d.month - 1 + months) // 12
    m = (d.month - 1 + months) % 12 + 1
    return date(y, m, 1)

def iter_month_starts(start: date, end: date) -> Iterator[date]:
    """
    Génère les 1ers jours de chaque mois entre start et end (inclus).
    start/end peuvent être n'importe quel jour du mois.
    """
    cur = month_start(start)
    last = month_start(end)
    while cur <= last:
        yield cur
        cur = add_months(cur, 1)