from django.urls import path

from . import views

app_name = "reports"

urlpatterns = [
    # Rapports principaux
    path("", views.report_list, name="list"),
    path("nouveau/", views.report_create, name="create"),
    path("export/<str:file_format>/", views.reports_export, name="export"),
    path("<int:pk>/", views.report_detail, name="detail"),
    path("<int:pk>/imprimer/", views.report_print, name="print"),
    path("<int:pk>/export/<str:file_format>/", views.report_export, name="export_detail"),

    # Recettes et Dépenses supplémentaires
    path("recettes-supplementaires/", views.extra_income_list, name="extra_income_list"),
    path("recettes-supplementaires/ajouter/", views.extra_income_create, name="extra_income_create"),
    path("depenses-supplementaires/", views.extra_expense_list, name="extra_expense_list"),
    path("depenses-supplementaires/ajouter/", views.extra_expense_create, name="extra_expense_create"),

    # Rapports périodiques
    path("mensuel/<int:year>/<int:month>/imprimer/", views.report_monthly_print, name="monthly_print"),
    path("trimestriel/<int:year>/<int:quarter>/imprimer/", views.report_quarterly_print, name="quarterly_print"),
    path("annuel/<int:year>/imprimer/", views.report_annual_print, name="annual_print"),

    # API — calcul financier temps réel (formulaire)
    path("api/financial-preview/", views.report_financial_preview, name="financial_preview"),
]
