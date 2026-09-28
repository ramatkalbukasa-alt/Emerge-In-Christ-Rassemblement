from django.contrib import admin
from apps.reports.permissions import user_is_admin
from .models import AuditEntry


@admin.register(AuditEntry)
class AuditEntryAdmin(admin.ModelAdmin):
    list_display = ["created_at", "actor", "extension", "action", "target"]
    list_filter = ["extension", "action"]
    readonly_fields = ["created_at", "actor", "extension", "action", "target"]

    def has_view_permission(self, request, obj=None):
        return user_is_admin(request.user)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
