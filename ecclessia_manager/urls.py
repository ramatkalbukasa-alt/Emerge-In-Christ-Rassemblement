from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path
from django.views.generic import RedirectView

from apps.accounts.views import AccountLoginView


urlpatterns = [
    path("admin/", admin.site.urls),
    path(
        "login/",
        AccountLoginView.as_view(),
        name="login",
    ),
    path("login/Nous", RedirectView.as_view(pattern_name="dashboard:home"), name="legacy_login"),
    path("login/Nous/", RedirectView.as_view(pattern_name="dashboard:home"), name="legacy_login_slash"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("", include("apps.dashboard.urls")),
    path("extensions/", include("apps.churches.urls")),
    path("rapports/", include("apps.reports.urls")),
    path("notifications/", include("apps.notifications.urls")),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
