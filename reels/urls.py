from django.urls import path
from . import views

app_name = "reels"

urlpatterns = [
    path("", views.ReelListView.as_view(), name="list"),
    path("new/", views.ReelCreateView.as_view(), name="create"),
    path("<int:pk>/", views.ReelDetailView.as_view(), name="detail"),
    path("<int:pk>/edit/", views.ReelUpdateView.as_view(), name="edit"),
    path("<int:pk>/delete/", views.ReelDeleteView.as_view(), name="delete"),
    path("<int:pk>/status/<slug:status>/", views.ReelSetStatusView.as_view(), name="set-status"),
    path("categories/new/", views.CategoryCreateView.as_view(), name="category-create"),
]