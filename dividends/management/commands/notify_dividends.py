from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from django.utils import timezone

from dividends.models import DividendAlertSetting
from dividends.services.outlook import payments_on


class Command(BaseCommand):
    help = (
        "Envoie un e-mail aux utilisateurs qui ont activé l'alerte, la veille d'un versement de dividende. "
        "À lancer une fois par jour (tâche planifiée) : chaque versement n'est annoncé qu'une fois."
    )

    def add_arguments(self, parser):
        parser.add_argument("--ahead", type=int, default=1, help="Jours d'avance (1 = versements de demain).")
        parser.add_argument("--dry-run", action="store_true", help="Affiche sans envoyer.")

    def handle(self, *args, **opts):
        day = timezone.localdate() + timedelta(days=opts["ahead"])
        User = get_user_model()
        user_ids = DividendAlertSetting.objects.filter(enabled=True).values_list("user_id", flat=True)

        sent = 0
        for user in User.objects.filter(id__in=user_ids, is_active=True).exclude(email=""):
            events = payments_on(user, day)
            if not events:
                continue
            lines = [f"- {e.ticker} : {e.estimated_amount:.2f} {e.currency or 'EUR'}" for e in events]
            total = sum(e.estimated_amount for e in events)
            body = (
                f"Bonjour {user.first_name or user.username},\n\n"
                f"Versements de dividendes prévus le {day:%d/%m/%Y} (estimation) :\n\n"
                + "\n".join(lines)
                + f"\n\nTotal estimé : {total:.2f}\n\n"
                "Tu reçois ce message parce que l'alerte est activée sur ton profil."
            )
            if opts["dry_run"]:
                self.stdout.write(f"[dry-run] {user.email}\n{body}\n")
            else:
                send_mail(f"Dividendes demain : {len(events)} versement(s)", body, settings.DEFAULT_FROM_EMAIL, [user.email])
            sent += 1
        self.stdout.write(f"Done. messages={sent} date={day.isoformat()}")
