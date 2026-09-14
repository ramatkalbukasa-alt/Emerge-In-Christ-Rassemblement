from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Sum
from django.shortcuts import render

from apps.churches.models import ChurchExtension
from apps.reports.permissions import reports_for_user, user_is_admin


@login_required
def home(request):
    reports = reports_for_user(request.user)
    totals = reports.aggregate(
        reports_count=Count("id"),
        attendance=Sum("total_attendance"),
    )
    known_currency = Q(currency__isnull=False) & ~Q(currency="")
    financial_totals = (
        reports.filter(known_currency).values("currency")
        .annotate(balance=Sum("net_balance"))
        .order_by("currency")
    )
    unknown_currency_count = reports.exclude(known_currency).count()
    extension_count = ChurchExtension.objects.count() if user_is_admin(request.user) else 1
    recent_reports = reports[:8]
    by_extension = (
        reports.values("extension_id", "extension__name", "extension__slug", "currency")
        .annotate(
            total=Sum("total_offerings", filter=known_currency),
            attendance=Sum("total_attendance"), count=Count("id"),
        )
        .order_by("extension__name", "extension_id", "currency")[:8]
    )

    return render(
        request,
        "dashboard/home.html",
        {
            "totals": totals,
            "financial_totals": financial_totals,
            "unknown_currency_count": unknown_currency_count,
            "extension_count": extension_count,
            "recent_reports": recent_reports,
            "by_extension": by_extension,
            "is_admin": user_is_admin(request.user),
        },
    )
