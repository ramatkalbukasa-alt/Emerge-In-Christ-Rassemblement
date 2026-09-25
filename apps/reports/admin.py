from django.contrib import admin

from .models import Expense, ExtraIncome, ExtraExpense, NewConvert, Newcomer, ServiceReport
from .models import ReportIncomeLine


class ReportIncomeLineInline(admin.TabularInline):
    model = ReportIncomeLine
    extra = 0
    can_delete = False
    fields = readonly_fields = ["category", "amount", "currency", "exchange_rate", "converted_amount"]

    def has_add_permission(self, request, obj=None):
        return False


class ExpenseInline(admin.TabularInline):
    model = Expense
    extra = 1
    fields = ["number", "amount", "reason"]


class NewConvertInline(admin.TabularInline):
    model = NewConvert
    extra = 0
    fields = ["full_name", "phone", "address", "follow_up_owner"]


class NewcomerInline(admin.TabularInline):
    model = Newcomer
    extra = 0
    fields = ["full_name", "invited_by"]


@admin.register(ServiceReport)
class ServiceReportAdmin(admin.ModelAdmin):
    list_display = [
        "service_date", "extension", "service_type",
        "total_attendance", "total_offerings", "total_expenses", "net_balance",
    ]
    list_filter = ["service_type", "extension", "service_date"]
    search_fields = ["extension__name", "preacher", "theme"]
    date_hierarchy = "service_date"
    readonly_fields = [
        "total_attendance", "total_offerings",
        "total_expenses", "tithe_deduction", "social_deduction", "net_balance",
    ]
    inlines = [ExpenseInline, NewcomerInline, NewConvertInline, ReportIncomeLineInline]

    def get_readonly_fields(self, request, obj=None):
        fields = list(super().get_readonly_fields(request, obj))
        if obj and obj.income_lines.exists():
            fields += ["currency", "extension", "offering_regular", "offering_preacher", "offering_tithe", "offering_thanksgiving"]
        return fields

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        form.instance.refresh_totals()

    fieldsets = [
        ("Informations du culte", {
            "fields": [
                "extension", "service_type", "service_date", "currency",
                "service_time_start", "service_time_end",
                "preacher", "moderator", "interpreter", "scripture_text", "theme",
            ]
        }),
        ("Effectif des présents", {
            "fields": ["papa_count", "maman_count", "brothers_count", "sisters_count", "children_count"]
        }),
        ("Offrandes", {
            "fields": ["offering_regular", "offering_preacher", "offering_tithe", "offering_thanksgiving"]
        }),
        ("Totaux calculés", {
            "classes": ["collapse"],
            "fields": [
                "total_attendance", "total_offerings",
                "total_expenses", "tithe_deduction", "social_deduction", "net_balance",
            ],
        }),
        ("Responsable", {"fields": ["submitted_by"]}),
    ]


@admin.register(ExtraIncome)
class ExtraIncomeAdmin(admin.ModelAdmin):
    list_display = ["income_date", "extension", "amount", "description"]
    list_filter = ["extension", "income_date"]


@admin.register(ExtraExpense)
class ExtraExpenseAdmin(admin.ModelAdmin):
    list_display = ["expense_date", "extension", "amount", "description"]
    list_filter = ["extension", "expense_date"]
