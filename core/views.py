from __future__ import annotations

import secrets
from datetime import timedelta
from typing import Any

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.mail import send_mail
from django.db import transaction
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.generic import DetailView, ListView
from django.views.generic.edit import CreateView, UpdateView

from .forms import GKEntryFormSet, GKSheetForm
from .models import GKSheet, Project, ReviewToken
from .permissions import get_role_emails, user_has_any_role, user_has_role


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


def can_edit_sheet(user, sheet: GKSheet) -> bool:
    return sheet.is_draft and (user_has_role(user, "admin") or user_has_role(user, "izvodjac"))


def can_review_sheet(user) -> bool:
    return user_has_role(user, "admin") or user_has_role(user, "nadzor")


def can_submit_sheet(user, sheet: GKSheet) -> bool:
    return can_edit_sheet(user, sheet) and sheet.has_entries()


class GKSheetListView(RoleRequiredMixin, ListView):
    model = GKSheet
    context_object_name = "sheets"
    template_name = "core/sheet_list.html"
    roles = ("izvodjac", "nadzor", "investitor")

    def get_queryset(self):
        queryset = (
            GKSheet.objects.select_related("project")
            .prefetch_related("entries__boq_item")
            .order_by("-date")
        )
        project_id = self.request.GET.get("project")
        if project_id:
            queryset = queryset.filter(project_id=project_id)
        return queryset

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        sheets = list(context.get("sheets", []))
        context["sheets"] = sheets
        context["projects"] = Project.objects.order_by("name")
        context["selected_project"] = self.request.GET.get("project", "")
        context["can_create"] = user_has_role(self.request.user, "izvodjac") or user_has_role(self.request.user, "admin")
        context["editable_ids"] = {sheet.pk for sheet in sheets if can_edit_sheet(self.request.user, sheet)}
        context["submittable_ids"] = {sheet.pk for sheet in sheets if can_submit_sheet(self.request.user, sheet)}
        return context


class SheetFormsetMixin:
    form_class = GKSheetForm
    formset_class = GKEntryFormSet

    def get_success_url(self) -> str:
        return self.object.get_absolute_url()

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        if can_review_sheet(self.request.user):
            form.fields["review_note"].widget.attrs.pop("readonly", None)
        else:
            form.fields["review_note"].disabled = True
        return form

    def get_formset(self, *, instance: GKSheet, data=None):
        return self.formset_class(data, instance=instance)

    def forms_invalid(self, form, formset):
        context = self.get_context_data(form=form, formset=formset)
        return self.render_to_response(context)

    def _formset_has_entries(self, formset) -> bool:
        return any(
            form.cleaned_data and not form.cleaned_data.get("DELETE", False)
            for form in formset.forms
        )


class GKSheetCreateView(RoleRequiredMixin, SheetFormsetMixin, CreateView):
    template_name = "core/sheet_form.html"
    roles = ("izvodjac",)

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        if "formset" not in context:
            context["formset"] = self.formset_class(instance=GKSheet())
        context.setdefault("sheet", None)
        context["title"] = "Nova građevinska knjiga"
        return context

    def post(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        self.object = None
        form = self.get_form()
        if form.is_valid():
            provisional_sheet: GKSheet = form.save(commit=False)
            formset = self.get_formset(instance=provisional_sheet, data=request.POST)
            if formset.is_valid() and self._formset_has_entries(formset):
                with transaction.atomic():
                    provisional_sheet.status = GKSheet.Status.DRAFT
                    provisional_sheet.save()
                    self.object = provisional_sheet
                    formset.instance = self.object
                    formset.save()
                messages.success(request, "Građevinska knjiga je sačuvana.")
                return redirect(self.get_success_url())
            if not formset.is_valid():
                return self.forms_invalid(form, formset)
            formset._non_form_errors = formset.error_class(["Dodajte bar jednu stavku u knjigu."])
            return self.forms_invalid(form, formset)
        project = None
        project_id = form.data.get("project")
        if project_id:
            project = Project.objects.filter(pk=project_id).first()
        temp_sheet = GKSheet(project=project)
        formset = self.get_formset(instance=temp_sheet, data=request.POST)
        return self.forms_invalid(form, formset)


class GKSheetDetailView(RoleRequiredMixin, DetailView):
    model = GKSheet
    context_object_name = "sheet"
    template_name = "core/sheet_detail.html"
    roles = ("izvodjac", "nadzor", "investitor")

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        sheet: GKSheet = context["sheet"]
        context["entries"] = sheet.entries.select_related("boq_item").all()
        context["can_edit"] = can_edit_sheet(self.request.user, sheet)
        context["can_submit"] = can_submit_sheet(self.request.user, sheet)
        context["can_review"] = can_review_sheet(self.request.user)
        return context


class GKSheetUpdateView(RoleRequiredMixin, SheetFormsetMixin, UpdateView):
    model = GKSheet
    template_name = "core/sheet_form.html"
    context_object_name = "sheet"
    roles = ("izvodjac",)

    def dispatch(self, request: HttpRequest, *args, **kwargs):
        self.object = self.get_object()
        if not can_edit_sheet(request.user, self.object):
            return HttpResponseForbidden("Izmena nije dozvoljena.")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        if "formset" not in context:
            context["formset"] = self.formset_class(instance=self.object)
        context["title"] = "Izmena građevinske knjige"
        return context

    def post(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        form = self.get_form()
        formset = self.get_formset(instance=self.object, data=request.POST)
        if form.is_valid() and formset.is_valid() and self._formset_has_entries(formset):
            with transaction.atomic():
                self.object = form.save()
                formset.instance = self.object
                formset.save()
            messages.success(request, "Građevinska knjiga je izmenjena.")
            return redirect(self.get_success_url())
        if formset.is_valid() and not self._formset_has_entries(formset):
            formset._non_form_errors = formset.error_class(["Dodajte bar jednu stavku u knjigu."])
        return self.forms_invalid(form, formset)


class GKSheetSubmitView(RoleRequiredMixin, View):
    model = GKSheet
    roles = ("izvodjac",)

    def post(self, request: HttpRequest, pk: int) -> HttpResponse:
        sheet = GKSheet.objects.select_related("project").prefetch_related("entries__boq_item").get(pk=pk)
        if not can_submit_sheet(request.user, sheet):
            return HttpResponseForbidden("Nema dovoljno prava za slanje ili knjiga nema stavke.")
        with transaction.atomic():
            sheet.review_tokens.update(used=True)
            sheet.status = GKSheet.Status.SUBMITTED
            sheet.save(update_fields=["status"])
            tokens = self._create_tokens(sheet)
        self._send_submit_email(request, sheet, tokens)
        messages.success(request, "Knjiga je poslata na reviziju.")
        return redirect(sheet.get_absolute_url())

    def _create_tokens(self, sheet: GKSheet) -> dict[str, ReviewToken]:
        expires_at = timezone.now() + timedelta(days=7)
        tokens = {}
        for token_type in (ReviewToken.TokenType.APPROVE, ReviewToken.TokenType.REJECT):
            token_value = secrets.token_urlsafe(32)
            tokens[token_type] = ReviewToken.objects.create(
                sheet=sheet,
                token=token_value,
                token_type=token_type,
                expires_at=expires_at,
            )
        return tokens

    def _send_submit_email(self, request: HttpRequest, sheet: GKSheet, tokens: dict[str, ReviewToken]) -> None:
        recipients = get_role_emails("nadzor")
        if not recipients:
            return
        approve_url = request.build_absolute_uri(reverse("core:review-approve", args=[tokens[ReviewToken.TokenType.APPROVE].token]))
        reject_url = request.build_absolute_uri(reverse("core:review-reject", args=[tokens[ReviewToken.TokenType.REJECT].token]))
        subject = f"GK sheet #{sheet.pk} – zahtev za pregled"
        message = (
            f"Knjiga: {sheet}\n"
            f"Projekat: {sheet.project.name}\n"
            f"Datum: {sheet.date:%Y-%m-%d}\n\n"
            f"Pregledajte knjigu i izaberite akciju:\n"
            f"Odobri: {approve_url}\n"
            f"Odbij: {reject_url}\n"
        )
        send_mail(subject, message, None, recipients)


class ReviewTokenBaseView(View):
    token_type: ReviewToken.TokenType

    def get(self, request: HttpRequest, token: str) -> HttpResponse:
        review_token = ReviewToken.objects.filter(token=token, token_type=self.token_type).select_related("sheet").first()
        if not review_token:
            return HttpResponse("Token nije pronađen.", status=404)
        if not review_token.is_valid():
            return HttpResponse("Token je iskorišćen ili istekao.")
        action = "odobravanje" if self.token_type == ReviewToken.TokenType.APPROVE else "odbijanje"
        return HttpResponse(f"Stub za {action}.")


class ReviewApproveView(ReviewTokenBaseView):
    token_type = ReviewToken.TokenType.APPROVE


class ReviewRejectView(ReviewTokenBaseView):
    token_type = ReviewToken.TokenType.REJECT


def index(request: HttpRequest) -> HttpResponse:
    return HttpResponse("Građevinska knjiga — radi")
