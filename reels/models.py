from django.conf import settings
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from .utils import normalize_url

User = settings.AUTH_USER_MODEL


class Category(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="reel_categories")
    name = models.CharField(max_length=60)
    color = models.CharField(max_length=7, blank=True)  # ex: #FFAA00
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "name")
        ordering = ["name"]

    def __str__(self):
        return self.name


class Reel(models.Model):
    class Status(models.TextChoices):
        TO_TEST = "to_test", "À tester"
        TESTED = "tested", "Testé"
        APPROVED = "approved", "Validé"
        REJECTED = "rejected", "Rejeté"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="reels")
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, blank=True, related_name="reels"
    )

    url = models.URLField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.TO_TEST)

    rating = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(10)]
    )
    comment = models.TextField(blank=True)
    tags = models.CharField(max_length=200, blank=True)

    # Métadonnées Instagram (oEmbed plus tard)
    title = models.CharField(max_length=255, blank=True)
    author_name = models.CharField(max_length=255, blank=True)
    thumbnail = models.ImageField(upload_to="reels_thumbs/", blank=True, null=True)
    thumbnail_url = models.URLField(blank=True)
    embed_html = models.TextField(blank=True)
    fetch_error = models.CharField(max_length=255, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("user", "url")
        ordering = ["-created_at"]

    def __str__(self):
        return self.title or self.url
    
    from .utils import normalize_url

    def save(self, *args, **kwargs):
        self.url = normalize_url(self.url)
        super().save(*args, **kwargs)