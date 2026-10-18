from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .forms import ReelForm
from .models import Category, Reel

User = get_user_model()


class ReelsIsolationTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user("alice", "a@example.com", "pw-alice-123")
        self.bob = User.objects.create_user("bob", "b@example.com", "pw-bob-12345")
        self.private = Category.objects.create(user=self.alice, name="Secret d'Alice")
        self.reel = Reel.objects.create(user=self.alice, url="https://example.com/r/1", title="Reel d'Alice", category=self.private)

    def test_other_users_do_not_see_the_category_or_reel(self):
        self.client.force_login(self.bob)
        r = self.client.get(reverse("reels:list"))
        self.assertNotContains(r, "Secret d&#x27;Alice")
        self.assertNotContains(r, "Reel d&#x27;Alice")
        r = self.client.get(reverse("reels:create"))
        self.assertNotContains(r, "Secret d&#x27;Alice")

    def test_form_rejects_a_category_of_someone_else(self):
        form = ReelForm({"url": "https://example.com/r/2", "status": "to_test", "category": self.private.pk}, user=self.bob)
        self.assertFalse(form.is_valid())
        self.assertIn("category", form.errors)

    def test_cannot_open_edit_or_delete_someone_elses_reel(self):
        self.client.force_login(self.bob)
        self.assertEqual(self.client.get(reverse("reels:detail", args=[self.reel.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("reels:delete", args=[self.reel.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("reels:set-status", args=[self.reel.pk, "approved"])).status_code, 404)
        self.assertTrue(Reel.objects.filter(pk=self.reel.pk).exists())

    def test_category_rename_and_delete_are_owner_only(self):
        self.client.force_login(self.bob)
        self.assertEqual(self.client.post(reverse("reels:category-rename", args=[self.private.pk]), {"name": "Piraté"}).status_code, 404)
        self.assertEqual(self.client.post(reverse("reels:category-delete", args=[self.private.pk])).status_code, 404)
        self.client.force_login(self.alice)
        self.client.post(reverse("reels:category-rename", args=[self.private.pk]), {"name": "Renommée"})
        self.private.refresh_from_db()
        self.assertEqual(self.private.name, "Renommée")

    def test_deleting_a_category_keeps_its_reels(self):
        self.client.force_login(self.alice)
        self.client.post(reverse("reels:category-delete", args=[self.private.pk]))
        self.reel.refresh_from_db()
        self.assertIsNone(self.reel.category)

    def test_duplicate_category_name_is_refused(self):
        self.client.force_login(self.alice)
        self.client.post(reverse("reels:categories"), {"name": "secret d'alice"})
        self.assertEqual(Category.objects.filter(user=self.alice).count(), 1)

    def test_search_and_status_filter(self):
        Reel.objects.create(user=self.alice, url="https://example.com/r/3", title="Recette tarte", tags="cuisine", status="approved")
        self.client.force_login(self.alice)
        r = self.client.get(reverse("reels:list") + "?q=cuisine")
        self.assertContains(r, "Recette tarte")
        self.assertNotContains(r, "Reel d&#x27;Alice")
        r = self.client.get(reverse("reels:list") + "?status=approved&category=abc&order=zzz")
        self.assertEqual(r.status_code, 200)

    def test_status_change_only_redirects_inside_reels(self):
        self.client.force_login(self.alice)
        r = self.client.post(reverse("reels:set-status", args=[self.reel.pk, "approved"]), {"next": "https://evil.example/"})
        self.assertEqual(r["Location"], reverse("reels:list"))
        self.reel.refresh_from_db()
        self.assertEqual(self.reel.status, "approved")
