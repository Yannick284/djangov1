from django.shortcuts import render, get_object_or_404
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.views.generic import ListView
from django.views import View
from django.views.generic import TemplateView


from .models import Post
from .forms import CommentForm

from django.db.models import Q
from django.http import Http404

from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import CreateView
from django.urls import reverse_lazy
from .forms import PostForm
from .models import Post

# Create your views here.



# Function-based
# from django.contrib.auth.decorators import login_required

# @login_required
# def dashboard(request):
#     ...

# Class-based

# from django.contrib.auth.mixins import LoginRequiredMixin

# class DashboardView(LoginRequiredMixin, TemplateView):
#     template_name = "dashboard.html"

class StartingPageView(ListView):
    template_name = "blog/index.html"
    model = Post
    context_object_name = "posts"

    def get_queryset(self):
        qs = Post.objects.order_by("-date")
        if not self.request.user.is_authenticated:
            qs = qs.filter(is_public=True)
        return qs[:3]

class AllPostsView(ListView):
    template_name = "blog/all-posts.html"
    model = Post
    ordering = ["-date"]
    context_object_name = "all_posts"

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.user.is_authenticated:
            return qs  # connecté => voit tout (public + privé)
        return qs.filter(is_public=True)  # anonyme => seulement public

class SinglePostView(View):
    def is_stored_post(self, request, post_id):
        stored_posts = request.session.get("stored_posts")
        if stored_posts is not None:
          is_saved_for_later = post_id in stored_posts
        else:
          is_saved_for_later = False

        return is_saved_for_later

    def get(self, request, slug):
      post = get_object_or_404(Post, slug=slug)

      # Privé => uniquement si connecté
      if (not post.is_public) and (not request.user.is_authenticated):
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

        if (not post.is_public) and (not request.user.is_authenticated):
            raise Http404()

        comment_form = CommentForm(request.POST)

        if comment_form.is_valid():
            comment = comment_form.save(commit=False)
            comment.post = post
            comment.save()
            return HttpResponseRedirect(reverse("post-detail-page", args=[slug]))

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
        stored_posts = request.session.get("stored_posts")

        if not stored_posts:
            return render(request, "blog/stored-posts.html", {
                "posts": [],
                "has_posts": False,
            })

        posts = Post.objects.filter(id__in=stored_posts)

        # ⬇️ LIGNE AJOUTÉE
        if not request.user.is_authenticated:
            posts = posts.filter(is_public=True)

        return render(request, "blog/stored-posts.html", {
            "posts": posts,
            "has_posts": posts.exists(),
        })


    def post(self, request):
        stored_posts = request.session.get("stored_posts")

        if stored_posts is None:
          stored_posts = []

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