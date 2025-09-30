from django.contrib import admin

from .models import BoQCategory, BoQItem, GKSheet, Project


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("name", "location", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name", "location")
    ordering = ("name",)


@admin.register(BoQCategory)
class BoQCategoryAdmin(admin.ModelAdmin):
    list_display = ("project", "sequence", "name")
    list_filter = ("project",)
    search_fields = ("name", "project__name")
    ordering = ("project__name", "sequence")


@admin.register(BoQItem)
class BoQItemAdmin(admin.ModelAdmin):
    list_display = ("code", "project", "category", "uom", "contract_qty", "unit_price")
    list_filter = ("project", "category")
    search_fields = ("code", "title", "project__name", "category__name")
    ordering = ("project__name", "category__sequence", "code")



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
