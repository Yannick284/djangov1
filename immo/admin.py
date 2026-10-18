from django.contrib import admin
from .models import Property, Loan, Expense, RentPeriod

@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "purchase_date", "purchase_price","name", "surface_sqm", "goodwill_eur_per_sqm")
    search_fields = ("name", "user__username", "user__email")

@admin.register(Loan)
class LoanAdmin(admin.ModelAdmin):
    list_display = ("property", "borrowed_capital", "annual_rate", "years", "start_date")

@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ("property", "date", "category", "amount")
    list_filter = ("category", "date")
    search_fields = ("property__name", "note")

@admin.register(RentPeriod)
class RentPeriodAdmin(admin.ModelAdmin):
    list_display = ("property", "start_date", "end_date", "rent_hc", "charges")
