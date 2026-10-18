from datetime import date
from decimal import Decimal
from django.core.management.base import BaseCommand, CommandError

from immo.models import Property, MarketPricePoint


MONTHS = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
    "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12
}

DATA = """
Apr-22\t7710
May-22\t7673
Jun-22\t7714
Jul-22\t7755
Aug-22\t7706
Sep-22\t7505
Oct-22\t7491
Nov-22\t7337
Dec-22\t7320
Jan-23\t7370
Feb-23\t7230
Mar-23\t7116
Apr-23\t7166
May-23\t7266
Jun-23\t7354
Jul-23\t7334
Aug-23\t7267
Sep-23\t7018
Oct-23\t6793
Nov-23\t6818
Dec-23\t6845
Jan-24\t6953
Feb-24\t6767
Mar-24\t6550
Apr-24\t6504
May-24\t6624
Jun-24\t6757
Jul-24\t6766
Aug-24\t6844
Sep-24\t6895
Oct-24\t6729
Nov-24\t6682
Dec-24\t6438
Jan-25\t6413
Feb-25\t6652
Mar-25\t6573
Apr-25\t6538
May-25\t6640
Jun-25\t6542
Jul-25\t6533
Aug-25\t6789
Sep-25\t6619
Oct-25\t6662
Nov-25\t6532
Dec-25\t6499
""".strip()


def parse_month_year(token: str) -> date:
    mon3, yy = token.split("-")
    m = MONTHS.get(mon3)
    if not m:
        raise ValueError(f"Mois invalide: {mon3}")
    return date(2000 + int(yy), m, 1)


class Command(BaseCommand):
    help = "Importe des points prix/m² mensuels dans MarketPricePoint pour un Property."

    def add_arguments(self, parser):
        parser.add_argument("property_id", type=int)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        prop_id = options["property_id"]
        dry = options["dry_run"]

        try:
            prop = Property.objects.get(id=prop_id)
        except Property.DoesNotExist:
            raise CommandError(f"Property id={prop_id} introuvable")

        created = 0
        updated = 0

        for line in DATA.splitlines():
            line = line.strip()
            if not line:
                continue

            parts = line.split("\t")
            if len(parts) != 2:
                raise CommandError(f"Ligne invalide (tab attendu) : {line!r}")

            month_token = parts[0].strip()
            value_token = parts[1].strip()

            d = parse_month_year(month_token)
            v = Decimal(value_token)

            if dry:
                self.stdout.write(f"{prop.name} {d.isoformat()} -> {v}")
                continue

            obj, was_created = MarketPricePoint.objects.update_or_create(
                property=prop,
                date=d,
                defaults={"price_per_sqm": v},
            )
            created += 1 if was_created else 0
            updated += 0 if was_created else 1

        if dry:
            self.stdout.write(self.style.SUCCESS("DRY RUN OK"))
        else:
            self.stdout.write(self.style.SUCCESS(f"Import terminé: {created} créés, {updated} mis à jour."))