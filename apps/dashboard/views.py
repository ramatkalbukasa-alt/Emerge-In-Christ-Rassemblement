import json
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Max, Min, Sum
from django.shortcuts import render
from django.core.exceptions import PermissionDenied
from django.contrib import admin

from apps.churches.models import ChurchExtension, Currency
from apps.churches.currency_service import convert_currency, get_currency_for_extension, get_exchange_rate, CurrencyConversionError
from apps.reports.permissions import reports_for_user, user_extension, user_is_admin


@login_required
def administration(request):
    if not (user_is_admin(request.user) or request.user.is_staff):
        raise PermissionDenied
    return render(request, "dashboard/administration.html", {
        "admin_apps": admin.site.get_app_list(request) if request.user.is_staff else [],
        "is_admin": user_is_admin(request.user),
    })


@login_required
def home(request):
    reports = reports_for_user(request.user)
    totals = reports.aggregate(
        reports_count=Count("id"),
        attendance=Sum("total_attendance"),
        period_start=Min("service_date"),
        period_end=Max("service_date"),
    )
    is_admin = user_is_admin(request.user)
    extension = user_extension(request.user)
    active_extensions = ChurchExtension.objects.filter(is_active=True)
    if not is_admin:
        active_extensions = active_extensions.filter(pk=extension.pk) if extension else active_extensions.none()
    extension_count = active_extensions.count()

    # Preserve the report-only scope and stored financial formulas. Use the
    # existing currency conversion service, as the periodic reports do.
    display_currency = Currency.get_default() if is_admin else get_currency_for_extension(extension)
    conversion_rates = {}
    financial_available = display_currency is not None
    has_conversion = False
    recent_reports = []
    grouped = {}
    fields = {"offerings": "total_offerings", "balance": "net_balance", "tithe": "tithe_deduction", "social": "social_deduction"}
    totals.update({key: Decimal("0") for key in fields})
    for report in reports.select_related("currency", "extension__currency").iterator():
        if len(recent_reports) < 8:
            recent_reports.append(report)
        row = grouped.setdefault(report.extension_id, {
            "extension__name": report.extension.name, "total": Decimal("0"), "attendance": 0, "count": 0,
        })
        row["attendance"] += report.total_attendance
        row["count"] += 1
        source = report.currency or get_currency_for_extension(report.extension)
        report.source_currency = source
        try:
            rate = get_exchange_rate(source, display_currency)
            amounts = {key: convert_currency(getattr(report, field), source, display_currency) for key, field in fields.items()}
        except CurrencyConversionError:
            financial_available = False
            continue
        has_conversion |= source.pk != display_currency.pk
        conversion_rates[source.code] = {"source": source.code, "rate": rate}
        for key, amount in amounts.items():
            totals[key] += amount
        row["total"] += amounts["offerings"]
        report.dashboard_offerings = amounts["offerings"]
        report.dashboard_balance = amounts["balance"]

    if not financial_available:
        # Never present a partial consolidation as the global balance.
        totals.update({key: None for key in fields})
        for row in grouped.values():
            row["total"] = None
    by_extension = sorted(grouped.values(), key=lambda row: -(row["total"] or 0))[:8]

    # ── Chart: trend over last 8 reports (oldest → newest) ─────────────────
    trend_labels = [str(r.service_date) for r in reversed(recent_reports)] if financial_available else []
    trend_offerings = [float(r.dashboard_offerings) for r in reversed(recent_reports)] if financial_available else []
    trend_balances = [float(r.dashboard_balance) for r in reversed(recent_reports)] if financial_available else []

    # ── Chart: per-extension breakdown ─────────────────────────────────────
    ext_labels = [row["extension__name"] for row in by_extension]
    ext_attendance = [row["attendance"] or 0 for row in by_extension]
    ext_offerings = [float(row["total"] or 0) for row in by_extension]

    # ── Chart: financial ventilation donut ─────────────────────────────────
    tithe_val = float(totals.get("tithe") or 0)
    social_val = float(totals.get("social") or 0)
    balance_val = float(totals.get("balance") or 0)

    return render(
        request,
        "dashboard/home.html",
        {
            "totals": totals,
            "extension_count": extension_count,
            "recent_reports": recent_reports,
            "by_extension": by_extension,
            "is_admin": is_admin,
            "period_start": totals["period_start"],
            "period_end": totals["period_end"],
            "display_currency": display_currency,
            "financial_available": financial_available,
            "has_conversion": has_conversion,
            "conversion_rates": list(conversion_rates.values()),
            # JSON payloads for Chart.js
            "chart_trend_labels": json.dumps(trend_labels),
            "chart_trend_offerings": json.dumps(trend_offerings),
            "chart_trend_balances": json.dumps(trend_balances),
            "chart_ext_labels": json.dumps(ext_labels),
            "chart_ext_attendance": json.dumps(ext_attendance),
            "chart_ext_offerings": json.dumps(ext_offerings),
            "chart_ventilation": json.dumps([tithe_val, social_val, max(balance_val, 0)]),
        },
    )
