from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from apps.churches.models import AppSetting
from apps.reports.models import ServiceReport


class Command(BaseCommand):
    help = "Contrôle les données avant migration financière, sans aucune écriture."

    def handle(self, *args, **options):
        invalid_settings = list(
            AppSetting.objects.filter(
                Q(social_percentage__lt=0) | Q(social_percentage__gt=90)
            ).values_list("pk", flat=True)
        )
        invalid_reports = []
        fields = [
            "offering_regular", "offering_preacher", "offering_tithe",
            "offering_thanksgiving", "extra_income", "expenses",
        ]
        for row in ServiceReport.objects.values(
            "pk", *fields, "total_offerings", "tithe_deduction", "social_deduction", "net_balance"
        ).iterator():
            total = sum(row[name] for name in fields[:4])
            balance = (
                total - row["tithe_deduction"] - row["social_deduction"]
                + row["extra_income"] - row["expenses"]
            )
            if (
                any(row[name] < 0 for name in fields)
                or total != row["total_offerings"]
                or balance != row["net_balance"]
            ):
                invalid_reports.append(row["pk"])
        if invalid_settings or invalid_reports:
            raise CommandError(
                f"Vérification nécessaire. Paramètres invalides : {invalid_settings}. "
                f"Rapports incohérents : {invalid_reports}. Aucune donnée modifiée."
            )
        self.stdout.write(self.style.SUCCESS("Données financières cohérentes. Aucune donnée modifiée."))
