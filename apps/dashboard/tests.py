import json
from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import UserProfile
from apps.churches.models import ChurchExtension, Currency
from apps.reports.models import ExtraIncome, ServiceReport


@override_settings(STORAGES={
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
})
class DashboardScopeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usd, _ = Currency.objects.update_or_create(code="USD", defaults={"name": "Dollar", "symbol": "$", "usd_rate": 1, "is_default": True})
        cls.eur, _ = Currency.objects.update_or_create(code="EUR", defaults={"name": "Euro", "symbol": "€", "usd_rate": Decimal("1.2")})
        cls.local = ChurchExtension.objects.create(name="Locale", slug="locale", currency=cls.eur)
        cls.other = ChurchExtension.objects.create(name="Autre", slug="autre", currency=cls.usd, is_active=False)
        cls.admin = User.objects.create_user(username="admin-test", first_name="Marie")
        UserProfile.objects.create(user=cls.admin, role=UserProfile.Role.ADMIN)
        cls.member = User.objects.create_user(username="locale-test")
        UserProfile.objects.create(user=cls.member, extension=cls.local)
        cls.first = ServiceReport.objects.create(extension=cls.local, service_date="2026-01-03", offering_regular=100, papa_count=3)
        cls.second = ServiceReport.objects.create(extension=cls.other, service_date="2026-09-15", currency=cls.usd, offering_regular=100, maman_count=4)
        ExtraIncome.objects.create(extension=cls.local, income_date="2025-01-01", amount=999, description="Outside dashboard scope")

    def dashboard(self, user):
        self.client.force_login(user)
        response = self.client.get(reverse("dashboard:home"))
        self.assertEqual(response.status_code, 200)
        return response

    def test_admin_converts_stored_balances_without_changing_report_scope(self):
        response = self.dashboard(self.admin)
        context = response.context
        self.assertContains(response, "Bonjour, Marie")
        self.assertEqual(context["extension_count"], 1)
        self.assertEqual(context["totals"]["reports_count"], 2)
        self.assertEqual(context["totals"]["attendance"], 7)
        self.assertEqual(context["totals"]["balance"], Decimal("176.00"))
        self.assertEqual(context["period_start"], date(2026, 1, 3))
        self.assertEqual(context["period_end"], date(2026, 9, 15))
        self.assertEqual(context["display_currency"], self.usd)
        self.assertEqual(json.loads(context["chart_trend_balances"]), [96, 80])
        self.first.refresh_from_db()
        self.assertEqual(self.first.net_balance, Decimal("80.00"))

    def test_member_scope_currency_and_action_destinations(self):
        response = self.dashboard(self.member)
        self.assertContains(response, "Bonjour, locale-test")
        self.assertEqual(response.context["totals"]["reports_count"], 1)
        self.assertEqual(response.context["totals"]["balance"], Decimal("80.00"))
        self.assertEqual(response.context["display_currency"], self.eur)
        self.assertEqual(response.context["period_end"], date(2026, 1, 3))
        self.assertNotContains(response, self.other.name)
        for route in ["reports:create", "reports:extra_income_create", "reports:extra_expense_create", "reports:list"]:
            url = reverse(route)
            self.assertContains(response, f'href="{url}"')
            self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(self.client.get(reverse("reports:detail", args=[self.second.pk])).status_code, 404)

    def test_missing_currency_never_exposes_a_partial_total(self):
        ChurchExtension.objects.filter(pk=self.local.pk).update(currency=None, currency_code_legacy="")
        response = self.dashboard(self.admin)
        self.assertFalse(response.context["financial_available"])
        self.assertIsNone(response.context["totals"]["balance"])
        self.assertEqual(json.loads(response.context["chart_trend_balances"]), [])
        self.assertContains(response, "Consolidation indisponible")

    def test_invalid_conversion_rate_is_not_used(self):
        Currency.objects.filter(pk=self.eur.pk).update(usd_rate=0)
        response = self.dashboard(self.admin)
        self.assertFalse(response.context["financial_available"])
        self.assertIsNone(response.context["totals"]["balance"])

    def test_no_extension_has_no_fabricated_count_or_period(self):
        user = User.objects.create_user(username="unassigned")
        UserProfile.objects.create(user=user)
        response = self.dashboard(user)
        self.assertEqual(response.context["extension_count"], 0)
        self.assertEqual(response.context["totals"]["reports_count"], 0)
        self.assertIsNone(response.context["period_start"])
        self.assertContains(response, "aucun rapport enregistré")

    def test_administration_rejects_extension_account(self):
        self.client.force_login(self.member)
        self.assertEqual(self.client.get(reverse("dashboard:administration")).status_code, 403)

    def test_application_admin_has_management_without_staff_escalation(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("dashboard:administration"))
        self.assertContains(response, reverse("churches:list"))
        self.assertNotContains(response, reverse("admin:auth_user_changelist"))
        self.admin.refresh_from_db()
        self.assertFalse(self.admin.is_staff)

    def test_superuser_without_profile_has_full_management(self):
        user = User.objects.create_superuser(username="super-admin", password="test-only")
        self.client.force_login(user)
        response = self.client.get(reverse("dashboard:administration"))
        self.assertContains(response, reverse("admin:auth_user_changelist"))
        self.assertContains(response, reverse("admin:churches_currency_changelist"))
        self.assertEqual(self.client.get(reverse("churches:list")).status_code, 200)
        self.assertEqual(self.client.get(reverse("dashboard:home")).context["totals"]["reports_count"], 2)

    def test_staff_only_sees_permitted_models(self):
        from django.contrib.auth.models import Permission
        user = User.objects.create_user(username="staff-limited", is_staff=True)
        user.user_permissions.add(Permission.objects.get(codename="view_currency"))
        self.client.force_login(user)
        response = self.client.get(reverse("dashboard:administration"))
        self.assertContains(response, reverse("admin:churches_currency_changelist"))
        self.assertNotContains(response, reverse("admin:auth_user_changelist"))
        self.assertNotContains(response, reverse("churches:list"))

    def test_currency_code_is_editable_only_on_creation(self):
        from django.contrib.admin.sites import site
        from django.test import RequestFactory
        model_admin = site._registry[Currency]
        request = RequestFactory().get("/admin/")
        self.assertNotIn("code", model_admin.get_readonly_fields(request))
        self.assertIn("code", model_admin.get_readonly_fields(request, self.usd))

    def test_interface_routes_render_for_admin(self):
        self.client.force_login(self.admin)
        routes = [
            ("reports:list", []), ("reports:create", []),
            ("reports:detail", [self.first.pk]), ("reports:print", [self.first.pk]),
            ("reports:extra_income_list", []), ("reports:extra_income_create", []),
            ("reports:extra_expense_list", []), ("reports:extra_expense_create", []),
            ("reports:monthly_print", [2026, 1]), ("reports:quarterly_print", [2026, 1]),
            ("reports:annual_print", [2026]), ("reports:export", ["html"]),
            ("churches:list", []), ("churches:create", []),
            ("churches:update", [self.local.slug]), ("notifications:list", []),
        ]
        for name, args in routes:
            with self.subTest(route=name):
                self.assertEqual(self.client.get(reverse(name, args=args)).status_code, 200)

    def test_anonymous_dashboard_requires_login(self):
        self.assertRedirects(self.client.get(reverse("dashboard:home")), "/login/?next=/")
