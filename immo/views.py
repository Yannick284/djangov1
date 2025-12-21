from datetime import date
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404

from immo.services.time_scenarios import time_sale_scenarios

from .models import Property
from .services.ledger import build_ledger

from .services.crd_series import crd_series_for_months
from decimal import Decimal



from .services.breakeven import breakeven_date

from .services.summary import property_summary
from django.shortcuts import render
from .models import Property, Loan

from .services.scenarios import sale_scenarios
from decimal import Decimal


@login_required
def ledger_view(request, property_id: int):
    prop = get_object_or_404(Property, id=property_id, user=request.user)

    end_str = request.GET.get("end")  # YYYY-MM-DD
    end_date = date.fromisoformat(end_str) if end_str else date.today()

    rows = build_ledger(prop, end_date)

    return JsonResponse({
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
    })
    


@login_required
def summary_view(request, property_id: int):
    prop = get_object_or_404(Property, id=property_id, user=request.user)

    end_str = request.GET.get("end")
    end_date = date.fromisoformat(end_str) if end_str else date.today()

    return JsonResponse(property_summary(prop, end_date))





@login_required
def breakeven_view(request, property_id: int):
    prop = get_object_or_404(Property, id=property_id, user=request.user)

    end_str = request.GET.get("end")
    end_date = date.fromisoformat(end_str) if end_str else date.today()
    growth = Decimal(request.GET.get("growth", "0.0"))
    horizon = int(request.GET.get("horizon", "120"))

    res = breakeven_date(prop, end_date, horizon_months=horizon, annual_growth_rate=growth)
    return JsonResponse({"property": prop.name, "as_of": end_date.isoformat(), "growth": str(growth), "result": res})





@login_required
def dashboard_view(request, property_id: int):
    prop = get_object_or_404(Property, id=property_id, user=request.user)

    end_str = request.GET.get("end")
    end_date = date.fromisoformat(end_str) if end_str else date.today()

    # growth dans l'URL = "2.0" => 2% affiché
    growth = Decimal(request.GET.get("growth", "0.0"))
    growth_frac = growth / Decimal("100")  # ✅ 2.0 -> 0.02

    summary = property_summary(prop, end_date)

    be = breakeven_date(
        prop,
        end_date,
        horizon_months=120,
        annual_growth_rate=growth_frac,  # ✅ cohérent avec time_sale_scenarios
    )

    scen = sale_scenarios(prop, end_date)

    time_scenarios = time_sale_scenarios(
        prop,
        end_date,
        growth_pct=growth_frac,  # ✅ 0.02 pour 2%/an
        years_list=(1, 2, 3, 4, 5),
    )

    return render(request, "immo/dashboard.html", {
        "prop": prop,
        "end_date": end_date,
        "growth": growth,                 # ✅ affichage "2%/an"
        "summary": summary,
        "breakeven": be,
        "scenarios": scen,
        "time_scenarios": time_scenarios, # ✅ sinon le tableau ne s’affiche jamais
    })
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from .models import Property

def market_series_view(request, property_id: int):
    prop = get_object_or_404(Property, id=property_id, user=request.user)

    points = list(prop.market_points.all())  # ordering en Meta
    months = [p.date for p in points]

    surface = Decimal(prop.surface_sqm) if prop.surface_sqm else None
    fee_rate = Decimal(prop.selling_fees_rate) if hasattr(prop, "selling_fees_rate") else Decimal("5.0")

    crd_map = None
    loan_start = None

    try:
        loan = prop.loan
    except Loan.DoesNotExist:
        loan = None

    if loan:
        loan_start = loan.start_date.isoformat()
        crd_map = crd_series_for_months(loan, months)

    series = []
    for p in points:
        price_m2 = Decimal(p.price_per_sqm)
        mv = (price_m2 * surface) if surface else None

        net_vendeur_m2 = None
        crd_val = crd_map.get(p.date.isoformat()) if crd_map else None
        if surface and mv and crd_val is not None:
     
            crd = Decimal(crd_val)
            selling_fees = mv * fee_rate / Decimal("100")
            net_vendeur = mv - selling_fees - crd
            net_vendeur_m2 = net_vendeur / surface

        series.append({
            "date": p.date.isoformat(),
            "price_per_sqm": float(price_m2),
            "net_vendeur_per_sqm": float(net_vendeur_m2) if net_vendeur_m2 is not None else None,
        })

    return JsonResponse({
        "property": prop.name,
        "surface_sqm": str(prop.surface_sqm) if prop.surface_sqm else None,
        "selling_fees_rate": str(fee_rate),
        "series": series
    })
    
    
from django.views.decorators.http import require_http_methods
from django.forms.models import model_to_dict
from django.utils.dateparse import parse_date

from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.utils.dateparse import parse_date
import json
from decimal import Decimal

from .models import Property, MarketPricePoint

import json
from datetime import date
from decimal import Decimal

from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods

from .models import Property, MarketPricePoint
from .services.months import iter_month_starts, month_start

@login_required
@require_http_methods(["GET", "POST"])
def market_points_view(request, property_id: int):
    prop = get_object_or_404(Property, id=property_id, user=request.user)

    if request.method == "POST":
        data = json.loads(request.body.decode("utf-8"))
        d = date.fromisoformat(data["date"])
        d = month_start(d)

        price = Decimal(str(data["price_per_sqm"]))
        obj, _ = MarketPricePoint.objects.update_or_create(
            property=prop,
            date=d,
            defaults={"price_per_sqm": price},
        )
        return JsonResponse({
            "ok": True,
            "date": obj.date.isoformat(),
            "price_per_sqm": str(obj.price_per_sqm),
        })

    # GET
    end_str = request.GET.get("end")
    end_date = date.fromisoformat(end_str) if end_str else date.today()

    start_date = prop.purchase_date
    months = list(iter_month_starts(start_date, end_date))

    existing = {
        p.date: p for p in prop.market_points.filter(date__in=months)
    }

    rows = []
    for m in months:
        p = existing.get(m)
        rows.append({
            "date": m.isoformat(),
            "price_per_sqm": str(p.price_per_sqm) if p else None,
        })

    return JsonResponse({"property": prop.name, "rows": rows})


from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse
from django.views.generic import CreateView, UpdateView
from django.shortcuts import get_object_or_404

from .models import Property
from .forms import PropertyForm

class PropertyCreateView(LoginRequiredMixin, CreateView):
    model = Property
    form_class = PropertyForm
    template_name = "immo/property_form.html"

    def form_valid(self, form):
        obj = form.save(commit=False)
        obj.user = self.request.user
        obj.save()
        self.object = obj
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("immo-dashboard", kwargs={"property_id": self.object.id})

class PropertyUpdateView(LoginRequiredMixin, UpdateView):
    model = Property
    form_class = PropertyForm
    template_name = "immo/property_form.html"

    def get_object(self, queryset=None):
        return get_object_or_404(Property, id=self.kwargs["property_id"], user=self.request.user)

    def get_success_url(self):
        return reverse("immo-dashboard", kwargs={"property_id": self.object.id})