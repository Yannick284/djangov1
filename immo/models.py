from django.db import models
from django.conf import settings
from decimal import Decimal

User = settings.AUTH_USER_MODEL


class Property(models.Model):
    # existant
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="properties")
    name = models.CharField(max_length=120)
    purchase_date = models.DateField()

    purchase_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    notary_fees = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    surface_sqm = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    parking = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    goodwill_eur_per_sqm = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Ajustement ajouté au prix marché €/m² pour estimer la valeur (travaux, qualité, vue, etc.)",
    )
    agency_fees = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # 🔽 AJOUT
    market_value_est = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    selling_fees_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=0.00  # %
    )

    def __str__(self):
        return self.name


class Loan(models.Model):
    property = models.OneToOneField(Property, on_delete=models.CASCADE, related_name="loan")

    borrowed_capital = models.DecimalField(max_digits=12, decimal_places=2)  # après apport
    annual_rate = models.DecimalField(max_digits=6, decimal_places=3)  # ex: 1.400
    years = models.PositiveIntegerField()
    insurance_monthly = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    start_date = models.DateField()

    def __str__(self):
        return f"Loan - {self.property.name}"


class Expense(models.Model):
    class Category(models.TextChoices):
        WORKS = "works", "Travaux"
        REPAIR = "repair", "Réparation"
        TAX = "tax", "Taxes"
        CHARGES = "charges", "Charges copro"
        INSURANCE = "insurance", "Assurance"
        OTHER = "other", "Autre"

    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name="expenses")
    date = models.DateField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)  # positif
    category = models.CharField(max_length=20, choices=Category.choices)
    note = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return f"{self.property.name} - {self.category} - {self.amount}€"


class RentPeriod(models.Model):
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name="rent_periods")
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)  # null = en cours
    rent_hc = models.DecimalField(max_digits=12, decimal_places=2)
    charges = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    def __str__(self):
        end = self.end_date.isoformat() if self.end_date else "ongoing"
        return f"{self.property.name} rent {self.start_date} → {end}"


from django.db import models

class MarketPricePoint(models.Model):
    property = models.ForeignKey("immo.Property", on_delete=models.CASCADE, related_name="market_points")
    date = models.DateField()
    price_per_sqm = models.DecimalField(max_digits=10, decimal_places=2)  # €/m²

    class Meta:
        unique_together = ("property", "date")
        ordering = ["date"]

    def __str__(self):
        return f"{self.property.name} {self.date} {self.price_per_sqm}€/m²"
    

