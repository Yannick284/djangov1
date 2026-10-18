from django.urls import path
from . import views

urlpatterns = [
    path("", views.dividends_dashboard, name="dividends-dashboard"),
    path("calendar/", views.dividends_calendar, name="dividends-calendar"),

    path("api/month/", views.api_month_details, name="dividends-api-month-details"),

    # dictionnaire (add/remove)
    path("assets/toggle/", views.toggle_asset_from_universe, name="dividends-toggle-asset"),

    # transactions
    path("tx/buy/", views.add_buy_from_universe, name="dividends-add-buy"),
    path("tx/sell/", views.add_sell_from_universe, name="dividends-add-sell"),

    # import CSV
    path("import/", views.import_transactions_view, name="dividends-import"),
    path("import/modele.csv", views.import_template_csv, name="dividends-import-template"),

    # legacy (si une URL existe encore ailleurs)
    path("portfolio/", views.portfolio, name="dividends-portfolio"),
]