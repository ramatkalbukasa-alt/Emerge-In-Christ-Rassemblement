from django.contrib import admin

from .models import NewConvert, ServiceReport


class NewConvertInline(admin.TabularInline):
    model = NewConvert
    extra = 0


@admin.register(ServiceReport)
class ServiceReportAdmin(admin.ModelAdmin):
    list_display = ("extension", "service_date", "service_type", "total_attendance", "total_offerings", "net_balance")
    list_filter = ("extension", "service_type", "service_date")
    search_fields = ("extension__name", "preacher", "theme")
    readonly_fields = ("total_attendance", "total_offerings", "tithe_deduction", "social_deduction", "net_balance")
    inlines = [NewConvertInline]


@admin.register(NewConvert)
class NewConvertAdmin(admin.ModelAdmin):
    list_display = ("full_name", "report", "phone", "follow_up_owner")
    search_fields = ("full_name", "phone", "follow_up_owner")
