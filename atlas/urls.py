from django.urls import path

from .views import AtlasView

urlpatterns = [
    path("atlas/", AtlasView.as_view(), name="atlas"),
]
