from django.db import models
from django.core.validators import MinLengthValidator
from storages.backends.s3boto3 import S3Boto3Storage
from django.conf import settings
from django.utils.text import slugify
# Create your models here.


class Tag(models.Model):
    caption = models.CharField(max_length=20)

    def __str__(self):
        return self.caption


class Author(models.Model):
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email_address = models.EmailField()

    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    def __str__(self):
        return self.full_name()




class Post(models.Model):
    title = models.CharField(max_length=150)
    excerpt = models.CharField(max_length=200)
    
    s3_storage = S3Boto3Storage()
    image = models.ImageField(storage=s3_storage, upload_to="posts", null=True)
    # image = models.ImageField(upload_to="posts", null=True, blank=True)
    is_superuser_only = models.BooleanField(default=False)
    # Date de publication : fixée à la création (avant : mise à jour à chaque modification).
    date = models.DateField(auto_now_add=True)
    slug = models.SlugField(unique=True, db_index=True)
    content = models.TextField()
    author = models.ForeignKey(
        Author, on_delete=models.SET_NULL, null=True, related_name="posts"
    )
    tags = models.ManyToManyField(Tag)

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="posts",
        null=True,
        blank=True,
    )
    
    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title)
            slug = base_slug
            counter = 1
            while Post.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                counter += 1
                slug = f"{base_slug}-{counter}"
            self.slug = slug
        super().save(*args, **kwargs)
        
    is_public = models.BooleanField(default=True)
    def __str__(self):
        return self.title

    @property
    def reading_minutes(self) -> int:
        """Temps de lecture estimé (≈ 200 mots/min), au moins 1 minute."""
        return max(1, round(len((self.content or "").split()) / 200))

    
    
    


    



class Comment(models.Model):
    user_name = models.CharField(max_length=120)
    user_email = models.EmailField() 
    text = models.TextField(max_length=400)
    # Un nouveau commentaire attend la validation de l'administrateur avant d'être affiché.
    is_approved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    post = models.ForeignKey(
        Post, on_delete=models.CASCADE, related_name="comments")

    def __str__(self):
        return f"{self.user_name} — {self.text[:40]}"


class Project(models.Model):
    class Status(models.TextChoices):
        ONGOING = "ongoing", "En cours"
        DONE = "done", "Terminé"
        PAUSED = "paused", "En pause"

    title = models.CharField("Titre", max_length=120)
    slug = models.SlugField(unique=True)
    summary = models.CharField("Résumé", max_length=220, help_text="Une phrase, affichée dans la liste.")
    description = models.TextField("Description", blank=True, help_text="Markdown accepté.")
    image = models.ImageField("Image", upload_to="projects", blank=True)
    url = models.URLField("Lien du projet", blank=True)
    repo_url = models.URLField("Lien du code", blank=True)
    technologies = models.CharField("Technologies", max_length=200, blank=True, help_text="Séparées par des virgules.")
    status = models.CharField("Statut", max_length=10, choices=Status.choices, default=Status.ONGOING)
    position = models.PositiveSmallIntegerField("Ordre", default=0, help_text="Les plus petits en premier.")
    is_public = models.BooleanField("Visible par tout le monde", default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["position", "-created_at"]

    def __str__(self):
        return self.title

    @property
    def tech_list(self):
        return [t.strip() for t in self.technologies.split(",") if t.strip()]
