from __future__ import annotations

from datetime import date
from decimal import Decimal
import json

from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_protect
from django.views.generic import ListView, UpdateView
from django.views import View

from .models import Property, Loan, MarketPricePoint
from .forms import PropertyForm, LoanForm, RentPeriodForm

from .services.ledger import build_ledger, month_start
from .services.summary import property_summary
from .services.breakeven import breakeven_date
from .services.scenarios import sale_scenarios
from .services.time_scenarios import time_sale_scenarios
from .services.crd_series import crd_series_for_months


class PropertyListView(LoginRequiredMixin, ListView):
    model = Property
    template_name = "immo/property_list.html"
    context_object_name = "properties"

    def get_queryset(self):
        return Property.objects.filter(user=self.request.user).order_by("-purchase_date")


@login_required
def dashboard_view(request, property_id: int):
    prop = get_object_or_404(Property, id=property_id, user=request.user)

    # "end" = date d’arrêt de l’analyse (par défaut aujourd’hui)
    end_str = request.GET.get("end")
    end_date = date.fromisoformat(end_str) if end_str else date.today()

    # growth dans l'URL est en % (ex: "2.0"), mais les services attendent une fraction (0.02)
    growth_pct = Decimal(request.GET.get("growth", "0.0"))
    growth_frac = growth_pct / Decimal("100")

    summary = property_summary(prop, end_date)

    be = breakeven_date(
        prop,
        end_date,
        horizon_months=120,
        annual_growth_rate=growth_frac,
    )

    scen = sale_scenarios(prop, end_date)

    time_scen = time_sale_scenarios(
        prop,
        end_date,
        growth_pct=growth_frac,
        years_list=(1, 2, 3, 4, 5),
    )

    return render(
        request,
        "immo/dashboard.html",
        {
            "prop": prop,
            "end_date": end_date,
            "growth": growth_pct,  # affichage "x%/an"
            "summary": summary,
            "breakeven": be,
            "scenarios": scen,
            "time_scenarios": time_scen,
        },
    )


@login_required
def summary_view(request, property_id: int):
    prop = get_object_or_404(Property, id=property_id, user=request.user)
    end_str = request.GET.get("end")
    end_date = date.fromisoformat(end_str) if end_str else date.today()
    return JsonResponse(property_summary(prop, end_date))


@login_required
def ledger_view(request, property_id: int):
    prop = get_object_or_404(Property, id=property_id, user=request.user)

    end_str = request.GET.get("end")
    end_date = date.fromisoformat(end_str) if end_str else date.today()

    rows = build_ledger(prop, end_date)

    return JsonResponse(
        {
            "property": prop.name,
            "end_date": end_date.isoformat(),
            "rows": [
                {
                    "month": r.month.isoformat(),
                    "rent_hc": str(r.rent_hc),
                    "charges": str(r.charges),
                    "expenses": str(r.expenses),
                    "loan_payment": str(r.loan_payment),
                    "insurance": str(r.insurance),
                    "net_cashflow": str(r.net_cashflow),
                    "cum_cashflow": str(r.cum_cashflow),
                }
                for r in rows
            ],
        }
    )


@login_required
def breakeven_view(request, property_id: int):
    prop = get_object_or_404(Property, id=property_id, user=request.user)

    end_str = request.GET.get("end")
    end_date = date.fromisoformat(end_str) if end_str else date.today()

    # Dans ton JS, tu envoies growth tel quel (aujourd’hui tu l’utilises plutôt en fraction)
    growth = Decimal(request.GET.get("growth", "0.0"))
    horizon = int(request.GET.get("horizon", "120"))

    res = breakeven_date(prop, end_date, horizon_months=horizon, annual_growth_rate=growth)
    return JsonResponse({"property": prop.name, "as_of": end_date.isoformat(), "growth": str(growth), "result": res})


@login_required
def market_series_view(request, property_id: int):
    """
    API du graphe: renvoie les points existants (MarketPricePoint)
    + net vendeur /m² si prêt disponible.
    """
    prop = get_object_or_404(Property, id=property_id, user=request.user)

    points = list(prop.market_points.order_by("date"))
    months = [p.date for p in points]

    surface = Decimal(prop.surface_sqm) if prop.surface_sqm else None
    fee_rate = Decimal(prop.selling_fees_rate or 0)

    try:
        loan = prop.loan
    except Loan.DoesNotExist:
        loan = None

    crd_map = crd_series_for_months(loan, months) if loan and months else None

    series = []
    for p in points:
        price_m2 = Decimal(p.price_per_sqm)
        mv = (price_m2 * surface) if surface else None

        net_vendeur_m2 = None
        if surface and mv and crd_map:
            crd_val = crd_map.get(p.date.isoformat())
            if crd_val is not None:
                crd = Decimal(str(crd_val))
                selling_fees = mv * fee_rate / Decimal("100")
                net_vendeur = mv - selling_fees - crd
                net_vendeur_m2 = net_vendeur / surface

        series.append(
            {
                "date": p.date.isoformat(),
                "price_per_sqm": float(price_m2),
                "net_vendeur_per_sqm": float(net_vendeur_m2) if net_vendeur_m2 is not None else None,
            }
        )

    return JsonResponse(
        {
            "property": prop.name,
            "surface_sqm": str(prop.surface_sqm) if prop.surface_sqm else None,
            "selling_fees_rate": str(fee_rate),
            "series": series,
        }
    )


@login_required
@csrf_protect
@require_http_methods(["GET", "POST"])
def market_points_view(request, property_id: int):
    """
    POST: { date: "YYYY-MM-01", price_per_sqm: "9200" }
    GET: renvoie uniquement les points existants
    """
    prop = get_object_or_404(Property, id=property_id, user=request.user)

    if request.method == "POST":
        try:
            payload = json.loads(request.body.decode("utf-8"))
        except Exception:
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        d_raw = payload.get("date")
        p_raw = payload.get("price_per_sqm")

        if not d_raw or p_raw in (None, ""):
            return JsonResponse({"error": "date/price_per_sqm required"}, status=400)

        try:
            d = date.fromisoformat(d_raw)
        except ValueError:
            return JsonResponse({"error": "Invalid date format"}, status=400)

        d = month_start(d)

        try:
            price = Decimal(str(p_raw))
        except Exception:
            return JsonResponse({"error": "Invalid price_per_sqm"}, status=400)

        obj, _ = MarketPricePoint.objects.update_or_create(
            property=prop,
            date=d,
            defaults={"price_per_sqm": price},
        )
        return JsonResponse({"ok": True, "date": obj.date.isoformat(), "price_per_sqm": str(obj.price_per_sqm)})

    pts = prop.market_points.order_by("date")
    return JsonResponse({"property": prop.name, "points": [{"date": p.date.isoformat(), "price_per_sqm": str(p.price_per_sqm)} for p in pts]})


class PropertyCreateView(LoginRequiredMixin, View):
    template_name = "immo/property_form.html"

    def get(self, request):
        return render(
            request,
            self.template_name,
            {
                "property_form": PropertyForm(),
                # ✅ prefixes => plus de collision start_date/end_date
                "loan_form": LoanForm(prefix="loan"),
                "rent_form": RentPeriodForm(prefix="rent"),
            },
        )

    @transaction.atomic
    def post(self, request):
        property_form = PropertyForm(request.POST)

        # ✅ mêmes prefixes côté POST
        loan_form = LoanForm(request.POST, prefix="loan")
        rent_form = RentPeriodForm(request.POST, prefix="rent")

        # property requis, loan/rent optionnels MAIS doivent être valides si renseignés
        ok_property = property_form.is_valid()
        ok_loan = loan_form.is_valid()
        ok_rent = rent_form.is_valid()

        if not ok_property or not ok_loan or not ok_rent:
            return render(
                request,
                self.template_name,
                {
                    "property_form": property_form,
                    "loan_form": loan_form,
                    "rent_form": rent_form,
                },
            )

        # 1) création propriété
        prop = property_form.save(commit=False)
        prop.user = request.user
        prop.save()

        # 2) prêt optionnel
        if not loan_form.is_empty():
            loan = loan_form.save(commit=False)
            loan.property = prop
            loan.save()

        # 3) loyer/cash optionnel
        if not rent_form.is_empty():
            rp = rent_form.save(commit=False)
            rp.property = prop
            rp.save()

        return redirect(reverse("immo:immo-dashboard", kwargs={"property_id": prop.id}))


class PropertyUpdateView(LoginRequiredMixin, UpdateView):
    model = Property
    form_class = PropertyForm
    template_name = "immo/property_form.html"

    def get_object(self, queryset=None):
        return get_object_or_404(Property, id=self.kwargs["property_id"], user=self.request.user)

    def get_success_url(self):
        return reverse("immo:immo-dashboard", kwargs={"property_id": self.object.id})