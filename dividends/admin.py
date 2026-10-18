from django.contrib import admin
from .models import Asset, Transaction, DividendEvent, DividendPayment


@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):

    ordering = ("ticker",)
    list_display = ("ticker", "name", "currency", "asset_type", "price_symbol", "last_price", "is_active")
    list_filter = ("asset_type", "currency", "is_active")
    search_fields = ("ticker", "name", "price_symbol")


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ("asset", "type", "quantity", "price", "date")
    list_filter = ("type", "date")
    search_fields = ("asset__ticker",)
    ordering = ("-date",)


@admin.register(DividendEvent)
class DividendEventAdmin(admin.ModelAdmin):
    list_display = (
        "asset",
        "ex_date",
        "pay_date",
        "amount_per_share",
        "currency",
        "status",
    )
    list_filter = ("status", "currency", "pay_date")
    search_fields = ("asset__ticker",)
    ordering = ("-pay_date",)


@admin.register(DividendPayment)
class DividendPaymentAdmin(admin.ModelAdmin):
    list_display = (
        "asset",
        "date",
        "gross_amount",
        "withholding_tax",
        "net_amount",
        "currency",
    )
    list_filter = ("currency", "date")
    search_fields = ("asset__ticker",)
    ordering = ("-date",)

    readonly_fields = ("net_amount",)
    
