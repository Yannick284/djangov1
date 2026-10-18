from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db import IntegrityError, transaction
from dividends.models import Asset, DividendEvent
import yfinance as yf


class Command(BaseCommand):
    help = "Sync declared dividends (per share) from yfinance. Idempotent + safe on duplicates."

    def add_arguments(self, parser):
        parser.add_argument("--years", type=int, default=5)
        parser.add_argument("--limit", type=int, default=500)
        parser.add_argument("--user-id", type=int, default=None)
        parser.add_argument("--autofill-symbol", action="store_true")

    def handle(self, *args, **opts):
        years = opts["years"]
        limit = opts["limit"]
        user_id = opts["user_id"]
        autofill = opts["autofill_symbol"]

        qs = Asset.objects.filter(is_active=True).order_by("id")
        if user_id:
            qs = qs.filter(user_id=user_id)
        qs = qs[:limit]

        ok = created = fail = no_div = skipped = dup = 0

        for a in qs:
            sym = (a.price_symbol or a.ticker or "").strip()
            if not sym:
                skipped += 1
                self.stdout.write(self.style.WARNING(f"SKIP Asset#{a.id} (no price_symbol/ticker)"))
                continue

            if autofill and not (a.price_symbol or "").strip():
                a.price_symbol = sym
                a.save(update_fields=["price_symbol"])

            try:
                t = yf.Ticker(sym)
                s = t.dividends
            except Exception as e:
                fail += 1
                self.stdout.write(self.style.WARNING(f"FAIL {a.ticker} (sym='{sym}') ({e})"))
                continue

            if s is None or getattr(s, "empty", True):
                no_div += 1
                self.stdout.write(f"NO  {a.ticker} (sym='{sym}')")
                ok += 1
                continue

            s = s.tail(years * 10)

            add = 0
            dup_local = 0

            for dt, amt in s.items():
                ex_date = dt.date()

                try:
                    amount = Decimal(str(amt))
                except Exception:
                    continue

                # ⚠️ IMPORTANT: wrap atomic + handle race duplicates
                try:
                    with transaction.atomic():
                        _obj, was_created = DividendEvent.objects.get_or_create(
                            asset=a,
                            ex_date=ex_date,
                            amount_per_share=amount,
                            defaults={
                                "currency": (getattr(a, "currency", None) or "EUR"),
                                "source": "yfinance",
                                "status": "declared",
                            },
                        )
                        if was_created:
                            add += 1
                except IntegrityError:
                    # Un autre run a créé la ligne entre-temps -> on ignore
                    dup_local += 1
                    continue

            ok += 1
            created += add
            dup += dup_local
            self.stdout.write(self.style.SUCCESS(f"OK  {a.ticker} (sym='{sym}') +{add} dup={dup_local}"))

        self.stdout.write(
            f"Done. OK={ok} created={created} dup={dup} NO={no_div} FAIL={fail} SKIP={skipped}"
        )