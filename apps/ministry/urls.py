from django.urls import path
from . import views

app_name = "ministry"
urlpatterns = [
    path("personnes/", views.people, name="people"),
    path("ouvriers/", views.people, {"workers": True}, name="workers"),
    path("personnes/<int:pk>/", views.person_detail, name="person_detail"),
    path("personnes/<int:pk>/rapprocher/", views.merge_person, name="merge_person"),
    path("departements/", views.departments, name="departments"),
    path("departements/catalogue/", views.catalog, name="catalog"),
    path("ajouter/<str:kind>/", views.edit, name="create"),
    path("modifier/<str:kind>/<int:pk>/", views.edit, name="edit"),
    path("accueil/<str:kind>/", views.events_report, name="events"),
    path("finances/regles/", views.policies, name="policies"),
    path("finances/rapports/<str:kind>/", views.financial_report, name="financial"),
    path("caisses/<str:fund>/", views.funds, name="funds"),
    path("allocation/<int:pk>/", views.allocation_detail, name="allocation"),
    path("remises/", views.remittances, name="remittances"),
    path("remises/<int:pk>/annuler/", views.cancel_remittance, name="cancel_payment"),
    path("parts/<int:pk>/supprimer/", views.delete_share, name="delete_share"),
]
