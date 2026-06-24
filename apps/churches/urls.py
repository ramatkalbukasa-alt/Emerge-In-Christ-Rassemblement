from django.urls import path

from . import views

app_name = "churches"

urlpatterns = [
    path("", views.extension_list, name="list"),
    path("nouvelle/", views.extension_create, name="create"),
    path("<slug:slug>/modifier/", views.extension_update, name="update"),
]
