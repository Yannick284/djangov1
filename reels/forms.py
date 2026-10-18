from django import forms

from .models import Reel, Category
from .utils import normalize_url


class ReelForm(forms.ModelForm):
    """Formulaire d'un Reel. Les catégories proposées sont celles du propriétaire du Reel."""

    class Meta:
        model = Reel
        fields = ["title", "url", "category", "status", "rating", "comment", "tags", "thumbnail", "thumbnail_url"]
        labels = {
            "title": "Titre",
            "url": "Lien",
            "category": "Catégorie",
            "status": "Statut",
            "rating": "Note (1 à 10)",
            "comment": "Commentaire",
            "tags": "Mots-clés",
            "thumbnail": "Image",
            "thumbnail_url": "Lien de l'image",
        }
        widgets = {"comment": forms.Textarea(attrs={"rows": 5})}

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

        # Le propriétaire : l'auteur du Reel à l'édition (même si c'est un admin qui édite), sinon l'utilisateur courant.
        self.owner = self.instance.user if self.instance.pk else self.user

        self.fields["category"].required = False
        self.fields["thumbnail_url"].required = False
        self.fields["category"].empty_label = "Sans catégorie"
        self.fields["category"].queryset = (
            Category.objects.filter(user=self.owner).order_by("name")
            if self.owner is not None
            else Category.objects.none()
        )

    def clean_url(self):
        url = normalize_url(self.cleaned_data["url"])
        if self.owner and Reel.objects.filter(user=self.owner, url=url).exclude(pk=self.instance.pk or 0).exists():
            raise forms.ValidationError("Ce Reel est déjà enregistré.")
        return url


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ["name"]
        labels = {"name": "Nom de la catégorie"}

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

    def clean_name(self):
        name = " ".join(self.cleaned_data["name"].split())
        qs = Category.objects.filter(user=self.user, name__iexact=name).exclude(pk=self.instance.pk or 0)
        if self.user and qs.exists():
            raise forms.ValidationError("Cette catégorie existe déjà.")
        return name
