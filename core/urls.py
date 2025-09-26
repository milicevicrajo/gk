from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.index, name="index"),
    path("sheets/", views.GKSheetListView.as_view(), name="sheet-list"),
    path("sheets/create/", views.GKSheetCreateView.as_view(), name="sheet-create"),
    path("sheets/<int:pk>/", views.GKSheetDetailView.as_view(), name="sheet-detail"),
    path("sheets/<int:pk>/edit/", views.GKSheetUpdateView.as_view(), name="sheet-update"),
    path("sheets/<int:pk>/submit/", views.GKSheetSubmitView.as_view(), name="sheet-submit"),
    path("review/<str:token>/approve/", views.ReviewApproveView.as_view(), name="review-approve"),
    path("review/<str:token>/reject/", views.ReviewRejectView.as_view(), name="review-reject"),
]
