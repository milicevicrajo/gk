from django import forms
from django.forms import BaseInlineFormSet, inlineformset_factory

from .models import BoQItem, GKEntry, GKSheet


class GKSheetForm(forms.ModelForm):
    class Meta:
        model = GKSheet
        fields = ["project", "date", "note", "review_note"]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            "note": forms.Textarea(attrs={"rows": 4}),
            "review_note": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            existing_class = field.widget.attrs.get("class", "")
            if name == "project":
                field.widget.attrs["class"] = f"{existing_class} form-select".strip()
            else:
                field.widget.attrs["class"] = f"{existing_class} form-control".strip()
        self.fields["review_note"].widget.attrs.setdefault("readonly", True)


class GKEntryForm(forms.ModelForm):
    class Meta:
        model = GKEntry
        fields = ["boq_item", "quantity", "comment"]
        widgets = {
            "comment": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, project=None, **kwargs):
        super().__init__(*args, **kwargs)
        if project is None and getattr(self.instance, "sheet", None):
            project = getattr(self.instance.sheet, "project", None)
        self._project = project
        if project is not None:
            queryset = BoQItem.objects.filter(project=project)
        else:
            queryset = BoQItem.objects.all()
        self.fields["boq_item"].queryset = queryset
        for name, field in self.fields.items():
            existing_class = field.widget.attrs.get("class", "")
            if name == "boq_item":
                field.widget.attrs["class"] = f"{existing_class} form-select".strip()
            else:
                field.widget.attrs["class"] = f"{existing_class} form-control".strip()

    def clean_boq_item(self):
        boq_item = self.cleaned_data.get("boq_item")
        if boq_item and self._project and boq_item.project_id != getattr(self._project, "id", None):
            raise forms.ValidationError("BoQ stavka ne pripada izabranom projektu.")
        return boq_item


class BaseGKEntryInlineFormSet(BaseInlineFormSet):
    def get_form_kwargs(self, index):
        kwargs = super().get_form_kwargs(index)
        kwargs.setdefault("project", getattr(self.instance, "project", None))
        return kwargs


GKEntryFormSet = inlineformset_factory(
    GKSheet,
    GKEntry,
    form=GKEntryForm,
    formset=BaseGKEntryInlineFormSet,
    fields=["boq_item", "quantity", "comment"],
    extra=1,
    can_delete=True,
)
