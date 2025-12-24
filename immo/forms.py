from __future__ import annotations

from django import forms
from .models import Property, Loan, RentPeriod


class PropertyForm(forms.ModelForm):
    """
    Form principal = infos du bien.
    """
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
            "market_value_est",  # override global € (optionnel)
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
        if v is not None and v < 0:
            raise forms.ValidationError("Le taux ne peut pas être négatif.")
        if v is not None and v > 30:
            raise forms.ValidationError("Taux trop élevé (>30%).")
        return v


class LoanForm(forms.ModelForm):
    """
    Prêt optionnel.
    IMPORTANT: ce form doit être utilisé avec prefix="loan"
    pour éviter collision avec RentPeriodForm.start_date/end_date.
    """
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
            "years": forms.NumberInput(attrs={"step": "1", "min": "1"}),
            "insurance_monthly": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
            "start_date": forms.DateInput(attrs={"type": "date"}),
        }

    def is_empty(self) -> bool:
        cd = getattr(self, "cleaned_data", None) or {}
        keys = ["borrowed_capital", "annual_rate", "years", "start_date"]
        return all(not cd.get(k) for k in keys)


class RentPeriodForm(forms.ModelForm):
    """
    Loyer / Cash optionnel.
    IMPORTANT: ce form doit être utilisé avec prefix="rent"
    pour éviter collision avec LoanForm.start_date.
    """
    class Meta:
        model = RentPeriod
        fields = [
            "start_date",
            "end_date",
            "rent_hc",
            "charges",
        ]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
            "rent_hc": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
            "charges": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
        }

    def is_empty(self) -> bool:
        cd = getattr(self, "cleaned_data", None) or {}
        # "utilisable" = start_date + rent_hc (charges peut être 0)
        return not cd.get("start_date") and not cd.get("rent_hc")

    def clean(self):
        cleaned = super().clean()
        sd = cleaned.get("start_date")
        ed = cleaned.get("end_date")
        if sd and ed and ed < sd:
            raise forms.ValidationError("La date de fin ne peut pas être avant la date de début.")
        return cleaned