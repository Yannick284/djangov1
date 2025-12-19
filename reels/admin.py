from django.contrib import admin
from .models import Reel, Category


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "created_at")
    list_filter = ("user",)
    search_fields = ("name",)


@admin.register(Reel)
class ReelAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "category", "status", "rating", "created_at")
    list_filter = ("status", "category")
    search_fields = ("title", "url", "tags")