from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from .forms import CategoryForm, ReelForm
from .models import Category, Reel
from django import forms
from .models import Reel, Category


def can_see_all_reels(user) -> bool:
    """Override: 'yannick' (ou staff/superuser) peut voir tous les reels."""
    if not user or not user.is_authenticated:
        return False
    return (
        user.is_superuser
        or user.is_staff
        or (getattr(user, "username", "") or "").lower() == "yannick"
    )


def reels_queryset_for_user(request: HttpRequest):
    qs = Reel.objects.select_related("category", "user").order_by("-id")
    if can_see_all_reels(request.user):
        return qs
    return qs.filter(user=request.user)


class ReelListView(LoginRequiredMixin, ListView):
    model = Reel
    template_name = "reels/reel_list.html"
    context_object_name = "reels"
    paginate_by = 60

    def get_queryset(self):
        qs = reels_queryset_for_user(self.request)

        # Filtre catégorie: /reels/?category=3
        category_id = self.request.GET.get("category")
        if category_id:
            qs = qs.filter(category_id=category_id)

        # Filtre status: /reels/?status=to_test
        status_val = self.request.GET.get("status")
        if status_val:
            qs = qs.filter(status=status_val)

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["categories"] = Category.objects.order_by("name")
        ctx["selected_category"] = self.request.GET.get("category", "")
        ctx["statuses"] = Reel.Status.choices  # <-- FIX: pas Reel.STATUS_CHOICES
        ctx["selected_status"] = self.request.GET.get("status", "")
        ctx["can_see_all"] = can_see_all_reels(self.request.user)
        return ctx


class ReelDetailView(LoginRequiredMixin, DetailView):
    model = Reel
    template_name = "reels/reel_detail.html"
    context_object_name = "reel"

    def get_queryset(self):
        return reels_queryset_for_user(self.request)


class ReelCreateView(LoginRequiredMixin, CreateView):
    model = Reel
    form_class = ReelForm
    template_name = "reels/reel_form.html"
    success_url = reverse_lazy("reels:list")

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)


class ReelUpdateView(LoginRequiredMixin, UpdateView):
    model = Reel
    form_class = ReelForm
    template_name = "reels/reel_form.html"
    success_url = reverse_lazy("reels:list")

    def get_queryset(self):
        return reels_queryset_for_user(self.request)


class ReelDeleteView(LoginRequiredMixin, DeleteView):
    model = Reel
    template_name = "reels/reel_confirm_delete.html"
    success_url = reverse_lazy("reels:list")

    def get_queryset(self):
        return reels_queryset_for_user(self.request)


@login_required
@require_POST
def set_status(request: HttpRequest, pk: int, status: str) -> HttpResponse:
    valid_statuses = {c[0] for c in Reel.Status.choices}
    if status not in valid_statuses:
        raise Http404("Invalid status")

    reel = get_object_or_404(reels_queryset_for_user(request), pk=pk)
    reel.status = status
    reel.save(update_fields=["status"])
    return redirect("reels:list")



    
class CategoryCreateView(LoginRequiredMixin, CreateView):
    model = Category
    form_class = CategoryForm
    template_name = "reels/category_form.html"
    success_url = reverse_lazy("reels:list")

    def form_valid(self, form):
        form.instance.user = self.request.user   # ✅ clé du fix
        return super().form_valid(form)
