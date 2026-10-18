from django.contrib import messages
from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponseRedirect, Http404, JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import ListView, CreateView, DetailView, TemplateView, UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin, UserPassesTestMixin
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.db.models import Q

from .models import Comment, Post, Project, Tag
from .feeds import LatestPostsFeed
from .forms import CommentForm, PostForm
from .templatetags.blog_extras import render_markdown


def post_is_accessible(post: Post, user) -> bool:
    """Access rules:

    - Public post -> accessible by anyone
    - Superuser-only post -> only authenticated superusers
    - Non-public post -> authenticated users
    """
    if post.is_public:
        # Even if someone accidentally marks a post public + superuser-only,
        # we still treat it as restricted.
        if getattr(post, "is_superuser_only", False):
            return user.is_authenticated and user.is_superuser
        return True

    if getattr(post, "is_superuser_only", False):
        return user.is_authenticated and user.is_superuser

    return user.is_authenticated


class StartingPageView(ListView):
    template_name = "blog/index.html"
    model = Post
    context_object_name = "posts"

    def get_queryset(self):
        qs = Post.objects.order_by("-date", "-id").prefetch_related("tags")
        user = self.request.user

        if not user.is_authenticated:
            # Public only, and never show superuser-only
            return qs.filter(is_public=True, is_superuser_only=False)[:3]

        if user.is_superuser:
            return qs[:3]

        # Authenticated but not superuser:
        # - public (excluding superuser-only)
        # - non-public (excluding superuser-only)
        return qs.filter(
            Q(is_public=True, is_superuser_only=False)
            | Q(is_public=False, is_superuser_only=False)
        )[:3]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        ctx["featured_projects"] = Project.objects.filter(is_public=True)[:3]
        if user.is_authenticated:
            # Chiffres affichés dans la bande « Mes outils » de l'accueil
            from dividends.models import Asset
            from immo.models import Property
            from reels.models import Reel

            ctx["tool_stats"] = {
                "immo": Property.objects.filter(user=user).count(),
                "dividends": Asset.objects.filter(user=user, is_active=True).count(),
                "reels": Reel.objects.filter(user=user).count(),
            }
        return ctx


class AllPostsView(ListView):
    template_name = "blog/all-posts.html"
    model = Post
    context_object_name = "all_posts"

    def visible_posts(self):
        """Tous les articles que l'utilisateur a le droit de voir (avant filtres)."""
        qs = Post.objects.prefetch_related("tags")
        user = self.request.user

        if not user.is_authenticated:
            return qs.filter(is_public=True, is_superuser_only=False)
        if user.is_superuser:
            return qs
        return qs.filter(is_superuser_only=False)

    def get_queryset(self):
        qs = self.visible_posts()
        q = self.request.GET.get("q", "").strip()
        tag = self.request.GET.get("tag", "").strip()

        if q:
            qs = qs.filter(
                Q(title__icontains=q) | Q(excerpt__icontains=q) | Q(content__icontains=q)
            )
        if tag:
            qs = qs.filter(tags__caption=tag)

        return qs.distinct().order_by("-date", "-id")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["q"] = self.request.GET.get("q", "").strip()
        ctx["current_tag"] = self.request.GET.get("tag", "").strip()
        ctx["tags"] = Tag.objects.filter(post__in=self.visible_posts()).distinct().order_by("caption")
        ctx["saved_count"] = len(self.request.session.get("stored_posts") or [])
        return ctx


class SinglePostView(View):
    COMMENT_DELAY_SECONDS = 20

    def is_stored_post(self, request, post_id: int) -> bool:
        stored_posts = request.session.get("stored_posts") or []
        return post_id in stored_posts

    def build_context(self, request, post, comment_form):
        is_admin = request.user.is_authenticated and request.user.is_superuser
        return {
            "post": post,
            "post_tags": post.tags.all(),
            "comment_form": comment_form,
            "comments": post.comments.filter(is_approved=True).order_by("-id"),
            "pending_comments": post.comments.filter(is_approved=False).order_by("id") if is_admin else [],
            "can_edit": can_edit_post(request.user, post),
            "saved_for_later": self.is_stored_post(request, post.id),
        }

    def get(self, request, slug):
        post = get_object_or_404(Post, slug=slug)
        if not post_is_accessible(post, request.user):
            raise Http404()
        return render(request, "blog/post-detail.html", self.build_context(request, post, CommentForm()))

    def post(self, request, slug):
        post = get_object_or_404(Post, slug=slug)
        if not post_is_accessible(post, request.user):
            raise Http404()

        comment_form = CommentForm(request.POST)
        back = reverse_lazy("post-detail-page", args=[slug])

        if comment_form.is_valid():
            # Robot : on fait comme si tout allait bien, sans rien enregistrer.
            if comment_form.cleaned_data.get("website"):
                return HttpResponseRedirect(back)

            last = request.session.get("last_comment_at") or 0
            now = timezone.now().timestamp()
            if now - last < self.COMMENT_DELAY_SECONDS:
                comment_form.add_error(None, "Un instant : attends quelques secondes avant d'envoyer un autre commentaire.")
            else:
                comment = comment_form.save(commit=False)
                comment.post = post
                is_admin = request.user.is_authenticated and request.user.is_superuser
                comment.is_approved = is_admin
                comment.save()
                request.session["last_comment_at"] = now
                if is_admin:
                    messages.success(request, "Commentaire publié.")
                else:
                    messages.success(request, "Merci ! Ton commentaire sera visible après validation.")
                return HttpResponseRedirect(f"{back}#comments-title")

        return render(request, "blog/post-detail.html", self.build_context(request, post, comment_form))


def can_edit_post(user, post) -> bool:
    if not user.is_authenticated:
        return False
    return user.is_superuser or (post.owner_id == user.id and user.has_perm("blog.add_post"))


@require_POST
def moderate_comment(request, pk: int, action: str):
    """Approuver ou supprimer un commentaire (superuser uniquement)."""
    if not (request.user.is_authenticated and request.user.is_superuser):
        raise Http404()
    comment = get_object_or_404(Comment.objects.select_related("post"), pk=pk)
    slug = comment.post.slug
    if action == "approve":
        comment.is_approved = True
        comment.save(update_fields=["is_approved"])
        messages.success(request, "Commentaire approuvé.")
    elif action == "delete":
        comment.delete()
        messages.success(request, "Commentaire supprimé.")
    else:
        raise Http404()
    return redirect(f"{reverse_lazy('post-detail-page', args=[slug])}#comments-title")


class ReadLaterView(View):
    def get(self, request):
        stored_posts = request.session.get("stored_posts") or []

        if not stored_posts:
            return render(
                request,
                "blog/stored-posts.html",
                {"posts": [], "has_posts": False},
            )

        qs = Post.objects.filter(id__in=stored_posts)
        user = request.user

        if not user.is_authenticated:
            qs = qs.filter(is_public=True, is_superuser_only=False)
        elif not user.is_superuser:
            qs = qs.filter(is_superuser_only=False)

        posts = qs.order_by("-date")

        return render(
            request,
            "blog/stored-posts.html",
            {"posts": posts, "has_posts": posts.exists()},
        )

    def post(self, request):
        stored_posts = request.session.get("stored_posts") or []

        try:
            post_id = int(request.POST.get("post_id", ""))
        except ValueError:
            return HttpResponseRedirect(reverse_lazy("read-later"))

        if post_id not in stored_posts:
            stored_posts.append(post_id)
        else:
            stored_posts.remove(post_id)

        request.session["stored_posts"] = stored_posts

        # Depuis la liste : on y reste. Depuis un article : on y revient.
        if request.POST.get("from") == "list":
            return HttpResponseRedirect(reverse_lazy("read-later"))
        post = Post.objects.filter(pk=post_id).only("slug").first()
        if post:
            return HttpResponseRedirect(reverse_lazy("post-detail-page", args=[post.slug]))
        return HttpResponseRedirect(reverse_lazy("read-later"))


class CreatePostView(PermissionRequiredMixin, CreateView):
    """Réservé aux comptes autorisés (superuser, ou permission « blog.add_post » donnée dans l'admin)."""

    permission_required = "blog.add_post"
    model = Post
    form_class = PostForm
    template_name = "blog/post-form.html"

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return redirect_to_login(self.request.get_full_path())
        raise PermissionDenied

    def form_valid(self, form):
        form.instance.owner = self.request.user
        response = super().form_valid(form)
        messages.success(self.request, "Article publié.")
        return response

    def get_success_url(self):
        return reverse_lazy("post-detail-page", args=[self.object.slug])


class UpdatePostView(UserPassesTestMixin, UpdateView):
    model = Post
    form_class = PostForm
    template_name = "blog/post-form.html"
    slug_field = "slug"
    slug_url_kwarg = "slug"

    def test_func(self):
        return can_edit_post(self.request.user, self.get_object())

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return redirect_to_login(self.request.get_full_path())
        raise PermissionDenied

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Article mis à jour.")
        return response

    def get_success_url(self):
        return reverse_lazy("post-detail-page", args=[self.object.slug])


@require_POST
def preview_markdown(request):
    """Aperçu du Markdown pendant la rédaction (comptes autorisés uniquement)."""
    if not (request.user.is_authenticated and request.user.has_perm("blog.add_post")):
        raise PermissionDenied
    return JsonResponse({"html": render_markdown(request.POST.get("content", ""))})


class ProjectListView(ListView):
    template_name = "blog/projects.html"
    context_object_name = "projects"

    def get_queryset(self):
        qs = Project.objects.all()
        if not self.request.user.is_authenticated:
            qs = qs.filter(is_public=True)
        return qs


class ProjectDetailView(DetailView):
    template_name = "blog/project-detail.html"
    context_object_name = "project"
    model = Project

    def get_queryset(self):
        qs = Project.objects.all()
        if not self.request.user.is_authenticated:
            qs = qs.filter(is_public=True)
        return qs


def rss_feed(request):
    return LatestPostsFeed(request)(request)


class CVView(TemplateView):
    template_name = "cv/cv.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["cv_url"] = (
            "https://django-media-yannicks3.s3.amazonaws.com/"
            "CV_Yannick_Wahl_2025.pdf"
        )
        return context
