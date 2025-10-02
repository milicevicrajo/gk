﻿from __future__ import annotations

from typing import Any, Optional
from decimal import Decimal

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.db.models import Prefetch
from django.contrib.auth.views import LoginView
from django.http import HttpRequest
from django.shortcuts import render
from django.urls import reverse, reverse_lazy
from django.views.generic import DetailView, ListView
from django.views.generic.edit import CreateView, DeleteView, UpdateView

from .forms import BoQCategoryForm, BoQItemForm, GKSheetForm, ProjectForm
from .models import BoQCategory, BoQItem, GKSheet, Project
from .permissions import user_has_any_role, user_has_role
from tempfile import NamedTemporaryFile
from pathlib import Path

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View

from .forms import BoQExcelUploadForm
from .models import Project
from .utils.boq_import import import_boq_excel
from django.db.models import Sum
from .forms import GKSheetCreateForm

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
        form.fields['username'].widget.attrs.setdefault('placeholder', 'Korisnicko ime')
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


class ProjectDetailView(RoleRequiredMixin, DetailView):
    model = Project
    template_name = 'core/project_detail.html'
    context_object_name = 'project'
    roles = ('izvodjac', 'nadzor', 'investitor')

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        project: Project = context['project']
        categories = list(
            project.boq_categories.order_by('sequence', 'name').prefetch_related(
                Prefetch('items', queryset=BoQItem.objects.order_by('code'))
            )
        )
        context['categories'] = categories
        all_items = list(project.boq_items.select_related('category').order_by('category__sequence', 'code'))
        uncategorised_items = [item for item in all_items if item.category_id is None]
        context['all_items'] = all_items
        context['uncategorised_items'] = uncategorised_items
        context['can_manage'] = user_has_any_role(self.request.user, ('admin', 'izvodjac'))
        context['total_items'] = len(all_items)
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

class BoQItemDetailView(DetailView):
    model = BoQItem
    template_name = "core/boqitem_detail.html"
    context_object_name = "item"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        item: BoQItem = ctx["item"]

        sheets_qs = (
            GKSheet.objects.filter(boq_item=item)
            .select_related("created_by")
            .order_by("seq_no")
        )

        approved_sum = sheets_qs.filter(status="approved").aggregate(s=Sum("qty_this_period"))["s"] or Decimal("0")
        submitted_sum = sheets_qs.filter(status__in=["submitted", "approved"]).aggregate(s=Sum("qty_this_period"))["s"] or Decimal("0")
        last_cumulative = sheets_qs.order_by("-seq_no").values_list("qty_cumulative", flat=True).first() or Decimal("0")

        remaining_qty = None
        if item.contract_qty is not None:
            remaining_qty = (item.contract_qty or Decimal("0")) - (last_cumulative or Decimal("0"))

        # >>> ovde dodajemo can_manage
        can_manage = user_has_any_role(self.request.user, ("admin", "izvodjac"))

        ctx.update({
            "sheets": sheets_qs,
            "approved_sum": approved_sum,
            "submitted_sum": submitted_sum,
            "last_cumulative": last_cumulative,
            "remaining_qty": remaining_qty,
            "can_manage": can_manage,
        })
        return ctx
    
class BoQCategoryCreateView(RoleRequiredMixin, CreateView):
    model = BoQCategory
    form_class = BoQCategoryForm
    template_name = 'core/boqcategory_form.html'
    roles = ('admin', 'izvodjac')

    def get_initial(self):
        initial = super().get_initial()
        project_id = self.kwargs.get('project_pk') or self.request.GET.get('project')
        if project_id:
            initial['project'] = project_id
        return initial

    def get_form_kwargs(self) -> dict[str, Any]:
        kwargs = super().get_form_kwargs()
        project = self._get_project_from_request()
        if project:
            kwargs['project'] = project
        return kwargs

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, 'Kategorija je saÄuvana.')
        return response

    def get_success_url(self) -> str:
        return reverse('core:project-detail', args=[self.object.project_id])

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context['title'] = 'Nova BoQ kategorija'
        context['project'] = self._get_project_from_request()
        return context

    def _get_project_from_request(self) -> Optional[Project]:
        project_id = self.kwargs.get('project_pk') or self.request.POST.get('project') or self.request.GET.get('project')
        if project_id:
            return Project.objects.filter(pk=project_id).first()
        return None


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

    def get_form_kwargs(self) -> dict[str, Any]:
        kwargs = super().get_form_kwargs()
        project = self._get_project_from_request()
        if project:
            kwargs['project'] = project
        return kwargs

    def get_success_url(self) -> str:
        return str(reverse_lazy("core:boqitem-list"))

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["title"] = "Nova BoQ stavka"
        return context

    def _get_project_from_request(self) -> Optional[Project]:
        project_id = self.request.POST.get('project') or self.request.GET.get('project')
        if project_id:
            return Project.objects.filter(pk=project_id).first()
        return None


class BoQItemUpdateView(RoleRequiredMixin, UpdateView):
    model = BoQItem
    form_class = BoQItemForm
    template_name = "core/boqitem_form.html"
    roles = ("admin", "izvodjac")
    context_object_name = "boq_item"

    def get_form_kwargs(self) -> dict[str, Any]:
        kwargs = super().get_form_kwargs()
        kwargs['project'] = self.get_object().project
        return kwargs

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

class BoQImportView(LoginRequiredMixin, View):
    template_name = "app/boq_import.html"

    def get(self, request, project_id: int):
        project = get_object_or_404(Project, pk=project_id)
        form = BoQExcelUploadForm()
        return render(request, self.template_name, {"form": form, "project": project})

    def post(self, request, project_id: int):
        project = get_object_or_404(Project, pk=project_id)
        form = BoQExcelUploadForm(request.POST, request.FILES)
        if not form.is_valid():
            return render(request, self.template_name, {"form": form, "project": project})

        upload = form.cleaned_data["excel"]
        clear_existing = form.cleaned_data["clear_existing"]

        # Sačuvaj upload u privremeni fajl (jer import_boq_excel očekuje path)
        with NamedTemporaryFile(delete=False, suffix=Path(upload.name).suffix) as tmp:
            for chunk in upload.chunks():
                tmp.write(chunk)
            tmp_path = Path(tmp.name)

        try:
            stats = import_boq_excel(
                project=project,
                excel_path=tmp_path,
                clear_existing=clear_existing,
            )
            msg = (
                f"Import OK — kategorije: {stats['categories']}, "
                f"kreirano: {stats['created']}, ažurirano: {stats['updated']}, "
                f"preskočeno: {stats['skipped']}."
            )
            messages.success(request, msg)
            if stats.get("warnings"):
                for w in stats["warnings"]:
                    messages.warning(request, w)
        except Exception as e:
            messages.error(request, f"Greška pri importu: {e}")
        finally:
            # očisti privremeni fajl
            try:
                tmp_path.unlink(missing_ok=True)
            except Exception:
                pass

        # vrati na projekat ili na istu formu — po želji
        return redirect(reverse("core:project-detail", args=[project.id]))

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
        sheet: GKSheet = context["sheet"]
        context["can_manage"] = user_has_any_role(self.request.user, ("admin", "izvodjac"))
        remaining = None
        contract_qty = getattr(sheet.boq_item, 'contract_qty', None)
        if contract_qty is not None:
            remaining = (contract_qty or Decimal('0')) - (sheet.qty_cumulative or Decimal('0'))
        context["remaining_qty"] = remaining
        return context


class GKSheetCreateView(CreateView):
    model = GKSheet
    form_class = GKSheetCreateForm
    template_name = "core/sheet_create_form.html"


    def dispatch(self, request, *args, **kwargs):
        boq_id = request.GET.get("boq") or kwargs.get("boq_id")
        self.boq_item = get_object_or_404(BoQItem, pk=boq_id)
        self.project = self.boq_item.project
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        # prethodno odobren kumulativ za ovu BoQ poziciju
        prev_approved_sum = (
            GKSheet.objects.filter(boq_item=self.boq_item, status="approved")
            .aggregate(total=Sum("qty_this_period"))["total"] or Decimal("0.000")
        ).quantize(Decimal("0.001"))

        # sledeći redni broj lista (seq_no) = max+1
        last = GKSheet.objects.filter(boq_item=self.boq_item).order_by("-seq_no").first()
        next_seq = (last.seq_no + 1) if last else 1

        ctx.update({
            "project": self.project,
            "boq_item": self.boq_item,
            "next_seq_no": next_seq,
            "boq_code": self.boq_item.code,
            "boq_name": getattr(self.boq_item, "name", ""),         # prilagodi imenu polja
            "boq_unit": getattr(self.boq_item, "uom", ""),         # npr. "m", "kom"...
            "boq_price": getattr(self.boq_item, "unit_price", None),
            "contract_qty": getattr(self.boq_item, "contract_qty", None),
            "prev_approved_sum": prev_approved_sum,
            # informativno: period ostavljamo da se NE unosi (po zahtevu),
            # ali ga prikazujemo kao "—" jer je slobodan
            "period_from": None,
            "period_to": None,
        })
        return ctx

   
    def form_valid(self, form):
        # >>> KLJUČNO: commit=False pa ručno setujemo FK pre .save()
        obj = form.save(commit=False)
        obj.project = self.project
        obj.boq_item = self.boq_item
        obj.created_by = self.request.user
        # seq_no će tvoj model sam dodeliti, ali možeš i ovde ako želiš pre poruke
        obj.save()  # sada model.save() ima postavljen boq_item i neće pucati
        # po želji poruka i redirect
        return redirect(self.get_success_url())
    
    def get_success_url(self):
        # Po želji: na detalj projekta ili na listu listova za BoQ stavku
        return reverse("core:project-detail", kwargs={"pk": self.project.pk})

class GKSheetUpdateView(RoleRequiredMixin, UpdateView):
    model = GKSheet
    form_class = GKSheetForm
    template_name = "core/sheet_form.html"
    context_object_name = "sheet"
    roles = ("admin", "izvodjac")
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.pop('project', None)  # ako si ga ranije dodavao, skloni da ne smeta ovoj formi
        return kwargs

    def get_success_url(self) -> str:
        return reverse("core:sheet-detail", args=[self.object.pk])

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        sheet: GKSheet = context["sheet"]
        context["title"] = "Izmena lista GK"
        contract_qty = getattr(sheet.boq_item, 'contract_qty', None)
        remaining = None
        if contract_qty is not None:
            remaining = (contract_qty or Decimal('0')) - (sheet.qty_cumulative or Decimal('0'))
        context["remaining_qty"] = remaining
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



