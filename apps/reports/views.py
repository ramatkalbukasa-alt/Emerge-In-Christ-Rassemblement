import csv
from io import BytesIO

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from docx import Document
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .forms import ServiceReportForm
from .permissions import reports_for_user, user_extension, user_is_admin
from .realtime import publish_report_created


def _report_filename(report, extension):
    date_part = report.service_date.isoformat()
    slug = report.extension.slug
    return f"rapport-{slug}-{date_part}.{extension}"


def _money(value):
    return f"{value:.2f}"


def _report_rows(report):
    return [
        ("Extension", report.extension.name),
        ("Devise", report.currency_label),
        ("Taux social applique (%)", report.social_percentage_applied
         if report.social_percentage_applied is not None else "Historique inconnu"),
        ("Date", report.service_date),
        ("Type", report.get_service_type_display()),
        ("Predicateur", report.preacher or ""),
        ("Theme", report.theme or ""),
        ("Hommes", report.men_count),
        ("Femmes", report.women_count),
        ("Enfants", report.children_count),
        ("Visiteurs", report.visitors_count),
        ("Presence totale", report.total_attendance),
        ("Offrandes ordinaires", _money(report.offering_regular)),
        ("Offrande orateur", _money(report.offering_preacher)),
        ("Dimes", _money(report.offering_tithe)),
        ("Actions de grace", _money(report.offering_thanksgiving)),
        ("Recettes supplementaires", _money(report.extra_income)),
        ("Depenses", _money(report.expenses)),
        ("Total offrandes", _money(report.total_offerings)),
        ("Ventilation dimes", _money(report.tithe_deduction)),
        ("Ventilation sociale", _money(report.social_deduction)),
        ("Dime + social", _money(report.total_deductions)),
        ("Solde net", _money(report.net_balance)),
        ("Notes", report.notes or ""),
    ]


def _export_report_csv(report):
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{_report_filename(report, "csv")}"'
    response.write("\ufeff")
    writer = csv.writer(response)
    writer.writerow(["Champ", "Valeur"])
    writer.writerows(_report_rows(report))
    return response


def _export_report_docx(report):
    document = Document()
    document.add_heading(f"Rapport - {report.extension.name}", level=1)
    document.add_paragraph(f"{report.get_service_type_display()} du {report.service_date}")

    table = document.add_table(rows=1, cols=2)
    table.style = "Table Grid"
    table.rows[0].cells[0].text = "Champ"
    table.rows[0].cells[1].text = "Valeur"
    for label, value in _report_rows(report):
        cells = table.add_row().cells
        cells[0].text = str(label)
        cells[1].text = str(value)

    buffer = BytesIO()
    document.save(buffer)
    response = HttpResponse(
        buffer.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    response["Content-Disposition"] = f'attachment; filename="{_report_filename(report, "docx")}"'
    return response


def _export_report_pdf(report):
    buffer = BytesIO()
    document = SimpleDocTemplate(buffer, pagesize=A4, title=f"Rapport {report.extension.name}")
    styles = getSampleStyleSheet()
    rows = [["Champ", "Valeur"], *[[label, str(value)] for label, value in _report_rows(report)]]
    table = Table(rows, colWidths=[170, 330])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F2937")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D1D5DB")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F9FAFB")]),
            ]
        )
    )
    story = [
        Paragraph(f"Rapport - {report.extension.name}", styles["Title"]),
        Paragraph(f"{report.get_service_type_display()} du {report.service_date}", styles["Normal"]),
        Spacer(1, 18),
        table,
    ]
    document.build(story)
    response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{_report_filename(report, "pdf")}"'
    return response


def _export_reports_csv(reports):
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="rapports.csv"'
    response.write("\ufeff")
    writer = csv.writer(response)
    writer.writerow(
        [
            "Date",
            "Extension",
            "Devise",
            "Type",
            "Presence",
            "Offrandes",
            "Dimes",
            "Social",
            "Depenses",
            "Solde",
        ]
    )
    for report in reports:
        writer.writerow(
            [
                report.service_date,
                report.extension.name,
                report.currency_label,
                report.get_service_type_display(),
                report.total_attendance,
                _money(report.total_offerings),
                _money(report.tithe_deduction),
                _money(report.social_deduction),
                _money(report.expenses),
                _money(report.net_balance),
            ]
        )
    return response


@login_required
def report_list(request):
    reports = reports_for_user(request.user)
    return render(request, "reports/report_list.html", {"reports": reports})


@login_required
def report_detail(request, pk):
    report = get_object_or_404(reports_for_user(request.user), pk=pk)
    return render(request, "reports/report_detail.html", {"report": report})


@login_required
def report_print(request, pk):
    report = get_object_or_404(reports_for_user(request.user), pk=pk)
    return render(request, "reports/report_print.html", {"report": report})


@login_required
def report_export(request, pk, file_format):
    report = get_object_or_404(reports_for_user(request.user), pk=pk)
    exporters = {
        "csv": _export_report_csv,
        "docx": _export_report_docx,
        "pdf": _export_report_pdf,
    }
    exporter = exporters.get(file_format)
    if exporter is None:
        return redirect("reports:detail", pk=report.pk)
    return exporter(report)


@login_required
def reports_export(request, file_format):
    reports = reports_for_user(request.user)
    if file_format == "csv":
        return _export_reports_csv(reports)
    if file_format == "html":
        html = render_to_string("reports/report_collection_print.html", {"reports": reports}, request=request)
        return HttpResponse(html)
    return redirect("reports:list")


@login_required
def report_create(request):
    initial = {}
    if not user_is_admin(request.user):
        extension = user_extension(request.user)
        if extension is None or not extension.is_active:
            raise PermissionDenied("Une extension active doit être affectée à votre compte.")
        initial["extension"] = extension

    form = ServiceReportForm(request.POST or None, initial=initial)
    if not user_is_admin(request.user):
        form.fields["extension"].disabled = True
        form.fields["extension"].required = False

    if form.is_valid():
        report = form.save(commit=False)
        if not user_is_admin(request.user):
            report.extension = user_extension(request.user)
        report.submitted_by = request.user
        try:
            with transaction.atomic():
                report.save()
                transaction.on_commit(lambda: publish_report_created(report), robust=True)
        except ValidationError as error:
            form.add_error(None, error.messages)
        else:
            return redirect("reports:detail", pk=report.pk)

    return render(request, "reports/report_form.html", {"form": form})
