from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Expense, Loan, Property, RentPeriod
from .services.ledger import build_ledger, monthly_payment, rent_for_month
from .services.loan_schedule import balance_after_months, payment_amount

User = get_user_model()


class FinanceCalculationTests(TestCase):
    def test_monthly_payment_matches_the_textbook_value(self):
        # 200 000 € à 3 % sur 20 ans : 1 109,20 € par mois
        self.assertEqual(monthly_payment(Decimal("200000"), Decimal("3"), 20), Decimal("1109.20"))
        self.assertEqual(payment_amount(Decimal("200000"), Decimal("3"), 20), Decimal("1109.20"))

    def test_zero_rate_loan_is_a_simple_division(self):
        self.assertEqual(monthly_payment(Decimal("12000"), Decimal("0"), 1), Decimal("1000.00"))

    def test_remaining_balance_decreases_and_ends_at_zero(self):
        start = balance_after_months(Decimal("100000"), Decimal("2"), 10, 0)
        mid = balance_after_months(Decimal("100000"), Decimal("2"), 10, 60)
        end = balance_after_months(Decimal("100000"), Decimal("2"), 10, 120)
        self.assertEqual(start["crd"], Decimal("100000.00"))
        self.assertLess(mid["crd"], start["crd"])
        self.assertEqual(end["crd"], Decimal("0.00"))
        # capital remboursé + capital restant = capital emprunté
        self.assertEqual(mid["capital_paid"] + mid["crd"], Decimal("100000.00"))

    def test_first_rent_month_is_prorated_by_days(self):
        user = User.objects.create_user("u", "u@example.com", "pw-12345-abc")
        prop = Property.objects.create(user=user, name="B", purchase_date=date(2025, 1, 1))
        period = RentPeriod.objects.create(property=prop, start_date=date(2025, 10, 16), rent_hc=Decimal("930"), charges=Decimal("31"))
        rent, charges = rent_for_month([period], date(2025, 10, 1))
        # 16 octobre → 1er novembre = 16 jours sur 31
        self.assertEqual(rent, (Decimal("930") * 16 / 31).quantize(Decimal("0.01")))
        self.assertEqual(charges, (Decimal("31") * 16 / 31).quantize(Decimal("0.01")))
        self.assertEqual(rent_for_month([period], date(2025, 9, 1)), (Decimal("0"), Decimal("0")))
        self.assertEqual(rent_for_month([period], date(2025, 11, 1))[0], Decimal("930.00"))

    def test_ledger_adds_rent_and_subtracts_loan_and_expenses(self):
        user = User.objects.create_user("u", "u@example.com", "pw-12345-abc")
        prop = Property.objects.create(user=user, name="B", purchase_date=date(2025, 1, 1))
        Loan.objects.create(property=prop, borrowed_capital=Decimal("120000"), annual_rate=Decimal("0"), years=10, insurance_monthly=Decimal("10"), start_date=date(2025, 1, 1))
        RentPeriod.objects.create(property=prop, start_date=date(2025, 1, 1), rent_hc=Decimal("900"), charges=Decimal("100"))
        Expense.objects.create(property=prop, date=date(2025, 2, 10), amount=Decimal("300"), category="works")
        rows = build_ledger(prop, date(2025, 2, 28))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0].net_cashflow, Decimal("1000") - Decimal("1000") - Decimal("10"))  # loyer+charges − mensualité − assurance
        self.assertEqual(rows[1].net_cashflow, Decimal("-10") - Decimal("300"))
        self.assertEqual(rows[1].cum_cashflow, rows[0].net_cashflow + rows[1].net_cashflow)


class ImmoViewsTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user("alice", "a@example.com", "pw-alice-123")
        self.bob = User.objects.create_user("bob", "b@example.com", "pw-bob-12345")
        self.prop = Property.objects.create(user=self.alice, name="T2 Lyon", purchase_date=date(2024, 1, 1), purchase_price=Decimal("200000"), surface_sqm=Decimal("40"))

    def test_login_required(self):
        for name in ("immo:property-list", "immo:property-create"):
            self.assertEqual(self.client.get(reverse(name)).status_code, 302)
        self.assertEqual(self.client.get(reverse("immo:property-manage", args=[self.prop.pk])).status_code, 302)

    def test_other_users_get_404_everywhere(self):
        self.client.force_login(self.bob)
        for name in ("immo:immo-dashboard", "immo:property-manage", "immo:immo-export-csv", "immo:property-edit", "immo:immo-summary"):
            self.assertEqual(self.client.get(reverse(name, args=[self.prop.pk])).status_code, 404, name)
        r = self.client.post(reverse("immo:property-manage", args=[self.prop.pk]), {"action": "property-delete", "confirm_name": "T2 Lyon"})
        self.assertEqual(r.status_code, 404)
        self.assertTrue(Property.objects.filter(pk=self.prop.pk).exists())

    def test_invalid_query_parameters_do_not_crash_the_dashboard(self):
        self.client.force_login(self.alice)
        url = reverse("immo:immo-dashboard", args=[self.prop.pk])
        self.assertEqual(self.client.get(url + "?end=pas-une-date&growth=abc").status_code, 200)
        self.assertEqual(self.client.get(url + "?growth=NaN").status_code, 200)
        self.assertEqual(self.client.get(url + "?growth=Infinity").status_code, 200)
        self.assertEqual(self.client.get(reverse("immo:immo-ledger", args=[self.prop.pk]) + "?end=2025-13-45").status_code, 200)

    def test_dashboard_no_longer_depends_on_an_external_chart_library(self):
        self.client.force_login(self.alice)
        r = self.client.get(reverse("immo:immo-dashboard", args=[self.prop.pk]))
        self.assertNotContains(r, "cdn.jsdelivr.net")

    def test_manage_loan_rent_and_expense_lifecycle(self):
        self.client.force_login(self.alice)
        url = reverse("immo:property-manage", args=[self.prop.pk])

        r = self.client.post(url, {"action": "loan-save", "loan-borrowed_capital": "150000", "loan-annual_rate": "1.4", "loan-years": "25", "loan-insurance_monthly": "30", "loan-start_date": "2024-02-01"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Loan.objects.get(property=self.prop).years, 25)
        # Modifier le prêt ne crée pas de second prêt
        self.client.post(url, {"action": "loan-save", "loan-borrowed_capital": "140000", "loan-annual_rate": "1.4", "loan-years": "20", "loan-insurance_monthly": "30", "loan-start_date": "2024-02-01"})
        self.assertEqual(Loan.objects.filter(property=self.prop).count(), 1)
        self.assertEqual(Loan.objects.get(property=self.prop).borrowed_capital, Decimal("140000"))

        self.client.post(url, {"action": "rent-add", "rent-start_date": "2024-03-01", "rent-rent_hc": "800", "rent-charges": "50"})
        self.assertEqual(self.prop.rent_periods.count(), 1)
        self.client.post(url, {"action": "expense-add", "exp-date": "2024-04-01", "exp-amount": "250.50", "exp-category": "works", "exp-note": "Peinture"})
        exp = self.prop.expenses.get()
        self.assertEqual(exp.amount, Decimal("250.50"))

        self.assertContains(self.client.get(url), "Peinture")
        self.client.post(url, {"action": "expense-delete", "item_id": exp.pk})
        self.client.post(url, {"action": "rent-delete", "item_id": self.prop.rent_periods.get().pk})
        self.client.post(url, {"action": "loan-delete"})
        self.assertEqual((self.prop.expenses.count(), self.prop.rent_periods.count(), Loan.objects.filter(property=self.prop).count()), (0, 0, 0))

    def test_invalid_forms_show_errors_and_save_nothing(self):
        self.client.force_login(self.alice)
        url = reverse("immo:property-manage", args=[self.prop.pk])
        r = self.client.post(url, {"action": "expense-add", "exp-date": "2024-04-01", "exp-amount": "-5", "exp-category": "works"})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Le montant doit être positif")
        r = self.client.post(url, {"action": "rent-add", "rent-start_date": "2024-05-01", "rent-end_date": "2024-04-01", "rent-rent_hc": "800", "rent-charges": "0"})
        self.assertContains(r, "avant la date de début")
        self.assertEqual(self.prop.expenses.count() + self.prop.rent_periods.count(), 0)

    def test_cannot_delete_other_peoples_items_through_my_property(self):
        other = Property.objects.create(user=self.bob, name="Autre", purchase_date=date(2024, 1, 1))
        foreign = Expense.objects.create(property=other, date=date(2024, 1, 5), amount=Decimal("10"), category="tax")
        self.client.force_login(self.alice)
        self.client.post(reverse("immo:property-manage", args=[self.prop.pk]), {"action": "expense-delete", "item_id": foreign.pk})
        self.assertTrue(Expense.objects.filter(pk=foreign.pk).exists())

    def test_deleting_a_property_requires_its_exact_name(self):
        self.client.force_login(self.alice)
        url = reverse("immo:property-manage", args=[self.prop.pk])
        self.client.post(url, {"action": "property-delete", "confirm_name": "mauvais"})
        self.assertTrue(Property.objects.filter(pk=self.prop.pk).exists())
        r = self.client.post(url, {"action": "property-delete", "confirm_name": "T2 Lyon"})
        self.assertRedirects(r, reverse("immo:property-list"))
        self.assertFalse(Property.objects.filter(pk=self.prop.pk).exists())

    def test_csv_export_is_excel_friendly(self):
        RentPeriod.objects.create(property=self.prop, start_date=date(2024, 1, 1), rent_hc=Decimal("800.50"), charges=Decimal("0"))
        self.client.force_login(self.alice)
        r = self.client.get(reverse("immo:immo-export-csv", args=[self.prop.pk]) + "?end=2024-02-28")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r["Content-Type"].startswith("text/csv"))
        self.assertIn("attachment", r["Content-Disposition"])
        text = r.content.decode("utf-8")
        self.assertTrue(text.startswith("﻿Mois;Loyer hors charges"))
        lines = text.strip().split("\r\n")
        self.assertEqual(len(lines), 3)  # en-tête + janvier + février
        self.assertTrue(lines[1].startswith("01/2024;800,50;"))
