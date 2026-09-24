from urllib.parse import unquote, urlsplit

from django.contrib.auth.views import LoginView
from django.urls import Resolver404, resolve


class AccountLoginView(LoginView):
    template_name = "accounts/login.html"

    def get_redirect_url(self):
        # Retain Django's host/scheme checks, then require a known absolute path.
        target = super().get_redirect_url()
        if not target:
            return ""
        path = unquote(urlsplit(target).path)
        if not path.startswith("/") or path.startswith("//"):
            return ""
        try:
            match = resolve(path)
        except Resolver404:
            return ""
        if match.url_name in {"login", "logout", "legacy_login", "legacy_login_slash"}:
            return ""
        return target
