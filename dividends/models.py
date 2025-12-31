from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.db import models

User = settings.AUTH_USER_MODEL


class Asset(models.Model):
    ASSET_TYPES = [
        ("stock", "Action"),
        ("etf", "ETF"),
        ("reit", "REIT"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="div_assets")

    # Identité (chez toi)
    ticker = models.CharField(max_length=20)  # ex: SAN.PA (identifiant interne)
    name = models.CharField(max_length=120, blank=True, default="")

    # Références marché
    isin = models.CharField(max_length=12, blank=True, default="")  # ex: FR0000120578
    exchange = models.CharField(max_length=40, blank=True, default="")  # ex: EPA
    currency = models.CharField(max_length=3, default="EUR")  # EUR/USD/...
    asset_type = models.CharField(max_length=10, choices=ASSET_TYPES, default="stock")
    sector = models.CharField(max_length=60, blank=True, default="")

    # Symbole de prix (provider, ex Yahoo). Si vide => fallback ticker.
    price_symbol = models.CharField(max_length=30, blank=True, default="")  # ex: SAN.PA

    # Optionnel: symbole d'affichage court (ex: "SAN")
    symbol = models.CharField(max_length=32, blank=True, default="")

    # Dernier prix stocké
    last_price = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    last_price_asof = models.DateTimeField(null=True, blank=True)
    last_price_source = models.CharField(max_length=32, blank=True, default="")

    # Flags
    is_active = models.BooleanField(default=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "ticker")
        ordering = ["ticker"]
        indexes = [
            models.Index(fields=["user", "ticker"]),
            models.Index(fields=["user", "is_active"]),
            models.Index(fields=["user", "price_symbol"]),
        ]

    def __str__(self):
        return self.ticker

    @property
    def last_price_float(self) -> float:
        return float(self.last_price or 0)

    def save(self, *args, **kwargs):
        # ✅ garanti même si création via script (clean() n'est pas toujours appelé)
        if not self.price_symbol:
            self.price_symbol = self.ticker
        super().save(*args, **kwargs)


class Transaction(models.Model):
    BUY = "BUY"
    SELL = "SELL"
    TYPES = [(BUY, "Achat"), (SELL, "Vente")]

    # ✅ on garde user ici pour cohérence/filtrage (source de vérité = transactions)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="div_transactions",    null=True,
    blank=True,)
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name="transactions")

    date = models.DateField()
    type = models.CharField(max_length=4, choices=TYPES)

    quantity = models.DecimalField(max_digits=14, decimal_places=6)  # support fractions
    price = models.DecimalField(max_digits=14, decimal_places=6)  # prix unitaire
    fees = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))

    note = models.CharField(max_length=200, blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["date", "id"]
        indexes = [
            models.Index(fields=["user", "date"]),
            models.Index(fields=["asset", "date"]),
            models.Index(fields=["asset", "type", "date"]),
        ]
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name="tx_quantity_gt_0"),
            models.CheckConstraint(condition=models.Q(price__gt=0), name="tx_price_gt_0"),
            models.CheckConstraint(condition=models.Q(fees__gte=0), name="tx_fees_gte_0"),
        ]

    def save(self, *args, **kwargs):
        # ✅ verrouille l'ownership: la transaction appartient au même user que l'asset
        if self.asset_id and self.user_id != self.asset.user_id:
            self.user_id = self.asset.user_id
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.asset.ticker} {self.type} {self.quantity} @ {self.price} ({self.date})"


class DividendEvent(models.Model):
    STATUS = [
        ("estimated", "Estimé"),
        ("declared", "Déclaré"),
        ("received", "Reçu"),
    ]

    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name="dividend_events")

    # ⚠️ yfinance renvoie souvent un historique de "paiements" (payment date),
    # donc stocke aussi pay_date pour être clean.
    ex_date = models.DateField()
    pay_date = models.DateField(null=True, blank=True)

    amount_per_share = models.DecimalField(max_digits=12, decimal_places=6)
    currency = models.CharField(max_length=3, default="EUR")
    status = models.CharField(max_length=10, choices=STATUS, default="declared")
    source = models.CharField(max_length=20, default="yfinance")

    is_net_amount = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("asset", "ex_date", "amount_per_share")
        ordering = ["pay_date", "ex_date", "id"]
        indexes = [
            models.Index(fields=["asset", "ex_date"]),
            models.Index(fields=["pay_date"]),
            models.Index(fields=["ex_date"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        pd = self.pay_date.isoformat() if self.pay_date else "no-pay-date"
        return f"{self.asset.ticker} {pd} ({self.amount_per_share} {self.currency})"


class DividendPayment(models.Model):
    asset = models.ForeignKey(
        Asset, on_delete=models.SET_NULL, null=True, blank=True, related_name="dividend_payments"
    )

    date = models.DateField()

    gross_amount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    withholding_tax = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    other_fees = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    currency = models.CharField(max_length=3, default="EUR")

    event = models.ForeignKey(
        DividendEvent, on_delete=models.SET_NULL, null=True, blank=True, related_name="payments"
    )

    note = models.CharField(max_length=200, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-id"]
        indexes = [
            models.Index(fields=["date"]),
            models.Index(fields=["asset", "date"]),
        ]

    @property
    def net_amount(self) -> Decimal:
        return (self.gross_amount or Decimal("0.00")) - (self.withholding_tax or Decimal("0.00")) - (
            self.other_fees or Decimal("0.00")
        )

    def __str__(self):
        t = self.asset.ticker if self.asset else "UNKNOWN"
        return f"{t} paid {self.net_amount} {self.currency} ({self.date})"