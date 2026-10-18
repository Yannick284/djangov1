from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from .models import Comment, Post, Project
from .templatetags.blog_extras import render_markdown

User = get_user_model()


def make_post(**kw):
    defaults = dict(title="Un article", excerpt="Résumé", content="Texte", is_public=True)
    defaults.update(kw)
    return Post.objects.create(**defaults)


class PostPermissionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("bob", "bob@example.com", "pw-bob-12345")
        self.admin = User.objects.create_superuser("root", "root@example.com", "pw-root-12345")

    def test_anonymous_is_sent_to_login(self):
        r = self.client.get(reverse("post-create"))
        self.assertEqual(r.status_code, 302)
        self.assertIn("/accounts/login/", r["Location"])

    def test_regular_user_cannot_create_posts(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("post-create")).status_code, 403)
        r = self.client.post(reverse("post-create"), {"title": "x", "excerpt": "x", "content": "x"})
        self.assertEqual(r.status_code, 403)
        self.assertEqual(Post.objects.count(), 0)

    def test_superuser_can_create_with_new_tags(self):
        self.client.force_login(self.admin)
        r = self.client.post(
            reverse("post-create"),
            {"title": "Mon titre", "excerpt": "Résumé", "content": "**gras**", "is_public": "on", "new_tags": "django, python"},
        )
        self.assertEqual(r.status_code, 302)
        post = Post.objects.get(title="Mon titre")
        self.assertEqual(post.owner, self.admin)
        self.assertEqual(sorted(t.caption for t in post.tags.all()), ["django", "python"])

    def test_user_with_permission_can_create_and_edit_own_post_only(self):
        self.user.user_permissions.add(Permission.objects.get(codename="add_post"))
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("post-create")).status_code, 200)
        mine = make_post(title="À moi", owner=self.user)
        other = make_post(title="Autre", owner=self.admin)
        self.assertEqual(self.client.get(reverse("post-edit", args=[mine.slug])).status_code, 200)
        self.assertEqual(self.client.get(reverse("post-edit", args=[other.slug])).status_code, 403)

    def test_editing_keeps_the_publication_date(self):
        self.client.force_login(self.admin)
        post = make_post(owner=self.admin)
        Post.objects.filter(pk=post.pk).update(date="2020-01-02")
        self.client.post(reverse("post-edit", args=[post.slug]), {"title": "Nouveau titre", "excerpt": "R", "content": "C", "is_public": "on"})
        post.refresh_from_db()
        self.assertEqual(post.title, "Nouveau titre")
        self.assertEqual(str(post.date), "2020-01-02")

    def test_preview_requires_permission(self):
        self.assertEqual(self.client.post(reverse("post-preview"), {"content": "x"}).status_code, 403)
        self.client.force_login(self.admin)
        r = self.client.post(reverse("post-preview"), {"content": "**gras**"})
        self.assertIn("<strong>gras</strong>", r.json()["html"])


class MarkdownTests(TestCase):
    def test_scripts_and_event_handlers_are_removed(self):
        html = render_markdown('<script>alert(1)</script>\n\n<img src="x" onerror="alert(1)">\n\n[x](javascript:alert(1))')
        self.assertNotIn("<script", html)
        self.assertNotIn("onerror", html)
        self.assertNotIn("javascript:", html)

    def test_basic_markdown_is_rendered(self):
        html = render_markdown("# Titre\n\n- a\n- b\n\nligne 1\nligne 2")
        self.assertIn("<h2>Titre</h2>", html)  # « # » devient h2 : le titre de la page reste l'unique h1
        self.assertEqual(render_markdown("## A\n\n#### B"), "<h3>A</h3>\n<h4>B</h4>")
        self.assertIn("<li>a</li>", html)
        self.assertIn("<br", html)


class CommentModerationTests(TestCase):
    def setUp(self):
        self.post = make_post()
        self.url = reverse("post-detail-page", args=[self.post.slug])
        self.admin = User.objects.create_superuser("root", "root@example.com", "pw-root-12345")
        self.data = {"user_name": "Alice", "user_email": "a@example.com", "text": "Bravo !", "website": ""}

    def test_new_comment_waits_for_approval(self):
        r = self.client.post(self.url, self.data)
        self.assertEqual(r.status_code, 302)
        c = Comment.objects.get()
        self.assertFalse(c.is_approved)
        self.assertNotContains(self.client.get(self.url), "Bravo !")

    def test_admin_sees_pending_and_can_approve(self):
        self.client.post(self.url, self.data)
        c = Comment.objects.get()
        self.client.force_login(self.admin)
        self.assertContains(self.client.get(self.url), "À valider")
        self.client.post(reverse("comment-moderate", args=[c.pk, "approve"]))
        c.refresh_from_db()
        self.assertTrue(c.is_approved)
        self.client.logout()
        self.assertContains(self.client.get(self.url), "Bravo !")

    def test_visitors_cannot_moderate(self):
        c = Comment.objects.create(post=self.post, user_name="x", user_email="x@example.com", text="t")
        self.assertEqual(self.client.post(reverse("comment-moderate", args=[c.pk, "approve"])).status_code, 404)
        c.refresh_from_db()
        self.assertFalse(c.is_approved)

    def test_honeypot_discards_robot_comments(self):
        self.client.post(self.url, {**self.data, "website": "http://spam.example"})
        self.assertEqual(Comment.objects.count(), 0)

    def test_second_comment_too_fast_is_refused(self):
        self.client.post(self.url, self.data)
        self.client.post(self.url, {**self.data, "text": "Encore"})
        self.assertEqual(Comment.objects.count(), 1)

    def test_admin_comments_are_published_immediately(self):
        self.client.force_login(self.admin)
        self.client.post(self.url, self.data)
        self.assertTrue(Comment.objects.get().is_approved)


class PublicPagesTests(TestCase):
    def test_rss_lists_only_public_posts_with_absolute_links(self):
        make_post(title="Visible")
        make_post(title="Privé", is_public=False)
        make_post(title="Admin", is_superuser_only=True)
        r = self.client.get(reverse("rss"))
        self.assertEqual(r.status_code, 200)
        body = r.content.decode()
        self.assertIn("Visible", body)
        self.assertNotIn("Privé", body)
        self.assertNotIn("Admin", body)
        self.assertIn("http://testserver/posts/visible", body)

    def test_projects_pages_respect_visibility(self):
        Project.objects.create(title="Public", slug="public", summary="s", is_public=True)
        Project.objects.create(title="Secret", slug="secret", summary="s", is_public=False)
        r = self.client.get(reverse("projects"))
        self.assertContains(r, "Public")
        self.assertNotContains(r, "Secret")
        self.assertEqual(self.client.get(reverse("project-detail", args=["secret"])).status_code, 404)
        self.assertEqual(self.client.get(reverse("project-detail", args=["public"])).status_code, 200)

    def test_post_page_has_share_tags(self):
        post = make_post(title="Partage", excerpt="Pour les réseaux")
        r = self.client.get(reverse("post-detail-page", args=[post.slug]))
        self.assertContains(r, 'property="og:title" content="Partage"')
        self.assertContains(r, 'property="og:type" content="article"')

    def test_home_and_list_render_without_images(self):
        make_post()
        self.assertEqual(self.client.get(reverse("starting-page")).status_code, 200)
        self.assertEqual(self.client.get(reverse("posts-page")).status_code, 200)
        self.assertEqual(self.client.get(reverse("posts-page") + "?q=zzz&tag=nope").status_code, 200)
