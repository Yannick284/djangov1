from datetime import datetime, time

from django.contrib.syndication.views import Feed
from django.urls import reverse
from django.utils import timezone

from .models import Post


class LatestPostsFeed(Feed):
    """Flux RSS des derniers articles publics. Une instance par requête (liens absolus basés sur l'hôte réel)."""

    title = "Yannick Wahl · Notes & projets"
    description = "Ce que je construis, et ce que j'en apprends."

    def __init__(self, request):
        self.request = request

    def link(self):
        return self.request.build_absolute_uri(reverse("starting-page"))

    def feed_url(self):
        return self.request.build_absolute_uri(self.request.path)

    def items(self):
        return Post.objects.filter(is_public=True, is_superuser_only=False).order_by("-date", "-id")[:20]

    def item_title(self, item):
        return item.title

    def item_description(self, item):
        return item.excerpt

    def item_link(self, item):
        return self.request.build_absolute_uri(reverse("post-detail-page", args=[item.slug]))

    def item_pubdate(self, item):
        return timezone.make_aware(datetime.combine(item.date, time.min))
