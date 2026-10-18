from django.shortcuts import render, get_object_or_404
from django.http import HttpResponseRedirect, Http404
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import ListView, CreateView, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q

from .models import Post, Tag
from .forms import CommentForm, PostForm


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
        qs = Post.objects.order_by("-date").prefetch_related("tags")
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

        return qs.distinct().order_by("-date")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["q"] = self.request.GET.get("q", "").strip()
        ctx["current_tag"] = self.request.GET.get("tag", "").strip()
        ctx["tags"] = Tag.objects.filter(post__in=self.visible_posts()).distinct().order_by("caption")
        ctx["saved_count"] = len(self.request.session.get("stored_posts") or [])
        return ctx


class SinglePostView(View):
    def is_stored_post(self, request, post_id: int) -> bool:
        stored_posts = request.session.get("stored_posts") or []
        return post_id in stored_posts

    def get(self, request, slug):
        post = get_object_or_404(Post, slug=slug)

        if not post_is_accessible(post, request.user):
            raise Http404()

        context = {
            "post": post,
            "post_tags": post.tags.all(),
            "comment_form": CommentForm(),
            "comments": post.comments.all().order_by("-id"),
            "saved_for_later": self.is_stored_post(request, post.id),
        }
        return render(request, "blog/post-detail.html", context)

    def post(self, request, slug):
        post = get_object_or_404(Post, slug=slug)

        if not post_is_accessible(post, request.user):
            raise Http404()

        comment_form = CommentForm(request.POST)
        if comment_form.is_valid():
            comment = comment_form.save(commit=False)
            comment.post = post
            comment.save()
            return HttpResponseRedirect(reverse_lazy("post-detail-page", args=[slug]))

        context = {
            "post": post,
            "post_tags": post.tags.all(),
            "comment_form": comment_form,
            "comments": post.comments.all().order_by("-id"),
            "saved_for_later": self.is_stored_post(request, post.id),
        }
        return render(request, "blog/post-detail.html", context)


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


class CreatePostView(LoginRequiredMixin, CreateView):
    model = Post
    form_class = PostForm
    template_name = "blog/post-form.html"
    success_url = reverse_lazy("posts-page")

    def form_valid(self, form):
        form.instance.owner = self.request.user
        return super().form_valid(form)


class CVView(TemplateView):
    template_name = "cv/cv.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["cv_url"] = (
            "https://django-media-yannicks3.s3.amazonaws.com/"
            "CV_Yannick_Wahl_2025.pdf"
        )
        return context
