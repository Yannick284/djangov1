from django.contrib import admin

from .models import Post, Author, Tag, Comment

# Register your models here


class PostAdmin(admin.ModelAdmin):
    list_filter = ("author", "tags", "date","is_public", "is_superuser_only")
    list_display = ("title", "date", "author","is_public", "is_superuser_only")
    prepopulated_fields = {"slug": ("title",)}


class CommentAdmin(admin.ModelAdmin):
    list_display = ("user_name", "post")


admin.site.register(Post, PostAdmin)
admin.site.register(Author)
admin.site.register(Tag)
admin.site.register(Comment, CommentAdmin)


