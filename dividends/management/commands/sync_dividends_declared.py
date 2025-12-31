from django.core.management.base import BaseCommand
from dividends.models import Asset, DividendEvent
import yfinance as yf
from decimal import Decimal


class Command(BaseCommand):
    help = "Sync declared dividends (per share) from yfinance."

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

        ok = 0
        created = 0
        fail = 0
        no_div = 0
        skipped = 0

        for a in qs:
            sym = (a.price_symbol or a.ticker or "").strip()

            if not sym:
                skipped += 1
                self.stdout.write(self.style.WARNING(f"SKIP Asset#{a.id} (no price_symbol/ticker)"))
                continue

            # Optionnel: normaliser en base si price_symbol vide
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
                continue

            # ~4 dividendes/an -> years*10 suffit large
            s = s.tail(years * 10)

            add = 0
            for dt, amt in s.items():
                ex_date = dt.date()
                # yfinance peut renvoyer float/np.float; on sécurise la conversion
                try:
                    amount = Decimal(str(amt))
                except Exception:
                    continue

                obj, was_created = DividendEvent.objects.get_or_create(
                    asset=a,
                    ex_date=ex_date,
                    amount_per_share=amount,
                    defaults={
                        "currency": (getattr(a, "currency", None) or "EUR"),
                        "source": "yfinance",
                    },
                )
                if was_created:
                    add += 1

            ok += 1
            created += add
            self.stdout.write(self.style.SUCCESS(f"OK  {a.ticker} (sym='{sym}') +{add}"))

        self.stdout.write(
            f"Done. OK={ok} created={created} NO={no_div} FAIL={fail} SKIP={skipped}"
        )