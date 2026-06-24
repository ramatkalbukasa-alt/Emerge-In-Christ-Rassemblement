from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum
from django.shortcuts import render

from apps.churches.models import ChurchExtension
from apps.reports.permissions import reports_for_user, user_is_admin


@login_required
def home(request):
    reports = reports_for_user(request.user)
    totals = reports.aggregate(
        reports_count=Count("id"),
        attendance=Sum("total_attendance"),
        offerings=Sum("total_offerings"),
        balance=Sum("net_balance"),
        tithe=Sum("tithe_deduction"),
        social=Sum("social_deduction"),
    )
    extension_count = ChurchExtension.objects.count() if user_is_admin(request.user) else 1
    recent_reports = reports[:8]
    by_extension = (
        reports.values("extension__name")
        .annotate(total=Sum("total_offerings"), attendance=Sum("total_attendance"), count=Count("id"))
        .order_by("-total")[:8]
    )

    return render(
        request,
        "dashboard/home.html",
        {
            "totals": totals,
            "extension_count": extension_count,
            "recent_reports": recent_reports,
            "by_extension": by_extension,
            "is_admin": user_is_admin(request.user),
        },
    )
