from decimal import Decimal
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class RegistryMigrationTests(TransactionTestCase):
    def test_existing_reports_and_people_are_preserved(self):
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        # Remove only the new app/schema; use historical models, without modern signals.
        executor.migrate([("ministry", None), ("reports", "0008_report_income_lines")])
        try:
            old = executor.loader.project_state([("reports", "0008_report_income_lines")]).apps
            Currency = old.get_model("churches", "Currency")
            Extension = old.get_model("churches", "ChurchExtension")
            Report = old.get_model("reports", "ServiceReport")
            Convert = old.get_model("reports", "NewConvert")
            currency = Currency.objects.get(code="USD")
            ext = Extension.objects.create(name="Historique", slug="migration-history", currency=currency)
            report = Report.objects.create(extension=ext, currency=currency, service_date="2025-01-05", offering_tithe=1000,
                tithe_deduction=1000, net_balance=0, total_offerings=1000)
            old_person = Convert.objects.create(report=report, full_name="Personne historique", phone="123", address="Adresse")
            executor = MigrationExecutor(connection)
            executor.migrate(latest)
            from apps.reports.models import ServiceReport, NewConvert
            from apps.ministry.models import PersonEvent, Allocation
            current = ServiceReport.objects.get(pk=report.pk)
            self.assertEqual(current.financial_version, 1)
            self.assertEqual(current.tithe_deduction, Decimal(1000))
            self.assertFalse(Allocation.objects.filter(report=current).exists())
            imported = NewConvert.objects.get(pk=old_person.pk)
            self.assertIsNotNone(imported.person_id)
            event = PersonEvent.objects.get(person=imported.person)
            self.assertTrue(event.date_inferred)
            self.assertEqual(event.person.phone, "123")
            current.refresh_totals()
            self.assertEqual(current.tithe_deduction, Decimal(1000))
        finally:
            MigrationExecutor(connection).migrate(latest)
