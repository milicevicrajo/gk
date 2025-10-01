from django import forms
from django_select2.forms import Select2MultipleWidget, Select2Widget

from .models import BoQCategory, BoQItem, GKSheet, Project


class BaseBootstrapForm(forms.ModelForm):
    select_fields = (forms.Select, forms.SelectMultiple)
    select2_map = {
        forms.Select: Select2Widget,
        forms.SelectMultiple: Select2MultipleWidget,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            for base_widget, select2_widget in self.select2_map.items():
                if isinstance(widget, select2_widget):
                    break
                if isinstance(widget, base_widget):
                    attrs = widget.attrs.copy()
                    choices = getattr(widget, 'choices', None)
                    field.widget = select2_widget(attrs=attrs)
                    if choices is not None:
                        field.widget.choices = choices
                    widget = field.widget
                    break
            existing = widget.attrs.get('class', '')
            if isinstance(widget, forms.CheckboxInput):
                css_class = 'form-check-input'
            elif isinstance(widget, (Select2Widget, Select2MultipleWidget)):
                css_class = 'form-select w-100'
                widget.attrs.setdefault('data-width', '100%')
                widget.attrs.setdefault('style', 'width: 100%;')
            elif isinstance(widget, self.select_fields):
                css_class = 'form-select w-100'
                widget.attrs.setdefault('style', 'width: 100%;')
            else:
                css_class = 'form-control'
            widget.attrs['class'] = f"{existing} {css_class}".strip()


class ProjectForm(BaseBootstrapForm):
    class Meta:
        model = Project
        fields = ['name', 'location', 'description', 'is_active']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
        }


class BoQCategoryForm(BaseBootstrapForm):
    class Meta:
        model = BoQCategory
        fields = ['project', 'sequence', 'name']

    def __init__(self, *args, project=None, **kwargs):
        super().__init__(*args, **kwargs)
        if project is not None:
            if isinstance(project, Project):
                project_instance = project
            else:
                project_instance = Project.objects.filter(pk=project).first()
            if project_instance:
                self.fields['project'].queryset = Project.objects.filter(pk=project_instance.pk)
                self.fields['project'].initial = project_instance
        self.fields['sequence'].widget.attrs.setdefault('min', 1)

    def clean_sequence(self):
        sequence = self.cleaned_data.get('sequence')
        project = self.cleaned_data.get('project')
        if sequence and project:
            qs = BoQCategory.objects.filter(project=project, sequence=sequence)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError('Redni broj je vec zauzet u okviru ovog projekta.')
        return sequence




class BoQItemForm(BaseBootstrapForm):
    class Meta:
        model = BoQItem
        fields = [ 'project', 'category', 'code', 'title', 'uom', 'contract_qty', 'unit_price', 'close_note']
        widgets = {
            'close_note': forms.Textarea(attrs={'rows': 3}),
            'project': Select2MultipleWidget(attrs={'class': 'select2-method'}),
        }

    def __init__(self, *args, project=None, **kwargs):
        self._project = project
        super().__init__(*args, **kwargs)
        self._set_category_queryset()
        numeric_fields = {'contract_qty': '0.001', 'unit_price': '0.01'}
        for name, step in numeric_fields.items():
            if name in self.fields:
                self.fields[name].widget.attrs.setdefault('step', step)
        if project is not None:
            project_instance = project if isinstance(project, Project) else Project.objects.filter(pk=project).first()
            if project_instance:
                self.fields['project'].queryset = Project.objects.filter(pk=project_instance.pk)
                self.fields['project'].initial = project_instance

    def _set_category_queryset(self):
        category_field = self.fields.get('category')
        if not category_field:
            return
        project_obj = None
        if self.data.get('project'):
            try:
                project_obj = Project.objects.filter(pk=int(self.data['project'])).first()
            except (ValueError, TypeError):
                project_obj = None
        if project_obj is None:
            project_obj = getattr(self.instance, 'project', None)
        if project_obj is None and self._project is not None:
            project_obj = self._project if isinstance(self._project, Project) else Project.objects.filter(pk=self._project).first()
        if project_obj is None:
            initial_project = self.initial.get('project')
            if initial_project:
                if isinstance(initial_project, Project):
                    project_obj = initial_project
                else:
                    project_obj = Project.objects.filter(pk=initial_project).first()
        if project_obj:
            category_field.queryset = BoQCategory.objects.filter(project=project_obj).order_by('sequence', 'name')
        else:
            category_field.queryset = BoQCategory.objects.none()

    def clean(self):
        cleaned = super().clean()
        project = cleaned.get('project')
        category = cleaned.get('category')
        if project and category and category.project_id != project.id:
            self.add_error('category', 'Kategorija mora pripadati izabranom projektu.')
        return cleaned


class GKSheetForm(BaseBootstrapForm):
    class Meta:
        model = GKSheet
        fields = [
            'project',
            'boq_item',
            'seq_no',
            'period_from',
            'period_to',
            'qty_this_period',
            'status',
            'note',
        ]
        widgets = {
            'period_from': forms.DateInput(attrs={'type': 'date'}),
            'period_to': forms.DateInput(attrs={'type': 'date'}),
            'note': forms.Textarea(attrs={'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        project = kwargs.pop('project', None)
        super().__init__(*args, **kwargs)
        self.fields['qty_this_period'].widget.attrs.setdefault('step', '0.001')
        if project is None and self.instance and self.instance.pk:
            project = self.instance.project
        self._set_boq_queryset(project)

    def _set_boq_queryset(self, project):
        if 'boq_item' not in self.fields:
            return
        if project:
            self.fields['boq_item'].queryset = BoQItem.objects.filter(project=project).order_by('code')
        else:
            self.fields['boq_item'].queryset = BoQItem.objects.select_related('project').order_by('project__name', 'code')

    def clean(self):
        cleaned = super().clean()
        project = cleaned.get('project')
        boq_item = cleaned.get('boq_item')
        if project and boq_item and boq_item.project_id != project.id:
            self.add_error('boq_item', 'BoQ stavka mora pripadati izabranom projektu.')
        return cleaned
    

ALLOWED_EXTS = {".xls", ".xlsx"}

class BoQExcelUploadForm(forms.Form):
    excel = forms.FileField(label="Excel (BoQ)", help_text=".xls ili .xlsx")
    clear_existing = forms.BooleanField(
        label="Obriši postojeće stavke i kategorije pre importa",
        required=False
    )

    def clean_excel(self):
        f = self.cleaned_data["excel"]
        name = (f.name or "").lower()
        if not any(name.endswith(ext) for ext in ALLOWED_EXTS):
            raise forms.ValidationError("Dozvoljeni formati su .xls i .xlsx")
        return f