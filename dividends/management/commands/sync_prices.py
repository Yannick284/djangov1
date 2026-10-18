from django.core.management.base import BaseCommand
from dividends.models import Asset
from dividends.services.prices import update_asset_price


class Command(BaseCommand):
    help = "Sync last prices for assets."

    def add_arguments(self, parser):
        parser.add_argument("--user-id", type=int, default=None)
        parser.add_argument("--limit", type=int, default=500)

    def handle(self, *args, **options):
        qs = Asset.objects.filter(is_active=True).order_by("id")
        if options["user_id"]:
            qs = qs.filter(user_id=options["user_id"])
        qs = qs[: options["limit"]]

        ok = 0
        fail = 0

        for a in qs:
            # ✅ Fallback: si price_symbol vide, on utilise ticker
            symbol = (a.price_symbol or a.ticker or "").strip()

            if not symbol:
                fail += 1
                self.stdout.write(self.style.WARNING(f"FAIL Asset#{a.id} (no price_symbol/ticker)"))
                continue

            # Optionnel: si ton service lit a.price_symbol, on le remplit à la volée
            if not (a.price_symbol or "").strip():
                a.price_symbol = symbol  # pas besoin de save() pour ce run

            if update_asset_price(a):
                ok += 1
                self.stdout.write(self.style.SUCCESS(f"OK  {symbol} -> {a.last_price}"))
            else:
                fail += 1
                self.stdout.write(self.style.WARNING(f"FAIL {a.ticker} (symbol='{symbol}')"))

        self.stdout.write(f"Done. OK={ok} FAIL={fail}")