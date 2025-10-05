# filters.py
import django_filters as df
from django_select2.forms import Select2Widget, ModelSelect2Widget
from .models import GKSheet, Project, BoQItem

class BoQByProjectSelect2(ModelSelect2Widget):
    """
    Select2 widget sa pretragom za BoQItem.
    Optional: forward=["project"] – zavisi od polja 'project' u istoj formi.
    """
    model = BoQItem
    search_fields = [
        "code__icontains",
        "title__icontains",
        "project__name__icontains",
    ]

    def __init__(self, *args, **kwargs):
        # prosledi zavisnost od project-a ako želiš kaskadni filter
        forward = kwargs.pop("forward", None)
        super().__init__(*args, **kwargs)
        if forward:
            # django-select2 prosleđuje vrednost iz polja 'project' pod tim imenom
            self.forward = forward  # npr. ["project"]


class GKSheetFilter(df.FilterSet):
    project = df.ModelChoiceFilter(
        label="Projekat",
        field_name="project",                      # 👈 eksplicitno
        queryset=Project.objects.order_by("name"),
        widget=Select2Widget(attrs={
            "data-placeholder": "Svi projekti",
            "data-allow-clear": "true",
            "style": "width: 100%;",
            "class": "form-select",
        }),
    )

    boq = df.ModelChoiceFilter(                    # 👈 ime filtera ostaje 'boq'
        label="BoQ stavka",
        field_name="boq_item",                     # 👈 ali filtrira po 'boq_item'
        queryset=BoQItem.objects.select_related("project")
                              .order_by("project__name", "code"),
        widget=ModelSelect2Widget(
            model=BoQItem,
            search_fields=[
                "code__icontains",
                "title__icontains",
                "project__name__icontains",
            ],
            attrs={
                "data-placeholder": "Sve stavke",
                "data-allow-clear": "true",
                "style": "width: 100%;",
                "class": "form-select",
            },
            # opcionalno: forward=["project"],  # ako želiš kaskadni dropdown
        ),
    )

    class Meta:
        model = GKSheet
        fields = ["project", "boq"]
