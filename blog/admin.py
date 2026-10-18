from django.contrib import admin

from .models import Post, Author, Tag, Comment, Project

# Register your models here


class PostAdmin(admin.ModelAdmin):
    list_filter = ("author", "tags", "date","is_public", "is_superuser_only")
    list_display = ("title", "date", "author","is_public", "is_superuser_only")
    prepopulated_fields = {"slug": ("title",)}


@admin.action(description="Approuver les commentaires sélectionnés")
def approve_comments(modeladmin, request, queryset):
    queryset.update(is_approved=True)


class CommentAdmin(admin.ModelAdmin):
    list_display = ("user_name", "post", "is_approved", "created_at")
    list_filter = ("is_approved",)
    actions = [approve_comments]


class ProjectAdmin(admin.ModelAdmin):
    list_display = ("title", "status", "position", "is_public")
    list_editable = ("position", "is_public")
    prepopulated_fields = {"slug": ("title",)}


admin.site.register(Post, PostAdmin)
admin.site.register(Author)
admin.site.register(Tag)
admin.site.register(Comment, CommentAdmin)
admin.site.register(Project, ProjectAdmin)


