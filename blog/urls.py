from django.urls import path
from .views import CVView
from django.views.generic import TemplateView


from . import views

urlpatterns = [
    path("", views.StartingPageView.as_view(), name="starting-page"),
    path("posts", views.AllPostsView.as_view(), name="posts-page"),
    path("posts/<slug:slug>", views.SinglePostView.as_view(),
         name="post-detail-page"),  # /posts/my-first-post
    path("read-later", views.ReadLaterView.as_view(), name="read-later"),
    # blog/urls.py
    path("posts/new/", views.CreatePostView.as_view(), name="post-create"),
    path("cv/", CVView.as_view(), name="cv"),
    path("legal/", TemplateView.as_view(template_name="legal.html"), name="legal"),
]
