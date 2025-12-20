from django.shortcuts import render, get_object_or_404
from django.http import HttpResponseRedirect, Http404
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import ListView, CreateView, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q

from .models import Post
from .forms import CommentForm, PostForm


def user_is_admin(user) -> bool:
    """Users allowed to read 'admin-only' posts.

    - Django superusers are always allowed
    - Any user in the 'Admin' group is allowed (you can manage this in /admin)
    """
    return (
        user.is_authenticated
        and (user.is_superuser or user.groups.filter(name="Admin").exists())
    )


def post_is_accessible(post: Post, user) -> bool:
    if post.is_public:
        return True
    if getattr(post, "is_admin_only", False):
        return user_is_admin(user)
    return user.is_authenticated


class StartingPageView(ListView):
    template_name = "blog/index.html"
    model = Post
    context_object_name = "posts"

    def get_queryset(self):
        qs = Post.objects.order_by("-date")
        user = self.request.user

        if not user.is_authenticated:
            return qs.filter(is_public=True)[:3]

        if user_is_admin(user):
            return qs[:3]

        # Connected but not admin: public + non-public (excluding admin-only)
        return qs.filter(Q(is_public=True) | Q(is_public=False, is_admin_only=False))[:3]


class AllPostsView(ListView):
    template_name = "blog/all-posts.html"
    model = Post
    ordering = ["-date"]
    context_object_name = "all_posts"

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user

        if not user.is_authenticated:
            return qs.filter(is_public=True)

        if user_is_admin(user):
            return qs

        return qs.filter(Q(is_public=True) | Q(is_public=False, is_admin_only=False))


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
            qs = qs.filter(is_public=True)
        elif not user_is_admin(user):
            qs = qs.filter(Q(is_public=True) | Q(is_public=False, is_admin_only=False))

        posts = qs.order_by("-date")

        return render(
            request,
            "blog/stored-posts.html",
            {"posts": posts, "has_posts": posts.exists()},
        )

    def post(self, request):
        stored_posts = request.session.get("stored_posts") or []

        post_id = int(request.POST["post_id"])

        if post_id not in stored_posts:
            stored_posts.append(post_id)
        else:
            stored_posts.remove(post_id)

        request.session["stored_posts"] = stored_posts
        return HttpResponseRedirect("/")


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
