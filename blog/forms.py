from django import forms

from .models import Comment
        
from allauth.account.forms import SignupForm

from .models import Post
import uuid
from django.utils.text import slugify

class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        exclude = ["post"]
        labels = {
          "user_name": "Votre nom",
          "user_email": "Votre e-mail",
          "text": "Votre commentaire"
        }


class CustomSignupForm(SignupForm):
    first_name = forms.CharField(max_length=30, label="Prénom")
    last_name = forms.CharField(max_length=30, label="Nom")

    def save(self, request):
        user = super().save(request)

        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]

        # 🔥 IMPORTANT : générer un username UNIQUE
        if not user.username:
            base = slugify(user.first_name) or "user"
            user.username = f"{base}-{uuid.uuid4().hex[:8]}"

        user.save()
        return user
# blog/forms.py

from allauth.account.adapter import DefaultAccountAdapter




class PostForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = ["title", "excerpt", "image", "content", "is_public"]
        exclude = ("slug", "owner", "date")
        labels = {
            "title": "Titre",
            "excerpt": "Résumé",
            "image": "Image de couverture",
            "content": "Texte",
            "is_public": "Visible par tout le monde",
        }
        help_texts = {
            "excerpt": "Une ou deux phrases, affichées dans la liste des articles.",
            "is_public": "Décoché : réservé aux personnes connectées.",
        }