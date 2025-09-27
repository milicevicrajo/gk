from django import forms

from .models import BoQItem, GKSheet, Project


class BaseBootstrapForm(forms.ModelForm):
    select_fields = (forms.Select, forms.SelectMultiple)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            existing = widget.attrs.get('class', '')
            if isinstance(widget, forms.CheckboxInput):
                css_class = 'form-check-input'
            elif isinstance(widget, self.select_fields):
                css_class = 'form-select'
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


class BoQItemForm(BaseBootstrapForm):
    class Meta:
        model = BoQItem
        fields = ['project', 'code', 'title', 'uom', 'contract_qty', 'unit_price', 'closed_at', 'close_note']
        widgets = {
            'close_note': forms.Textarea(attrs={'rows': 3}),
            'closed_at': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        numeric_fields = {'contract_qty': '0.001', 'unit_price': '0.01'}
        for name, step in numeric_fields.items():
            if name in self.fields:
                self.fields[name].widget.attrs.setdefault('step', step)


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
