from django.contrib import admin

from .models import BoQItem, GKSheet, Project


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("name", "location", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name", "location")
    ordering = ("name",)


@admin.register(BoQItem)
class BoQItemAdmin(admin.ModelAdmin):
    list_display = ("code", "project", "uom", "contract_qty", "unit_price", "is_closed")
    list_filter = ("project", "closed_at")
    search_fields = ("code", "title", "project__name")
    ordering = ("project__name", "code")
    readonly_fields = ("closed_at",)


@admin.register(GKSheet)
class GKSheetAdmin(admin.ModelAdmin):
    list_display = ("project", "boq_item", "seq_no", "status", "qty_this_period", "qty_cumulative", "created_by", "created_at")
    list_filter = ("status", "project", "boq_item")
    search_fields = ("boq_item__code", "boq_item__title", "project__name")
    ordering = ("boq_item__code", "seq_no")
    readonly_fields = ("qty_cumulative", "created_by", "created_at", "updated_at")

    def get_readonly_fields(self, request, obj=None):
        if obj is None:
            return tuple(field for field in self.readonly_fields if field != "created_by")
        return self.readonly_fields

    def save_model(self, request, obj, form, change):
        if not change and not obj.created_by_id:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
