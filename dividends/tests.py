from datetime import date, timedelta
from decimal import Decimal
from io import StringIO
from unittest import mock

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Asset, DividendAlertSetting, DividendEvent, Transaction
from .services.importer import import_transactions, parse_rows
from .services.instruments import resolve_item
from .services.outlook import next_12_months, payments_on
from .services.prices import PriceQuote, guess_currency, update_asset_price

User = get_user_model()


def csv_bytes(*lines):
    return ("\r\n".join(lines) + "\r\n").encode("utf-8")


class PriceUpdateTests(TestCase):
    def test_update_asset_price_saves_without_crashing(self):
        # Avant : le code écrivait « last_price_updated_at », un champ inexistant (le prix n'était jamais daté).
        user = User.objects.create_user("u", "u@example.com", "pw-12345-abc")
        asset = Asset.objects.create(user=user, ticker="SAN.PA")
        quote = PriceQuote(symbol="SAN.PA", price=Decimal("92.456"), asof=timezone.now(), source="yfinance")
        with mock.patch("dividends.services.prices.get_quote", return_value=quote):
            self.assertTrue(update_asset_price(asset))
        asset.refresh_from_db()
        self.assertEqual(asset.last_price, Decimal("92.46"))
        self.assertIsNotNone(asset.last_price_asof)
        self.assertEqual(asset.last_price_source, "yfinance")

    def test_currency_guess_from_exchange_suffix(self):
        self.assertEqual(guess_currency("SAN.PA"), "EUR")
        self.assertEqual(guess_currency("KO"), "USD")
        self.assertEqual(guess_currency("VOD.L"), "GBP")


class ResolveInstrumentTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("u", "u@example.com", "pw-12345-abc")

    def test_universe_key_and_isin(self):
        item, err = resolve_item(self.user, key="san.pa")
        self.assertEqual((item.ticker, err), ("SAN.PA", ""))
        item, _ = resolve_item(self.user, custom="FR0000120578", verify=False)
        self.assertEqual(item.ticker, "SAN.PA")

    def test_free_ticker_is_checked_against_yahoo(self):
        with mock.patch("dividends.services.instruments.lookup_instrument", return_value=None):
            item, err = resolve_item(self.user, custom="zzzzz")
        self.assertIsNone(item)
        self.assertIn("introuvable", err)
        with mock.patch("dividends.services.instruments.lookup_instrument", return_value={"currency": "USD"}):
            item, err = resolve_item(self.user, custom="pep")
        self.assertEqual((item.ticker, item.currency, err), ("PEP", "USD", ""))

    def test_dangerous_tickers_are_rejected_before_any_network_call(self):
        with mock.patch("dividends.services.instruments.lookup_instrument") as lookup:
            for bad in ("../etc/passwd", "A B", "X" * 40, "a;b", "<script>"):
                item, err = resolve_item(self.user, custom=bad)
                self.assertIsNone(item, bad)
            lookup.assert_not_called()


class ImportTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("u", "u@example.com", "pw-12345-abc")

    def test_french_file_is_imported(self):
        res = import_transactions(self.user, csv_bytes(
            "date;type;ticker;quantite;prix;frais",
            "15/03/2024;achat;SAN.PA;10;92,50;1,90",
            "2024-09-02;Achat;KO;5;61.20;0",
            "2025-01-20;vente;SAN.PA;4;95,10;1,90",
        ))
        self.assertTrue(res.ok, res.errors)
        self.assertEqual(res.created, 3)
        san = Asset.objects.get(user=self.user, ticker="SAN.PA")
        buy = san.transactions.get(type="BUY")
        self.assertEqual((buy.quantity, buy.price, buy.fees, buy.date), (Decimal("10"), Decimal("92.50"), Decimal("1.90"), date(2024, 3, 15)))
        self.assertEqual(Asset.objects.get(user=self.user, ticker="KO").currency, "USD")

    def test_reimporting_the_same_file_creates_no_duplicates(self):
        data = csv_bytes("date;type;ticker;quantite;prix", "2024-03-15;achat;SAN.PA;10;92,50")
        import_transactions(self.user, data)
        res = import_transactions(self.user, data)
        self.assertEqual((res.created, res.skipped_duplicates), (0, 1))
        self.assertEqual(Transaction.objects.count(), 1)

    def test_all_or_nothing_when_a_line_is_wrong(self):
        res = import_transactions(self.user, csv_bytes(
            "date;type;ticker;quantite;prix",
            "2024-03-15;achat;SAN.PA;10;92,50",
            "pas-une-date;achat;SAN.PA;1;1",
            "2024-03-16;echange;SAN.PA;1;1",
            "2024-03-17;achat;SAN.PA;-2;1",
        ))
        self.assertFalse(res.ok)
        self.assertEqual(len(res.errors), 3)
        self.assertIn("Ligne 3", res.errors[0])
        self.assertEqual((Transaction.objects.count(), Asset.objects.count()), (0, 0))

    def test_selling_more_than_held_rolls_everything_back(self):
        res = import_transactions(self.user, csv_bytes(
            "date;type;ticker;quantite;prix",
            "2024-03-15;achat;SAN.PA;10;92,50",
            "2024-04-15;vente;SAN.PA;11;95",
        ))
        self.assertFalse(res.ok)
        self.assertIn("Ligne 3", res.errors[0])
        self.assertEqual(Transaction.objects.count(), 0)

    def test_missing_columns_and_other_separators(self):
        _, errors = parse_rows(csv_bytes("date;type;ticker", "2024-01-01;achat;KO"))
        self.assertIn("Colonnes manquantes", errors[0])
        rows, errors = parse_rows(csv_bytes("Date,Sens,Symbole,Quantité,Cours", "2024-01-01,Buy,KO,2,60"))
        self.assertEqual(errors, [])
        self.assertEqual(rows[0]["ticker"], "KO")

    def test_amounts_with_thousand_separators(self):
        res = import_transactions(self.user, csv_bytes("date;type;ticker;quantite;prix", '2024-01-01;achat;MC.PA;1;"1 234,56"'))
        self.assertTrue(res.ok, res.errors)
        self.assertEqual(Transaction.objects.get().price, Decimal("1234.56"))

    def test_import_page_and_template_download(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("dividends-import")).status_code, 200)
        r = self.client.get(reverse("dividends-import-template"))
        self.assertIn("date;type;ticker", r.content.decode("utf-8"))
        up = StringIO("date;type;ticker;quantite;prix\n2024-01-01;achat;KO;2;60\n")
        up.name = "ops.csv"
        r = self.client.post(reverse("dividends-import"), {"file": up})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Transaction.objects.count(), 1)


class DashboardActionsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("u", "u@example.com", "pw-12345-abc")
        self.client.force_login(self.user)

    def test_buy_with_a_free_ticker_creates_the_asset(self):
        with mock.patch("dividends.services.instruments.lookup_instrument", return_value={"currency": "USD"}), \
             mock.patch("dividends.views.sync_asset_dividends", return_value=3) as sync:
            r = self.client.post(reverse("dividends-add-buy"), {"custom_ticker": "pep", "qty": "3", "price": "150", "date": "2024-05-01"})
        self.assertEqual(r.status_code, 302)
        asset = Asset.objects.get(user=self.user, ticker="PEP")
        self.assertEqual(asset.currency, "USD")
        self.assertEqual(asset.transactions.count(), 1)
        sync.assert_called_once()

    def test_unknown_ticker_is_refused_without_creating_anything(self):
        with mock.patch("dividends.services.instruments.lookup_instrument", return_value=None):
            self.client.post(reverse("dividends-add-buy"), {"custom_ticker": "NOPE", "qty": "3", "price": "150", "date": "2024-05-01"})
        self.assertEqual((Asset.objects.count(), Transaction.objects.count()), (0, 0))

    def test_cannot_sell_more_than_held(self):
        self.client.post(reverse("dividends-add-buy"), {"universe_key": "san.pa", "qty": "5", "price": "90", "date": "2024-05-01"})
        self.client.post(reverse("dividends-add-sell"), {"universe_key": "san.pa", "qty": "6", "price": "95", "date": "2024-06-01"})
        self.assertEqual(Transaction.objects.filter(type="SELL").count(), 0)

    def test_dashboard_and_calendar_render(self):
        self.assertEqual(self.client.get(reverse("dividends-dashboard")).status_code, 200)
        self.assertEqual(self.client.get(reverse("dividends-calendar") + "?y=abc&m=99").status_code, 200)
        self.assertEqual(self.client.get(reverse("dividends-dashboard") + "?y=99999999&g=zzz").status_code, 200)
        self.assertEqual(self.client.get(reverse("dividends-api-month-details") + "?y=2025&m=13").status_code, 400)
        self.assertEqual(self.client.get(reverse("dividends-dashboard") + "?g=NaN").status_code, 200)


class OutlookAndAlertsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("u", "u@example.com", "pw-12345-abc", first_name="Yann")
        self.asset = Asset.objects.create(user=self.user, ticker="SAN.PA", currency="EUR")
        Transaction.objects.create(asset=self.asset, type="BUY", date=date(2020, 1, 1), quantity=Decimal("10"), price=Decimal("80"))
        self.target = timezone.localdate() + timedelta(days=1)
        # Un dividende versé l'an dernier à la même date : la prévision le reporte à l'année en cours.
        last_year = date(self.target.year - 1, self.target.month, min(self.target.day, 28))
        DividendEvent.objects.create(asset=self.asset, ex_date=last_year, pay_date=last_year, amount_per_share=Decimal("3.00"))

    def test_next_12_months_counts_the_projected_dividend(self):
        total, months = next_12_months(self.user)
        self.assertEqual(len(months), 12)
        self.assertEqual(total, Decimal("30.00"))

    def test_alert_email_is_sent_only_to_opted_in_users(self):
        day = self.target if self.target.day <= 28 else date(self.target.year, self.target.month, 28)
        with mock.patch("dividends.management.commands.notify_dividends.timezone.localdate", return_value=day - timedelta(days=1)):
            call_command("notify_dividends", stdout=StringIO())
            self.assertEqual(len(mail.outbox), 0)  # alerte non activée
            DividendAlertSetting.objects.create(user=self.user, enabled=True)
            call_command("notify_dividends", stdout=StringIO())
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("SAN.PA", mail.outbox[0].body)
        self.assertEqual(mail.outbox[0].to, ["u@example.com"])

    def test_dry_run_sends_nothing(self):
        DividendAlertSetting.objects.create(user=self.user, enabled=True)
        day = self.target if self.target.day <= 28 else date(self.target.year, self.target.month, 28)
        with mock.patch("dividends.management.commands.notify_dividends.timezone.localdate", return_value=day - timedelta(days=1)):
            call_command("notify_dividends", "--dry-run", stdout=StringIO())
        self.assertEqual(len(mail.outbox), 0)
