from django.urls import path

from . import views

app_name = "reports"

urlpatterns = [
    path("", views.report_list, name="list"),
    path("nouveau/", views.report_create, name="create"),
    path("export/<str:file_format>/", views.reports_export, name="export"),
    path("<int:pk>/", views.report_detail, name="detail"),
    path("<int:pk>/imprimer/", views.report_print, name="print"),
    path("<int:pk>/export/<str:file_format>/", views.report_export, name="export_detail"),
]
