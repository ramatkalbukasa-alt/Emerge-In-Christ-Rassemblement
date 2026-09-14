import csv
from datetime import date
from decimal import Decimal
from io import BytesIO, StringIO
from unittest.mock import patch

from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from docx import Document

from apps.accounts.models import UserProfile
from apps.churches.models import AppSetting, ChurchExtension
from ecclessia_manager.asgi import application

from .consumers import ReportEventsConsumer
from .forms import ServiceReportForm
from .models import ServiceReport
from .realtime import publish_report_created
from .services import compute_ventilation


TEST_STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
MEMORY_CHANNELS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}


def make_user(username, extension=None, role=UserProfile.Role.EXTENSION):
    user = get_user_model().objects.create_user(username=username)
    UserProfile.objects.create(user=user, role=role, extension=extension)
    return user


def report_data(extension, **overrides):
    return {
        "extension": extension.pk, "service_date": "2026-09-13", "service_type": "sunday",
        "men_count": 10, "women_count": 12, "children_count": 3, "visitors_count": 2,
        "offering_regular": "100.50", "offering_preacher": "0.00", "offering_tithe": "0.00",
        "offering_thanksgiving": "0.00", "extra_income": "0.00", "expenses": "0.00",
        **overrides,
    }


class FinanceTests(TestCase):
    def setUp(self):
        self.extension = ChurchExtension.objects.create(name="Alpha", slug="alpha")
        self.setting = AppSetting.current()

    def create_report(self, **overrides):
        return ServiceReport.objects.create(
            extension=self.extension, service_date=date(2026, 9, 13),
            offering_regular=Decimal("100.50"), **overrides,
        )

    def test_nominal_rounding_and_deficit(self):
        report = self.create_report(expenses=Decimal("100"))
        self.assertEqual(report.total_offerings, Decimal("100.50"))
        self.assertEqual(report.tithe_deduction, Decimal("10.05"))
        self.assertEqual(report.social_deduction, Decimal("5.03"))
        self.assertEqual(report.total_deductions, Decimal("15.08"))
        self.assertEqual(report.net_balance, Decimal("-14.58"))
        self.assertEqual(report.social_percentage_applied, Decimal("5"))
        self.assertEqual(report.calculation_version, 1)

    def test_negative_inputs_rejected_by_forms_and_database(self):
        report = self.create_report()
        for field in report.financial_inputs:
            with self.subTest(field=field):
                form = ServiceReportForm(data=report_data(self.extension, **{field: "-1"}))
                self.assertFalse(form.is_valid())
                self.assertIn(field, form.errors)
                with self.assertRaises(IntegrityError), transaction.atomic():
                    ServiceReport.objects.filter(pk=report.pk).update(**{field: -1})

    def test_model_save_rejects_invalid_input(self):
        with self.assertRaises(ValidationError):
            self.create_report(expenses=Decimal("-1"))
        self.assertFalse(ServiceReport.objects.exists())

    def test_service_rejects_negative_and_nonfinite_amounts(self):
        for amount in ("-1", "NaN", "Infinity", "invalid"):
            with self.subTest(amount=amount), self.assertRaises(ValidationError):
                compute_ventilation(amount, 0, 0, 0, 5)

    def test_invalid_rates_rejected_by_model_database_and_service(self):
        for rate in (-5, 91, 150):
            with self.subTest(rate=rate):
                self.setting.social_percentage = rate
                with self.assertRaises(ValidationError):
                    self.setting.full_clean()
                with self.assertRaises(IntegrityError), transaction.atomic():
                    AppSetting.objects.filter(pk=self.setting.pk).update(social_percentage=rate)
                with self.assertRaises(ValidationError):
                    compute_ventilation(100, 0, 0, 0, rate)

    def test_boundary_rates_preserve_conservation_at_cent_rounding(self):
        for rate in (0, 5, 90):
            for cents in range(1, 101):
                with self.subTest(rate=rate, cents=cents):
                    amount = Decimal(cents) / 100
                    result = compute_ventilation(amount, 0, 0, 0, rate)
                    self.assertGreaterEqual(result["offering_remainder"], 0)
                    self.assertEqual(
                        result["total_dime"] + result["total_social"] + result["offering_remainder"], amount
                    )

    def test_aggregate_overflow_is_a_form_error(self):
        form = ServiceReportForm(data=report_data(
            self.extension, offering_regular="9999999999.99", offering_preacher="9999999999.99"
        ))
        self.assertFalse(form.is_valid())
        self.assertIn("total_offerings", str(form.non_field_errors()))

    def test_note_edits_preserve_historical_amounts_and_currency(self):
        report = self.create_report()
        self.setting.social_percentage = 10
        self.setting.save()
        self.extension.currency = "USD"
        self.extension.save()
        report.notes = "Texte corrigé"
        report.save()
        report.refresh_from_db()
        self.assertEqual(report.net_balance, Decimal("85.42"))
        self.assertEqual(report.social_percentage_applied, Decimal("5"))
        self.assertEqual(report.currency, "EUR")
        new = ServiceReport.objects.create(extension=self.extension, service_date=date(2026, 9, 20))
        self.assertEqual(new.social_percentage_applied, Decimal("10"))
        self.assertEqual(new.currency, "USD")

    def test_partial_financial_save_recalculates_only_persisted_inputs(self):
        report = self.create_report()
        report.offering_regular = Decimal("200")
        report.expenses = Decimal("99")
        report.save(update_fields=["offering_regular"])
        report.refresh_from_db()
        self.assertEqual(report.offering_regular, Decimal("200"))
        self.assertEqual(report.expenses, Decimal("0"))
        self.assertEqual(report.total_offerings, Decimal("200"))
        self.assertEqual(report.net_balance, Decimal("170"))

    def test_partial_notes_and_attendance_do_not_save_pending_money_edits(self):
        report = self.create_report(men_count=1, women_count=2)
        report.offering_regular = Decimal("-50")
        report.notes = "Annotation"
        report.men_count = 4
        report.women_count = 100
        report.save(update_fields=["notes", "men_count"])
        report.refresh_from_db()
        self.assertEqual(report.total_attendance, 6)
        self.assertEqual(report.women_count, 2)
        self.assertEqual(report.net_balance, Decimal("85.42"))
        self.assertEqual(report.offering_regular, Decimal("100.50"))

    def test_legacy_money_remains_unchanged_and_cannot_be_recalculated(self):
        report = self.create_report()
        ServiceReport.objects.filter(pk=report.pk).update(
            social_percentage_applied=None, calculation_version=None, currency=None
        )
        report.refresh_from_db()
        report.notes = "Annotation historique"
        report.save()
        self.assertEqual(report.net_balance, Decimal("85.42"))
        self.assertIsNone(report.social_percentage_applied)
        self.assertIsNone(report.currency)
        report.offering_regular = Decimal("200")
        with self.assertRaises(ValidationError):
            report.save()
        report.refresh_from_db()
        self.assertEqual(report.offering_regular, Decimal("100.50"))

    def test_preflight_detects_incoherence_without_modifying_data(self):
        report = self.create_report()
        call_command("check_financial_data", stdout=StringIO())
        ServiceReport.objects.filter(pk=report.pk).update(total_offerings=Decimal("999"))
        with self.assertRaises(CommandError):
            call_command("check_financial_data", stdout=StringIO())
        report.refresh_from_db()
        self.assertEqual(report.total_offerings, Decimal("999"))


@override_settings(STORAGES=TEST_STORAGES, CHANNEL_LAYERS=MEMORY_CHANNELS)
class ReportViewsTests(TestCase):
    def setUp(self):
        self.extension = ChurchExtension.objects.create(name="Même nom", slug="alpha", currency="EUR")
        self.other = ChurchExtension.objects.create(name="Même nom", slug="beta", currency="USD")
        self.user = make_user("reader", self.extension)
        self.admin = make_user("manager", role=UserProfile.Role.ADMIN)
        self.client.force_login(self.user)

    def create_report(self, extension=None, **overrides):
        return ServiceReport.objects.create(
            extension=extension or self.extension, service_date=date(2026, 9, 13),
            offering_regular=Decimal("100.50"), **overrides,
        )

    def test_http_isolation_and_forged_extension(self):
        foreign = self.create_report(self.other)
        for name, extra in (("detail", {}), ("print", {}), ("export_detail", {"file_format": "csv"})):
            with self.subTest(route=name):
                self.assertEqual(self.client.get(reverse(f"reports:{name}", kwargs={
                    "pk": foreign.pk, **extra
                })).status_code, 404)
        response = self.client.post(reverse("reports:create"), report_data(self.other))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(ServiceReport.objects.exclude(pk=foreign.pk).get().extension_id, self.extension.pk)

    def test_duplicate_and_invalid_money_return_form_errors(self):
        self.create_report()
        response = self.client.post(reverse("reports:create"), report_data(self.extension))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].non_field_errors())
        response = self.client.post(reverse("reports:create"), report_data(
            self.extension, service_date="2026-09-20", expenses="-10"
        ))
        self.assertEqual(response.status_code, 200)
        self.assertIn("expenses", response.context["form"].errors)
        self.assertEqual(ServiceReport.objects.count(), 1)

    def test_missing_or_inactive_extension_is_denied(self):
        self.extension.is_active = False
        self.extension.save()
        self.assertEqual(self.client.post(reverse("reports:create"), report_data(self.extension)).status_code, 403)
        UserProfile.objects.filter(user=self.user).update(extension=None)
        self.assertEqual(self.client.post(reverse("reports:create"), report_data(self.extension)).status_code, 403)
        self.assertFalse(ServiceReport.objects.exists())

    def test_dashboard_separates_identifiers_and_currencies(self):
        self.create_report()
        self.create_report(self.other)
        self.client.force_login(self.admin)
        response = self.client.get(reverse("dashboard:home"))
        balances = {row["currency"]: row["balance"] for row in response.context["financial_totals"]}
        self.assertEqual(balances, {"EUR": Decimal("85.42"), "USD": Decimal("85.42")})
        groups = list(response.context["by_extension"])
        self.assertEqual({row["extension_id"] for row in groups}, {self.extension.pk, self.other.pk})
        self.assertEqual(len(groups), 2)
        self.client.force_login(self.user)
        response = self.client.get(reverse("dashboard:home"))
        self.assertEqual(len(response.context["financial_totals"]), 1)

    def test_unknown_currency_is_excluded_instead_of_invented(self):
        report = self.create_report()
        ServiceReport.objects.filter(pk=report.pk).update(currency=None)
        response = self.client.get(reverse("dashboard:home"))
        self.assertEqual(response.context["unknown_currency_count"], 1)
        self.assertEqual(len(response.context["financial_totals"]), 0)
        self.assertIsNone(response.context["by_extension"][0]["total"])
        self.assertContains(response, "exclus des totaux financiers")

    def test_cent_precision_and_currency_in_screens_and_exports(self):
        report = self.create_report()
        self.extension.currency = "USD"
        self.extension.save()
        for name in ("detail", "print"):
            response = self.client.get(reverse(f"reports:{name}", args=[report.pk]))
            self.assertContains(response, "15,08")
            self.assertContains(response, "EUR")
            self.assertNotContains(response, "USD")
        response = self.client.get(reverse("reports:export_detail", args=[report.pk, "csv"]))
        rows = dict(csv.reader(StringIO(response.content.decode("utf-8-sig"))))
        self.assertEqual(rows["Dime + social"], "15.08")
        self.assertEqual(rows["Devise"], "EUR")
        response = self.client.get(reverse("reports:export_detail", args=[report.pk, "docx"]))
        rows = {row.cells[0].text: row.cells[1].text for row in Document(BytesIO(response.content)).tables[0].rows}
        self.assertEqual(rows["Dime + social"], "15.08")
        self.assertEqual(rows["Devise"], "EUR")
        response = self.client.get(reverse("reports:export_detail", args=[report.pk, "pdf"]))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content.startswith(b"%PDF"))
        response = self.client.get(reverse("reports:export", args=["csv"]))
        rows = list(csv.DictReader(StringIO(response.content.decode("utf-8-sig"))))
        self.assertEqual(rows[0]["Devise"], "EUR")
        response = self.client.get(reverse("reports:export", args=["html"]))
        self.assertContains(response, "<td>EUR</td>", html=True)


@override_settings(STORAGES=TEST_STORAGES)
class PublicationTests(TransactionTestCase):
    def setUp(self):
        self.extension = ChurchExtension.objects.create(name="Alpha", slug="alpha")
        self.client.force_login(make_user("reader", self.extension))

    def test_notification_failure_does_not_turn_success_into_error(self):
        with patch("apps.reports.views.publish_report_created", side_effect=ConnectionError("Redis unavailable")):
            with self.assertLogs("django.db.backends.base", level="ERROR"):
                response = self.client.post(reverse("reports:create"), report_data(self.extension))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(ServiceReport.objects.count(), 1)

    def test_publication_waits_for_commit_and_is_discarded_on_rollback(self):
        with patch("apps.reports.views.publish_report_created") as publish:
            with transaction.atomic():
                self.client.post(reverse("reports:create"), report_data(self.extension))
                publish.assert_not_called()
            publish.assert_called_once()
        with patch("apps.reports.views.publish_report_created") as publish:
            with transaction.atomic():
                self.client.post(reverse("reports:create"), report_data(self.extension, service_date="2026-09-20"))
                transaction.set_rollback(True)
            publish.assert_not_called()
        self.assertEqual(ServiceReport.objects.count(), 1)


@override_settings(CHANNEL_LAYERS=MEMORY_CHANNELS)
class RealtimeTests(TransactionTestCase):
    def setUp(self):
        self.extension = ChurchExtension.objects.create(name="Alpha", slug="alpha")
        self.other = ChurchExtension.objects.create(name="Beta", slug="beta")
        self.reader = make_user("reader", self.extension)
        self.foreign = make_user("foreign", self.other)
        self.admin = make_user("manager", role=UserProfile.Role.ADMIN)
        self.unassigned = make_user("unassigned")
        self.report = ServiceReport.objects.create(extension=self.extension, service_date=date(2026, 9, 13))
        self.client.force_login(self.reader)
        self.cookie = f"sessionid={self.client.cookies['sessionid'].value}".encode()

    def communicator(self, user):
        communicator = WebsocketCommunicator(ReportEventsConsumer.as_asgi(), "/ws/reports/")
        communicator.scope["user"] = user
        return communicator

    async def test_only_admin_and_own_extension_receive_financial_events(self):
        own = self.communicator(self.reader)
        foreign = self.communicator(self.foreign)
        admin = self.communicator(self.admin)
        try:
            for communicator in (own, foreign, admin):
                connected, _ = await communicator.connect()
                self.assertTrue(connected)
            await database_sync_to_async(publish_report_created)(self.report)
            for communicator in (own, admin):
                event = await communicator.receive_json_from()
                self.assertEqual(event["id"], self.report.pk)
                self.assertEqual(event["currency"], "EUR")
            self.assertTrue(await foreign.receive_nothing(timeout=0.05))
        finally:
            for communicator in (own, foreign, admin):
                await communicator.disconnect()

    async def test_anonymous_unassigned_and_inactive_accounts_are_rejected(self):
        await get_user_model().objects.filter(pk=self.reader.pk).aupdate(is_active=False)
        for user in (AnonymousUser(), self.unassigned, self.reader):
            communicator = self.communicator(user)
            connected, _ = await communicator.connect()
            self.assertFalse(connected)
            await communicator.disconnect()

    async def test_reassignment_revokes_an_already_open_subscription(self):
        communicator = self.communicator(self.reader)
        try:
            self.assertTrue((await communicator.connect())[0])
            await UserProfile.objects.filter(user_id=self.reader.pk).aupdate(extension=self.other)
            await database_sync_to_async(publish_report_created)(self.report)
            self.assertEqual((await communicator.receive_output())["type"], "websocket.close")
        finally:
            await communicator.disconnect()

    async def test_suspension_revokes_an_already_open_subscription(self):
        communicator = self.communicator(self.reader)
        try:
            self.assertTrue((await communicator.connect())[0])
            await ChurchExtension.objects.filter(pk=self.extension.pk).aupdate(is_active=False)
            await database_sync_to_async(publish_report_created)(self.report)
            self.assertEqual((await communicator.receive_output())["type"], "websocket.close")
        finally:
            await communicator.disconnect()

    async def test_asgi_validates_origin_with_real_session_authentication(self):
        for origin, allowed in ((b"http://localhost", True), (b"https://untrusted.invalid", False)):
            communicator = WebsocketCommunicator(application, "/ws/reports/", headers=[
                (b"origin", origin), (b"cookie", self.cookie),
            ])
            try:
                connected, _ = await communicator.connect()
                self.assertEqual(connected, allowed)
            finally:
                await communicator.disconnect()


class FinancialMigrationTests(TransactionTestCase):
    def test_upgrade_preserves_existing_financial_values_and_leaves_unknown_metadata_null(self):
        executor = MigrationExecutor(connection)
        before = [("churches", "0001_initial"), ("reports", "0001_initial")]
        after = executor.loader.graph.leaf_nodes()
        try:
            executor.migrate(before)
            old_apps = executor.loader.project_state(before).apps
            extension = old_apps.get_model("churches", "ChurchExtension").objects.create(
                name="Historical", slug="historical", currency="USD"
            )
            old_apps.get_model("churches", "AppSetting").objects.create(pk=1, social_percentage=20)
            old_report = old_apps.get_model("reports", "ServiceReport").objects.create(
                extension=extension, service_date=date(2025, 9, 14), offering_regular=Decimal("100.50"),
                total_offerings=Decimal("100.50"), tithe_deduction=Decimal("10.05"),
                social_deduction=Decimal("5.03"), net_balance=Decimal("85.42"),
            )
            call_command("check_financial_data", stdout=StringIO())
            executor = MigrationExecutor(connection)
            executor.migrate(after)
            report = ServiceReport.objects.get(pk=old_report.pk)
            self.assertEqual(report.net_balance, Decimal("85.42"))
            self.assertEqual(report.total_deductions, Decimal("15.08"))
            self.assertIsNone(report.social_percentage_applied)
            self.assertIsNone(report.calculation_version)
            self.assertIsNone(report.currency)
            self.assertEqual(report.created_at, old_report.created_at)
        finally:
            MigrationExecutor(connection).migrate(after)
