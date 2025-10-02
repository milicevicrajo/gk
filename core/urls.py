from django.urls import path
from django.contrib.auth.views import LogoutView

from . import views

app_name = "core"

urlpatterns = [
    path('projects/', views.ProjectListView.as_view(), name='project-list'),
    path('projects/<int:pk>/', views.ProjectDetailView.as_view(), name='project-detail'),
    path('projects/<int:project_pk>/categories/create/', views.BoQCategoryCreateView.as_view(), name='boqcategory-create'),
    path('projects/create/', views.ProjectCreateView.as_view(), name='project-create'),
    path('projects/<int:pk>/edit/', views.ProjectUpdateView.as_view(), name='project-update'),
    path('projects/<int:pk>/delete/', views.ProjectDeleteView.as_view(), name='project-delete'),

    path('boq/', views.BoQItemListView.as_view(), name='boqitem-list'),
    path('boq/create/', views.BoQItemCreateView.as_view(), name='boqitem-create'),
    path('boq/<int:pk>/edit/', views.BoQItemUpdateView.as_view(), name='boqitem-update'),
    path('boq/<int:pk>/delete/', views.BoQItemDeleteView.as_view(), name='boqitem-delete'),
    path('boq/<int:pk>/', views.BoQItemDetailView.as_view(), name='boqitem-detail'),
    path("projects/<int:project_id>/boq/import/", views.BoQImportView.as_view(), name="boq_import"),
    
    path('login/', views.AppLoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(next_page='core:login'), name='logout'),

    path("", views.index, name="index"),
    path("sheets/", views.GKSheetListView.as_view(), name="sheet-list"),
    path("sheets/create/", views.GKSheetCreateView.as_view(), name="sheet-create"),
    path("sheets/<int:pk>/", views.GKSheetDetailView.as_view(), name="sheet-detail"),
    path("sheets/<int:pk>/edit/", views.GKSheetUpdateView.as_view(), name="sheet-update"),
    path("sheets/<int:pk>/delete/", views.GKSheetDeleteView.as_view(), name="sheet-delete"),
]
