from django.contrib import admin

from . import models


@admin.register(models.Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)


@admin.register(models.BoQItem)
class BoQItemAdmin(admin.ModelAdmin):
    list_display = ("code", "project", "unit_of_measure", "contracted_quantity")
    list_filter = ("project",)
    search_fields = ("code", "description")


@admin.register(models.GKSheet)
class GKSheetAdmin(admin.ModelAdmin):
    list_display = ("project", "date", "status")
    list_filter = ("status", "project")
    search_fields = ("project__name", "note", "review_note")
    date_hierarchy = "date"


@admin.register(models.GKEntry)
class GKEntryAdmin(admin.ModelAdmin):
    list_display = ("sheet", "boq_item", "quantity")
    list_filter = ("sheet__project",)
    search_fields = ("sheet__project__name", "boq_item__code")


@admin.register(models.ReviewToken)
class ReviewTokenAdmin(admin.ModelAdmin):
    list_display = ("sheet", "token_type", "expires_at", "used")
    list_filter = ("token_type", "used")
    search_fields = ("token", "sheet__project__name")
