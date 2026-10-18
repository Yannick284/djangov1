import os
import subprocess
import sys
from pathlib import Path

from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
from django.test import TestCase
from django.urls import reverse

from dividends.models import DividendAlertSetting

User = get_user_model()
BASE = Path(__file__).resolve().parent.parent


class ProfileTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("yann", "y@example.com", "pw-12345-abc")

    def test_requires_login(self):
        self.assertEqual(self.client.get(reverse("profile")).status_code, 302)

    def test_update_name_and_alerts(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("profile")).status_code, 200)
        r = self.client.post(reverse("profile"), {"first_name": "Yannick", "last_name": "Wahl", "dividend_alerts": "on"})
        self.assertEqual(r.status_code, 302)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Yannick")
        self.assertTrue(DividendAlertSetting.objects.get(user=self.user).enabled)
        self.client.post(reverse("profile"), {"first_name": "Yannick", "last_name": "Wahl"})
        self.assertFalse(DividendAlertSetting.objects.get(user=self.user).enabled)


class AccountPagesTests(TestCase):
    def test_password_reset_pages_use_the_site_frame_in_french(self):
        r = self.client.get(reverse("account_reset_password"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Yannick Wahl")  # cadre du site
        self.assertContains(r, "ui-field")

    def test_password_reset_email_is_sent_with_the_real_domain(self):
        from django.core import mail

        User.objects.create_user("yann", "y@example.com", "pw-12345-abc")
        r = self.client.post(reverse("account_reset_password"), {"email": "y@example.com"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("http://testserver/accounts/password/reset/key/", mail.outbox[0].body)
        self.assertNotIn("example.com/accounts", mail.outbox[0].body)
        self.assertTrue(mail.outbox[0].subject.startswith("Yannick Wahl"))

    def test_site_domain_is_set_by_migration(self):
        self.assertEqual(Site.objects.get(pk=1).domain, "yannickwahl.fr")


class ProductionSettingsTests(TestCase):
    def run_settings(self, env):
        code = "import django,os;os.environ['DJANGO_SETTINGS_MODULE']='my_site.settings';from django.conf import settings;print(settings.DEBUG, bool(settings.SECRET_KEY))"
        full = {k: v for k, v in os.environ.items() if k not in ("ENV", "SECRET_KEY", "DJANGO_DEBUG", "DATABASE_URL")}
        full.update(env)
        return subprocess.run([sys.executable, "-c", code], cwd=BASE, env=full, capture_output=True, text=True)

    def test_production_refuses_to_start_without_secret_key(self):
        r = self.run_settings({"ENV": "prod", "AWS_ACCESS_KEY_ID": "x", "AWS_SECRET_ACCESS_KEY": "x"})
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("SECRET_KEY", r.stderr)

    def test_production_has_debug_off(self):
        r = self.run_settings({"ENV": "prod", "SECRET_KEY": "k" * 50, "AWS_ACCESS_KEY_ID": "x", "AWS_SECRET_ACCESS_KEY": "x"})
        self.assertEqual(r.stdout.strip(), "False True", r.stderr)

    def test_local_default_is_debug_on(self):
        self.assertEqual(self.run_settings({}).stdout.strip(), "True True")

    def test_superuser_script_has_no_hardcoded_password(self):
        text = (BASE / "my_site" / "create_superuser.py").read_text()
        self.assertNotIn('"admin"', text)
        self.assertIn("DJANGO_SUPERUSER_PASSWORD", text)
