from __future__ import annotations

from typing import Any, Optional

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.views import LoginView
from django.http import HttpRequest
from django.shortcuts import render
from django.urls import reverse, reverse_lazy
from django.views.generic import DetailView, ListView
from django.views.generic.edit import CreateView, DeleteView, UpdateView

from .forms import BoQItemForm, GKSheetForm, ProjectForm
from .models import BoQItem, GKSheet, Project
from .permissions import user_has_any_role, user_has_role


class RoleRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    roles: tuple[str, ...] = ()
    allow_admin: bool = True

    def test_func(self) -> bool:
        user = self.request.user
        if self.allow_admin and user_has_role(user, "admin"):
            return True
        if not self.roles:
            return True
        return user_has_any_role(user, self.roles)


class AppLoginView(LoginView):
    template_name = 'core/auth/login.html'
    redirect_authenticated_user = True

    def get_success_url(self) -> str:
        redirect_to = self.get_redirect_url()
        if redirect_to:
            return redirect_to
        return str(reverse_lazy('core:sheet-list'))

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        for field_name in ('username', 'password'):
            if field_name in form.fields:
                field = form.fields[field_name]
                existing = field.widget.attrs.get('class', '')
                field.widget.attrs['class'] = f"{existing} form-control".strip()
        form.fields['username'].widget.attrs.setdefault('autofocus', True)
        form.fields['username'].widget.attrs.setdefault('placeholder', 'Korisničko ime')
        form.fields['password'].widget.attrs.setdefault('placeholder', 'Lozinka')
        return form


class ProjectListView(RoleRequiredMixin, ListView):
    model = Project
    context_object_name = "projects"
    template_name = "core/project_list.html"
    roles = ("izvodjac", "nadzor", "investitor")

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["can_manage"] = user_has_role(self.request.user, "admin")
        return context


class ProjectCreateView(RoleRequiredMixin, CreateView):
    model = Project
    form_class = ProjectForm
    template_name = "core/project_form.html"
    roles = ("admin",)

    def get_success_url(self) -> str:
        return str(reverse_lazy("core:project-list"))

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["title"] = "Novi projekat"
        return context


class ProjectUpdateView(RoleRequiredMixin, UpdateView):
    model = Project
    form_class = ProjectForm
    template_name = "core/project_form.html"
    roles = ("admin",)
    context_object_name = "project"

    def get_success_url(self) -> str:
        return str(reverse_lazy("core:project-list"))

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["title"] = "Izmena projekta"
        return context


class ProjectDeleteView(RoleRequiredMixin, DeleteView):
    model = Project
    template_name = "core/project_confirm_delete.html"
    roles = ("admin",)
    context_object_name = "project"

    def get_success_url(self) -> str:
        return str(reverse_lazy("core:project-list"))

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context.setdefault("title", "Brisanje projekta")
        return context


class BoQItemListView(RoleRequiredMixin, ListView):
    model = BoQItem
    context_object_name = "boq_items"
    template_name = "core/boqitem_list.html"
    roles = ("izvodjac", "nadzor", "investitor")

    def get_queryset(self):
        queryset = BoQItem.objects.select_related("project").order_by("project__name", "code")
        project_id = self.request.GET.get("project")
        if project_id:
            queryset = queryset.filter(project_id=project_id)
        return queryset

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["projects"] = Project.objects.order_by("name")
        context["selected_project"] = self.request.GET.get("project", "")
        context["can_manage"] = user_has_any_role(self.request.user, ("admin", "izvodjac"))
        return context


class BoQItemCreateView(RoleRequiredMixin, CreateView):
    model = BoQItem
    form_class = BoQItemForm
    template_name = "core/boqitem_form.html"
    roles = ("admin", "izvodjac")

    def get_initial(self):
        initial = super().get_initial()
        project_id = self.request.GET.get("project")
        if project_id:
            initial["project"] = project_id
        return initial

    def get_success_url(self) -> str:
        return str(reverse_lazy("core:boqitem-list"))

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["title"] = "Nova BoQ stavka"
        return context


class BoQItemUpdateView(RoleRequiredMixin, UpdateView):
    model = BoQItem
    form_class = BoQItemForm
    template_name = "core/boqitem_form.html"
    roles = ("admin", "izvodjac")
    context_object_name = "boq_item"

    def get_success_url(self) -> str:
        return str(reverse_lazy("core:boqitem-list"))

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["title"] = "Izmena BoQ stavke"
        return context


class BoQItemDeleteView(RoleRequiredMixin, DeleteView):
    model = BoQItem
    template_name = "core/boqitem_confirm_delete.html"
    roles = ("admin", "izvodjac")
    context_object_name = "boq_item"

    def get_success_url(self) -> str:
        return str(reverse_lazy("core:boqitem-list"))

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context.setdefault("title", "Brisanje BoQ stavke")
        return context


class GKSheetListView(RoleRequiredMixin, ListView):
    model = GKSheet
    context_object_name = "sheets"
    template_name = "core/sheet_list.html"
    roles = ("izvodjac", "nadzor", "investitor")

    def get_queryset(self):
        queryset = GKSheet.objects.select_related("project", "boq_item").order_by("boq_item__code", "seq_no")
        project_id = self.request.GET.get("project")
        boq_id = self.request.GET.get("boq")
        if project_id:
            queryset = queryset.filter(project_id=project_id)
        if boq_id:
            queryset = queryset.filter(boq_item_id=boq_id)
        return queryset

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["projects"] = Project.objects.order_by("name")
        context["boq_items"] = BoQItem.objects.select_related("project").order_by("project__name", "code")
        context["selected_project"] = self.request.GET.get("project", "")
        context["selected_boq"] = self.request.GET.get("boq", "")
        context["can_manage"] = user_has_any_role(self.request.user, ("admin", "izvodjac"))
        return context


class GKSheetDetailView(RoleRequiredMixin, DetailView):
    model = GKSheet
    context_object_name = "sheet"
    template_name = "core/sheet_detail.html"
    roles = ("izvodjac", "nadzor", "investitor")

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["can_manage"] = user_has_any_role(self.request.user, ("admin", "izvodjac"))
        return context


class GKSheetCreateView(RoleRequiredMixin, CreateView):
    model = GKSheet
    form_class = GKSheetForm
    template_name = "core/sheet_form.html"
    roles = ("admin", "izvodjac")

    def get_initial(self):
        initial = super().get_initial()
        if project_id := self.request.GET.get("project"):
            initial["project"] = project_id
        if boq_id := self.request.GET.get("boq"):
            initial["boq_item"] = boq_id
        initial.setdefault("status", "draft")
        return initial

    def get_form_kwargs(self) -> dict[str, Any]:
        kwargs = super().get_form_kwargs()
        project = self._get_project_from_request()
        if project:
            kwargs["project"] = project
        return kwargs

    def form_valid(self, form: GKSheetForm):
        form.instance.created_by = self.request.user
        return super().form_valid(form)

    def get_success_url(self) -> str:
        return reverse("core:sheet-detail", args=[self.object.pk])

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["title"] = "Novi list GK"
        return context

    def _get_project_from_request(self) -> Optional[Project]:
        project_id = self.request.POST.get("project") or self.request.GET.get("project")
        if project_id:
            return Project.objects.filter(pk=project_id).first()
        return None


class GKSheetUpdateView(RoleRequiredMixin, UpdateView):
    model = GKSheet
    form_class = GKSheetForm
    template_name = "core/sheet_form.html"
    context_object_name = "sheet"
    roles = ("admin", "izvodjac")

    def get_form_kwargs(self) -> dict[str, Any]:
        kwargs = super().get_form_kwargs()
        kwargs["project"] = self.get_object().project
        return kwargs

    def get_success_url(self) -> str:
        return reverse("core:sheet-detail", args=[self.object.pk])

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["title"] = "Izmena lista GK"
        return context


class GKSheetDeleteView(RoleRequiredMixin, DeleteView):
    model = GKSheet
    template_name = "core/sheet_confirm_delete.html"
    context_object_name = "sheet"
    roles = ("admin", "izvodjac")

    def get_success_url(self) -> str:
        return str(reverse_lazy("core:sheet-list"))


def index(request: HttpRequest):
    stats = {
        "projects": Project.objects.count(),
        "boq_items": BoQItem.objects.count(),
        "sheets": GKSheet.objects.count(),
        "active_projects": Project.objects.filter(is_active=True).count(),
    }
    return render(request, "core/index.html", {"stats": stats})
