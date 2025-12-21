from django import forms
from .models import Property

class PropertyForm(forms.ModelForm):
    class Meta:
        model = Property
        fields = [
            "name",
            "purchase_date",
            "purchase_price",
            "notary_fees",
            "agency_fees",
            "surface_sqm",
            "parking",
            "selling_fees_rate",
            "goodwill_eur_per_sqm",
            "market_value_est",  # optionnel (si tu veux pouvoir forcer une valeur)
        ]
        widgets = {
            "purchase_date": forms.DateInput(attrs={"type": "date"}),
            "purchase_price": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
            "notary_fees": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
            "agency_fees": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
            "surface_sqm": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
            "parking": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
            "selling_fees_rate": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
            "goodwill_eur_per_sqm": forms.NumberInput(attrs={"step": "0.01"}),
            "market_value_est": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
        }

    def clean_selling_fees_rate(self):
        v = self.cleaned_data.get("selling_fees_rate")
        if v is not None and v > 30:
            raise forms.ValidationError("Taux de frais de vente trop élevé.")
        return v