from django.apps import AppConfig


class MinistryConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.ministry"
    verbose_name = "Registres et caisses"

    def ready(self):
        from . import signals  # noqa: F401
