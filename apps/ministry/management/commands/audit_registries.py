from django.core.management.base import BaseCommand
from django.db.models import Count
from apps.ministry.models import Person, PersonEvent, Allocation
from apps.reports.models import Newcomer, NewConvert, ServiceReport


class Command(BaseCommand):
    help = "Audit en lecture seule des registres et de la transition financière."

    def handle(self, *args, **options):
        self.stdout.write(f"Personnes : {Person.objects.filter(merged_into=None).count()}")
        self.stdout.write(f"Dates reprises à vérifier : {PersonEvent.objects.filter(date_inferred=True, person__merged_into=None).count()}")
        groups = Person.objects.filter(merged_into=None).values("extension_id", "name_key").annotate(n=Count("pk")).filter(n__gt=1)
        self.stdout.write(f"Groupes de noms similaires (à vérifier, pas fusionnés automatiquement) : {groups.count()}")
        self.stdout.write(f"Nouveaux venus sans lien : {Newcomer.objects.filter(person=None).count()}")
        self.stdout.write(f"Convertis sans lien : {NewConvert.objects.filter(person=None).count()}")
        self.stdout.write(f"Rapports historiques : {ServiceReport.objects.filter(financial_version=1).count()}")
        self.stdout.write(f"Allocations historiques inattendues : {Allocation.objects.filter(report__financial_version=1).count()}")
