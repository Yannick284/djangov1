from django import forms
from .models import Reel, Category
from .utils import normalize_url

class ReelForm(forms.ModelForm):
    class Meta:
        model = Reel
        fields = ["url", "category", "status", "rating", "comment", "tags", "thumbnail", "thumbnail_url"]
        widgets = {
            "comment": forms.Textarea(attrs={"rows": 5}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)  # ← LIGNE CLÉ
        super().__init__(*args, **kwargs)

        self.fields["category"].required = False
        self.fields["thumbnail_url"].required = False

        if self.user:
            self.fields["category"].queryset = Category.objects.filter(
                user=self.user
            ).order_by("name")

    def clean_url(self):
        url = normalize_url(self.cleaned_data["url"])

        if self.user and Reel.objects.filter(user=self.user, url=url).exclude(
            pk=self.instance.pk or 0
        ).exists():
            raise forms.ValidationError("Ce Reel est déjà enregistré.")

        return url
class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ["name", "color"]