from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from apps.accounts.models import UserProfile

from .forms import ServiceReportForm
from .permissions import reports_for_user, user_extension, user_is_admin
from .models import ServiceReport
from .realtime import publish_report_created


@login_required
def report_list(request):
    reports = reports_for_user(request.user)
    return render(request, "reports/report_list.html", {"reports": reports})


@login_required
def report_detail(request, pk):
    report = get_object_or_404(reports_for_user(request.user), pk=pk)
    return render(request, "reports/report_detail.html", {"report": report})


@login_required
def report_create(request):
    initial = {}
    if not user_is_admin(request.user):
        initial["extension"] = user_extension(request.user)

    form = ServiceReportForm(request.POST or None, initial=initial)
    if not user_is_admin(request.user):
        form.fields["extension"].disabled = True
        form.fields["extension"].required = False

    if form.is_valid():
        report = form.save(commit=False)
        if not user_is_admin(request.user):
            report.extension = user_extension(request.user)
        report.submitted_by = request.user
        report.save()
        publish_report_created(report)
        return redirect("reports:detail", pk=report.pk)

    return render(request, "reports/report_form.html", {"form": form})
