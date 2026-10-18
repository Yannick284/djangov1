from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Q
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import CreateView, DeleteView, DetailView, ListView, TemplateView, UpdateView

from .forms import CategoryForm, ReelForm
from .models import Category, Reel
from .utils import fetch_page_meta


def is_admin_user(user) -> bool:
    return user.is_authenticated and user.is_superuser


class ReelAccessMixin(LoginRequiredMixin):
    """Chaque personne ne voit que ses reels (le superuser voit tout)."""

    def get_queryset(self):
        qs = Reel.objects.select_related("category", "user")
        if is_admin_user(self.request.user):
            return qs
        return qs.filter(user=self.request.user)


class ReelFormMixin:
    form_class = ReelForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs


def _fill_from_page(reel: Reel) -> None:
    """Complète titre et image depuis le lien, sans jamais bloquer l'enregistrement."""
    if reel.title and (reel.thumbnail or reel.thumbnail_url):
        return
    meta = fetch_page_meta(reel.url)
    if not reel.title and meta.get("title"):
        reel.title = meta["title"]
    if not (reel.thumbnail or reel.thumbnail_url) and meta.get("image"):
        reel.thumbnail_url = meta["image"]


class ReelListView(LoginRequiredMixin, ListView):
    model = Reel
    template_name = "reels/reel_list.html"
    context_object_name = "reels"
    paginate_by = 24

    def get_queryset(self):
        qs = Reel.objects.select_related("category", "user")
        if not is_admin_user(self.request.user):
            qs = qs.filter(user=self.request.user)

        q = (self.request.GET.get("q") or "").strip()
        category_id = self.request.GET.get("category") or ""
        status = self.request.GET.get("status") or ""
        order = self.request.GET.get("order") or "-updated_at"

        if q:
            qs = qs.filter(
                Q(title__icontains=q)
                | Q(comment__icontains=q)
                | Q(tags__icontains=q)
                | Q(url__icontains=q)
                | Q(category__name__icontains=q)
            )
        if category_id.isdigit():
            qs = qs.filter(category_id=int(category_id))
        if status in {c[0] for c in Reel.Status.choices}:
            qs = qs.filter(status=status)

        allowed_orders = {"-updated_at", "rating", "-rating", "title"}
        if order not in allowed_orders:
            order = "-updated_at"
        return qs.order_by(order, "-id")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        cats = Category.objects.all() if is_admin_user(user) else Category.objects.filter(user=user)
        ctx["categories"] = cats.order_by("name")
        ctx["status_choices"] = Reel.Status.choices
        ctx["q"] = (self.request.GET.get("q") or "").strip()
        ctx["selected_category"] = self.request.GET.get("category", "")
        ctx["selected_status"] = self.request.GET.get("status", "")
        ctx["selected_order"] = self.request.GET.get("order", "-updated_at")
        ctx["is_admin"] = is_admin_user(user)
        ctx["total"] = ctx["paginator"].count if ctx.get("paginator") else len(ctx["reels"])
        # Conserve les filtres dans les liens de pagination
        params = self.request.GET.copy()
        params.pop("page", None)
        ctx["qs_without_page"] = params.urlencode()
        return ctx


class ReelDetailView(ReelAccessMixin, DetailView):
    model = Reel
    template_name = "reels/reel_detail.html"
    context_object_name = "reel"


class ReelCreateView(LoginRequiredMixin, ReelFormMixin, CreateView):
    model = Reel
    template_name = "reels/reel_form.html"

    def form_valid(self, form):
        obj = form.save(commit=False)
        obj.user = self.request.user
        _fill_from_page(obj)
        obj.save()
        messages.success(self.request, "Reel enregistré.")
        return HttpResponseRedirect(reverse("reels:detail", kwargs={"pk": obj.pk}))

    def get_initial(self):
        initial = super().get_initial()
        category_id = self.request.GET.get("category")
        if category_id and category_id.isdigit():
            initial["category"] = int(category_id)
        return initial


class ReelUpdateView(ReelAccessMixin, ReelFormMixin, UpdateView):
    model = Reel
    template_name = "reels/reel_form.html"

    def form_valid(self, form):
        obj = form.save()
        messages.success(self.request, "Modifications enregistrées.")
        return HttpResponseRedirect(reverse("reels:detail", kwargs={"pk": obj.pk}))


class ReelDeleteView(ReelAccessMixin, DeleteView):
    model = Reel
    template_name = "reels/reel_confirm_delete.html"
    success_url = reverse_lazy("reels:list")


class ReelSetStatusView(ReelAccessMixin, View):
    """POST uniquement : change le statut depuis la liste."""

    http_method_names = ["post"]

    def post(self, request, pk: int, status: str):
        reel = get_object_or_404(self.get_queryset(), pk=pk)
        if status not in {c[0] for c in Reel.Status.choices}:
            raise Http404("Statut inconnu")
        reel.status = status
        reel.save(update_fields=["status", "updated_at"])
        nxt = request.POST.get("next") or ""
        if nxt.startswith("/reels/"):
            return redirect(nxt)
        return redirect("reels:list")


# --------------------------- catégories ------------------------------------

class CategoryCreateView(LoginRequiredMixin, CreateView):
    """Depuis le formulaire de reel : crée la catégorie puis revient au formulaire avec elle présélectionnée."""

    model = Category
    form_class = CategoryForm
    template_name = "reels/category_form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.instance.user = self.request.user
        category = form.save()
        return HttpResponseRedirect(f"{reverse('reels:create')}?category={category.pk}")


class CategoryListView(LoginRequiredMixin, TemplateView):
    """Gérer ses catégories : créer, renommer, supprimer."""

    template_name = "reels/category_list.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["categories"] = (
            Category.objects.filter(user=self.request.user).annotate(n=Count("reels")).order_by("name")
        )
        ctx["new_form"] = kwargs.get("new_form") or CategoryForm(user=self.request.user)
        return ctx

    def post(self, request, *args, **kwargs):
        form = CategoryForm(request.POST, user=request.user)
        if form.is_valid():
            form.instance.user = request.user
            form.save()
            messages.success(request, "Catégorie créée.")
            return redirect("reels:categories")
        return self.render_to_response(self.get_context_data(new_form=form))


class CategoryOwnedMixin(LoginRequiredMixin):
    def get_category(self, pk):
        return get_object_or_404(Category, pk=pk, user=self.request.user)


class CategoryRenameView(CategoryOwnedMixin, View):
    http_method_names = ["post"]

    def post(self, request, pk):
        cat = self.get_category(pk)
        form = CategoryForm(request.POST, instance=cat, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Catégorie renommée.")
        else:
            messages.error(request, " ".join(e for errs in form.errors.values() for e in errs))
        return redirect("reels:categories")


class CategoryDeleteView(CategoryOwnedMixin, View):
    http_method_names = ["post"]

    def post(self, request, pk):
        cat = self.get_category(pk)
        n = cat.reels.count()
        cat.delete()  # les reels restent, sans catégorie (on_delete=SET_NULL)
        messages.success(request, f"Catégorie supprimée ({n} reel{'s' if n > 1 else ''} conservé{'s' if n > 1 else ''}).")
        return redirect("reels:categories")
