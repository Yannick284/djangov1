from django import forms

from .models import Comment
        
from allauth.account.forms import SignupForm

from .models import Post, Tag
import uuid
from django.utils.text import slugify

class CommentForm(forms.ModelForm):
    # Piège à robots : champ invisible pour les humains. S'il est rempli, le commentaire est ignoré.
    website = forms.CharField(required=False, label="Ne pas remplir", widget=forms.TextInput(attrs={"tabindex": "-1", "autocomplete": "off"}))

    class Meta:
        model = Comment
        fields = ["user_name", "user_email", "text"]
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
    new_tags = forms.CharField(
        required=False,
        label="Nouveaux mots-clés",
        help_text="Séparés par des virgules (20 caractères maximum chacun).",
    )

    field_order = ["title", "excerpt", "image", "content", "tags", "new_tags", "is_public"]

    class Meta:
        model = Post
        fields = ["title", "excerpt", "image", "content", "tags", "is_public"]
        widgets = {
            "content": forms.Textarea(attrs={"rows": 18, "data-markdown-source": "1"}),
            "tags": forms.CheckboxSelectMultiple,
        }
        labels = {
            "title": "Titre",
            "excerpt": "Résumé",
            "image": "Image de couverture",
            "content": "Texte (Markdown)",
            "tags": "Mots-clés",
            "is_public": "Visible par tout le monde",
        }
        help_texts = {
            "excerpt": "Une ou deux phrases, affichées dans la liste des articles.",
            "content": "Markdown : **gras**, *italique*, # titre, - liste, [lien](https://…).",
            "is_public": "Décoché : réservé aux personnes connectées.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["image"].required = False
        self.fields["tags"].required = False

    def clean_new_tags(self):
        names = []
        for raw in self.cleaned_data.get("new_tags", "").split(","):
            name = " ".join(raw.split())
            if not name:
                continue
            if len(name) > 20:
                raise forms.ValidationError(f"« {name[:20]}… » dépasse 20 caractères.")
            names.append(name)
        return names

    def save(self, commit=True):
        post = super().save(commit=commit)
        if commit:
            for name in self.cleaned_data.get("new_tags", []):
                tag = Tag.objects.filter(caption__iexact=name).first() or Tag.objects.create(caption=name)
                post.tags.add(tag)
        return post