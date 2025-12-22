from django import forms
from decimal import Decimal
from .models import Property, Loan


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
            "market_value_est",  # override manuel optionnel
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


class LoanForm(forms.ModelForm):
    class Meta:
        model = Loan
        fields = [
            "borrowed_capital",
            "annual_rate",
            "years",
            "insurance_monthly",
            "start_date",
        ]
        widgets = {
            "borrowed_capital": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
            "annual_rate": forms.NumberInput(attrs={"step": "0.001", "min": "0"}),
            "insurance_monthly": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
            "start_date": forms.DateInput(attrs={"type": "date"}),
        }

    def is_empty(self):
        """Permet de rendre le prêt optionnel"""
        for field in self.fields:
            if self.cleaned_data.get(field):
                return False
        return True