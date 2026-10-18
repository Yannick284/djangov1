from django import forms
from django.contrib.auth import get_user_model

from dividends.models import DividendAlertSetting


class ProfileForm(forms.ModelForm):
    dividend_alerts = forms.BooleanField(
        required=False,
        label="M'envoyer un e-mail la veille d'un versement de dividende",
        help_text="Utilise l'adresse e-mail de ton compte.",
    )

    class Meta:
        model = get_user_model()
        fields = ["first_name", "last_name"]
        labels = {"first_name": "Prénom", "last_name": "Nom"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        setting = DividendAlertSetting.objects.filter(user=self.instance).first()
        self.fields["dividend_alerts"].initial = bool(setting and setting.enabled)

    def save(self, commit=True):
        user = super().save(commit=commit)
        if commit:
            DividendAlertSetting.objects.update_or_create(
                user=user, defaults={"enabled": self.cleaned_data["dividend_alerts"]}
            )
        return user
