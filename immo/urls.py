# immo/urls.py
from django.urls import path
from . import views

app_name = "immo"

urlpatterns = [
    # LIST / CREATE
    path("properties/", views.PropertyListView.as_view(), name="property-list"),
    path("properties/new/", views.PropertyCreateView.as_view(), name="property-create"),

    # DASHBOARD + APIs
    path("properties/<int:property_id>/", views.dashboard_view, name="immo-dashboard"),
    path("properties/<int:property_id>/summary/", views.summary_view, name="immo-summary"),
    path("properties/<int:property_id>/ledger/", views.ledger_view, name="immo-ledger"),
    path("properties/<int:property_id>/market-series/", views.market_series_view, name="immo-market-series"),
    path("properties/<int:property_id>/breakeven/", views.breakeven_view, name="immo-breakeven"),
    path("properties/<int:property_id>/market-points/", views.market_points_view, name="immo-market-points"),

    # GÉRER (prêt, loyers, dépenses) + EXPORT
    path("properties/<int:property_id>/manage/", views.manage_view, name="property-manage"),
    path("properties/<int:property_id>/export.csv", views.export_csv_view, name="immo-export-csv"),

    # EDIT
    path("properties/<int:property_id>/edit/", views.PropertyUpdateView.as_view(), name="property-edit"),
]