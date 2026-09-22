from django.contrib import admin

from .models import AppSetting, ChurchExtension, Currency


@admin.register(Currency)
class CurrencyAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "symbol", "usd_rate", "is_active", "is_default")
    list_filter = ("is_active", "is_default")
    search_fields = ("code", "name")
    fieldsets = (
        ("Informations générales", {
            "fields": ("code", "name", "symbol", "is_active", "is_default"),
        }),
        ("Taux de change", {
            "fields": ("usd_rate",),
            "description": (
                "Taux de change vers USD. 1 unité de cette devise = X dollars USD. "
                "Exemple: 1 EUR = 1.08 USD, donc usd_rate = 1.08"
            ),
        }),
    )
    def get_readonly_fields(self, request, obj=None):
        return ("code",) if obj else ()


@admin.register(ChurchExtension)
class ChurchExtensionAdmin(admin.ModelAdmin):
    list_display = ("name", "city", "country", "pastor_name", "currency", "tithe_percentage", "social_percentage", "is_active")
    list_filter = ("is_active", "country", "currency")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name", "city", "pastor_name")
    fieldsets = (
        ("Informations générales", {
            "fields": ("name", "slug", "logo", "color", "city", "country", "address", "created_on", "is_active"),
        }),
        ("Responsables", {
            "fields": ("pastor_name", "pastor_email", "pastor_phone", "coordinator", "secretary", "treasurer"),
        }),
        ("Devise", {
            "fields": ("currency",),
            "description": (
                "Sélectionnez la devise par défaut pour cette extension. "
                "Les taux de change sont gérés dans la section Devises."
            ),
        }),
        ("Paramètres financiers", {
            "fields": ("tithe_percentage", "social_percentage"),
            "description": (
                "Ces pourcentages s'appliquent aux offrandes ordinaires, aux dîmes et aux actions de grâce. "
                "Les offrandes pour l'orateur ne subissent aucun prélèvement. "
                "Les modifications n'affectent pas les rapports déjà enregistrés."
            ),
        }),
    )


@admin.register(AppSetting)
class AppSettingAdmin(admin.ModelAdmin):
    list_display = ("church_name", "social_percentage", "updated_at")
