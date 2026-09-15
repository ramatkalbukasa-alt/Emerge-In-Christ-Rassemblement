"""Service d'envoi d'emails SMTP pour Emerge In Christ Manager."""
from decimal import Decimal

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone


def _send(subject, template, context, recipients):
    """Envoie un email HTML + texte brut à une liste de destinataires."""
    if not recipients:
        return
    html_body = render_to_string(f"notifications/emails/{template}.html", context)
    text_body = render_to_string(f"notifications/emails/{template}.txt", context)
    email = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=recipients,
    )
    email.attach_alternative(html_body, "text/html")
    email.send(fail_silently=True)


def send_report_submitted_email(report):
    """Email envoyé aux admins lors de la soumission d'un nouveau rapport."""
    from django.contrib.auth import get_user_model

    User = get_user_model()
    admins = User.objects.filter(profile__role="admin").values_list("email", flat=True)
    recipients = [e for e in admins if e]

    from apps.churches.currency_service import get_currency_for_extension

    ext = report.extension
    ext_currency = get_currency_for_extension(ext)
    sym = ext_currency.symbol if ext_currency else "$"

    context = {
        "report": report,
        "extension": ext,
        "currency_symbol": sym,
        "site_name": "Emerge In Christ Manager",
        "now": timezone.now(),
    }
    subject = (
        f"[EIC] Nouveau rapport — {ext.name} "
        f"({report.service_date.strftime('%d/%m/%Y')})"
    )
    _send(subject, "report_submitted", context, recipients)


def send_monthly_summary_email(extension, year, month, reports):
    """Email récapitulatif mensuel envoyé aux admins."""
    from django.contrib.auth import get_user_model
    from django.db.models import Sum

    User = get_user_model()
    admins = User.objects.filter(profile__role="admin").values_list("email", flat=True)
    recipients = [e for e in admins if e]

    totals = reports.aggregate(
        total_presence=Sum("total_attendance"),
        total_offrandes=Sum("total_offerings"),
        total_dimes=Sum("tithe_deduction"),
        total_social=Sum("social_deduction"),
        total_depenses=Sum("total_expenses"),
        total_reste=Sum("net_balance"),
    )

    MOIS_FR = [
        "", "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
        "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre",
    ]
    from apps.churches.currency_service import get_currency_for_extension

    ext_currency = get_currency_for_extension(extension)
    context = {
        "extension": extension,
        "currency_symbol": ext_currency.symbol if ext_currency else "$",
        "year": year,
        "month_name": MOIS_FR[month],
        "reports": reports,
        "totals": totals,
        "site_name": "Emerge In Christ Manager",
        "now": timezone.now(),
    }
    subject = f"[EIC] Rapport mensuel — {MOIS_FR[month]} {year}"
    _send(subject, "monthly_summary", context, recipients)
