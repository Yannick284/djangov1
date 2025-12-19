from __future__ import annotations

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView

from django.forms import modelform_factory

from .models import Reel, Category


def is_admin_user(user) -> bool:
    # "yannick" peut tout voir (comme demandé)
    return user.is_authenticated and user.username == "yannick"


class ReelAccessMixin(LoginRequiredMixin):
    """Filtre par user, sauf admin."""

    def get_queryset(self):
        qs = Reel.objects.select_related("category", "user")
        if is_admin_user(self.request.user):
            return qs
        return qs.filter(user=self.request.user)


# Forms sans dépendre de reels/forms.py (ça évite ton ImportError CategoryForm)
ReelForm = modelform_factory(
    Reel,
    fields=[
        "title",
        "url",
        "category",
        "status",
        "rating",
        "comment",
        "tags",
        "thumbnail",
        "thumbnail_url",
    ],
)

CategoryForm = modelform_factory(
    Category,
    fields=["name", "color"],
)


class ReelListView(LoginRequiredMixin, ListView):
    model = Reel
    template_name = "reels/reel_list.html"
    context_object_name = "reels"
    paginate_by = 60

    def get_queryset(self):
        qs = Reel.objects.select_related("category", "user")

        if not is_admin_user(self.request.user):
            qs = qs.filter(user=self.request.user)

        category_id = self.request.GET.get("category") or ""
        status = self.request.GET.get("status") or ""
        order = self.request.GET.get("order") or "-updated_at"

        if category_id:
            qs = qs.filter(category_id=category_id)
        if status:
            qs = qs.filter(status=status)

        allowed_orders = {"-updated_at", "rating", "-rating", "title"}
        if order not in allowed_orders:
            order = "-updated_at"

        return qs.order_by(order)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["categories"] = Category.objects.order_by("name")
        ctx["status_choices"] = Reel.Status.choices  # <= FIX
        ctx["selected_category"] = self.request.GET.get("category", "")
        ctx["selected_status"] = self.request.GET.get("status", "")
        ctx["selected_order"] = self.request.GET.get("order", "-updated_at")
        ctx["is_admin"] = is_admin_user(self.request.user)
        return ctx


class ReelDetailView(ReelAccessMixin, DetailView):
    model = Reel
    template_name = "reels/reel_detail.html"
    context_object_name = "reel"


class ReelCreateView(LoginRequiredMixin, CreateView):
    model = Reel
    form_class = ReelForm
    template_name = "reels/reel_form.html"

    def form_valid(self, form):
        obj = form.save(commit=False)
        obj.user = self.request.user
        obj.save()
        form.save_m2m()
        return HttpResponseRedirect(reverse_lazy("reels:detail", kwargs={"pk": obj.pk}))


class ReelUpdateView(ReelAccessMixin, UpdateView):
    model = Reel
    form_class = ReelForm
    template_name = "reels/reel_form.html"

    def form_valid(self, form):
        obj = form.save()
        return HttpResponseRedirect(reverse_lazy("reels:detail", kwargs={"pk": obj.pk}))


class ReelDeleteView(ReelAccessMixin, DeleteView):
    model = Reel
    template_name = "reels/reel_confirm_delete.html"
    success_url = reverse_lazy("reels:list")


class ReelSetStatusView(ReelAccessMixin, View):
    """POST-only pour changer le statut depuis la liste."""

    def post(self, request, pk: int, status: str):
        reel = get_object_or_404(self.get_queryset(), pk=pk)

        valid_statuses = {choice[0] for choice in Reel.Status.choices}
        if status not in valid_statuses:
            raise Http404("Invalid status")

        reel.status = status
        reel.save(update_fields=["status"])

        return HttpResponseRedirect(request.META.get("HTTP_REFERER", reverse_lazy("reels:list")))


class CategoryCreateView(LoginRequiredMixin, CreateView):
    model = Category
    form_class = CategoryForm
    template_name = "reels/category_form.html"
    success_url = reverse_lazy("reels:list")