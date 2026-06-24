from django.contrib import admin

from .models import AppSetting, ChurchExtension


@admin.register(ChurchExtension)
class ChurchExtensionAdmin(admin.ModelAdmin):
    list_display = ("name", "city", "country", "pastor_name", "is_active")
    list_filter = ("is_active", "country")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name", "city", "pastor_name")


@admin.register(AppSetting)
class AppSettingAdmin(admin.ModelAdmin):
    list_display = ("church_name", "social_percentage", "updated_at")
