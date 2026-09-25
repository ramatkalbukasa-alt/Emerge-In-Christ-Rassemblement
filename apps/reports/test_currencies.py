import json
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse
from unittest.mock import patch

from apps.accounts.models import UserProfile
from apps.churches.models import Currency, ChurchExtension
from apps.churches.currency_service import convert_currency, get_exchange_rate, get_currency_for_extension, CurrencyConversionError
from apps.reports.forms import ExtraIncomeForm, ExtraExpenseForm, ServiceReportForm
from apps.reports.models import ServiceReport, ExtraIncome, ExtraExpense
from apps.reports.views import _aggregate_totals


@override_settings(SECURE_SSL_REDIRECT=False, STORAGES={
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
})
class CurrencyRegressionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Deliberately fixed test rates; these are not live market quotations.
        cls.usd, _ = Currency.objects.update_or_create(code="USD", defaults={"name": "Dollar", "symbol": "$", "usd_rate": Decimal("1"), "is_default": True})
        cls.try_, _ = Currency.objects.update_or_create(code="TRY", defaults={"name": "Livre turque", "symbol": "₺", "usd_rate": Decimal("0.025"), "is_default": False})
        cls.eur, _ = Currency.objects.update_or_create(code="EUR", defaults={"name": "Euro", "symbol": "€", "usd_rate": Decimal("1.25"), "is_default": False})
        cls.ext = ChurchExtension.objects.create(name="Goshen : Cité de Refuge", slug="goshen-test", currency=cls.try_)
        cls.admin = User.objects.create_user(username="currency-admin")
        UserProfile.objects.create(user=cls.admin, role=UserProfile.Role.ADMIN)
        cls.member = User.objects.create_user(username="currency-member")
        UserProfile.objects.create(user=cls.member, extension=cls.ext)
        cls.report = ServiceReport.objects.create(extension=cls.ext, service_date="2026-09-16", currency=cls.try_, offering_regular=4000, papa_count=32)

    def test_pivot_forward_reverse_cross_currency_and_rounding(self):
        self.assertEqual(convert_currency(4000, "TRY", "USD"), Decimal("100.00"))
        self.assertEqual(convert_currency(100, "USD", "TRY"), Decimal("4000.00"))
        self.assertEqual(convert_currency(4000, "TRY", "EUR"), Decimal("80.00"))
        self.assertEqual(convert_currency("1.005", "USD", "USD"), Decimal("1.01"))
        self.assertEqual(convert_currency(-4000, "TRY", "USD"), Decimal("-100.00"))
        self.assertEqual(convert_currency(0, "TRY", "USD"), Decimal("0.00"))
        self.assertEqual(get_exchange_rate("tl", "USD"), Decimal("0.025"))

    def test_unknown_and_invalid_rates_never_return_original_amount(self):
        for source, target in [(None, "USD"), ("XYZ", "USD"), ("TRY", None), ("XYZ", "XYZ")]:
            with self.subTest(source=source, target=target), self.assertRaises(CurrencyConversionError):
                convert_currency(4000, source, target)
        for rate in [0, -1]:
            Currency.objects.filter(pk=self.try_.pk).update(usd_rate=rate)
            with self.assertRaises(CurrencyConversionError):
                convert_currency(4000, "TRY", "USD")
            with self.assertRaises(CurrencyConversionError):
                convert_currency(100, "USD", "TRY")

    def test_currency_admin_validation(self):
        for code, rate in [("TRY", 0), ("TRY", -1), ("USD", 2)]:
            with self.subTest(code=code, rate=rate), self.assertRaises(ValidationError):
                Currency(code=code, usd_rate=rate).clean()

    def test_selecting_admin_default_clears_previous_default(self):
        from django.contrib.admin.sites import site
        from django.test import RequestFactory
        self.eur.is_default = True
        site._registry[Currency].save_model(RequestFactory().post("/admin/"), self.eur, None, True)
        self.assertEqual(Currency.get_default(), self.eur)
        self.assertEqual(Currency.objects.filter(is_default=True).count(), 1)

    def test_dashboard_converts_cards_table_and_chart(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("dashboard:home"))
        self.assertEqual(response.context["totals"]["offerings"], Decimal("100.00"))
        self.assertEqual(response.context["totals"]["balance"], Decimal("80.00"))
        self.assertEqual(response.context["recent_reports"][0].dashboard_offerings, Decimal("100.00"))
        self.assertEqual(json.loads(response.context["chart_trend_offerings"]), [100.0])
        self.assertContains(response, "TRY")
        self.report.refresh_from_db()
        self.assertEqual(self.report.total_offerings, Decimal("4000.00"))
        self.client.force_login(self.member)
        response = self.client.get(reverse("dashboard:home"))
        self.assertEqual(response.context["totals"]["offerings"], Decimal("4000.00"))
        self.assertEqual(response.context["display_currency"].code, "TRY")

    def test_legacy_report_and_legacy_tl_are_resolved_without_usd_fallback(self):
        ServiceReport.objects.filter(pk=self.report.pk).update(currency=None)
        ChurchExtension.objects.filter(pk=self.ext.pk).update(currency=None, currency_code_legacy="tl")
        self.client.force_login(self.admin)
        response = self.client.get(reverse("dashboard:home"))
        self.assertEqual(response.context["totals"]["offerings"], Decimal("100.00"))
        self.ext.refresh_from_db()
        self.ext.currency_code_legacy = "UNKNOWN"
        self.assertIsNone(get_currency_for_extension(self.ext))

    def test_mixed_currency_local_totals_and_converted_rows_agree(self):
        ServiceReport.objects.create(extension=self.ext, currency=self.usd, service_date="2026-09-17", offering_regular=100)
        ExtraIncome.objects.create(extension=self.ext, currency=self.usd, income_date="2026-09-17", amount=10, description="USD income")
        ExtraExpense.objects.create(extension=self.ext, currency=self.eur, expense_date="2026-09-17", amount=2, description="EUR expense")
        totals, _, _, reports, incomes, expenses = _aggregate_totals(ServiceReport.objects.all(), 2026, month=9, user=self.member)
        self.assertEqual(totals["total_offrandes"], Decimal("8000.00"))
        self.assertEqual(totals["total_extras"], Decimal("400.00"))
        self.assertEqual(totals["total_extra_expenses"], Decimal("100.00"))
        self.assertEqual(totals["total_reste"], Decimal("6700.00"))
        self.assertEqual(sum(r.total_offerings_disp for r in reports), totals["total_offrandes"])
        self.assertEqual(incomes[0]["amount"], Decimal("400.00"))
        self.assertEqual(expenses[0]["currency"], "₺")

    def test_monthly_quarterly_annual_respect_admin_default_currency(self):
        Currency.objects.update(is_default=False)
        Currency.objects.filter(pk=self.eur.pk).update(is_default=True)
        self.client.force_login(self.admin)
        for route, args, key in [("reports:monthly_print", [2026, 9], "totals"), ("reports:quarterly_print", [2026, 3], "quarter_totals"), ("reports:annual_print", [2026], "annual_totals")]:
            with self.subTest(route=route):
                response = self.client.get(reverse(route, args=args))
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.context["currency_code"], "EUR")
                self.assertEqual(response.context[key]["total_offrandes"], Decimal("80.00"))
                if key == "totals":
                    self.assertEqual(list(response.context["reports"])[0].total_offerings_disp, Decimal("80.00"))

    def test_detail_and_print_use_explicit_report_currency(self):
        ServiceReport.objects.filter(pk=self.report.pk).update(currency=self.eur)
        self.client.force_login(self.admin)
        for route in ["reports:detail", "reports:print"]:
            response = self.client.get(reverse(route, args=[self.report.pk]))
            self.assertEqual(response.context["report_currency"].code, "EUR")
            self.assertEqual(response.context["usd_balance"], Decimal("4000.00"))

    def test_invalid_rate_fails_visibly_instead_of_mislabeling(self):
        Currency.objects.filter(pk=self.try_.pk).update(usd_rate=0)
        self.client.force_login(self.admin)
        response = self.client.get(reverse("dashboard:home"))
        self.assertFalse(response.context["financial_available"])
        self.assertIsNone(response.context["totals"]["balance"])
        response = self.client.get(reverse("reports:monthly_print", args=[2026, 9]))
        self.assertContains(response, "Conversion indisponible", status_code=422)

    def test_new_entries_store_extension_currency_when_selection_is_empty(self):
        for form_class, date_field in [(ExtraIncomeForm, "income_date"), (ExtraExpenseForm, "expense_date")]:
            form = form_class(data={"extension": self.ext.pk, "currency": "", "amount": "40", "description": "Test", date_field: "2026-09-18"})
            self.assertTrue(form.is_valid(), form.errors)
            self.assertEqual(form.save().currency, self.try_)
        data = {"extension": self.ext.pk, "currency": "", "service_type": "week", "service_date": "2026-09-18"}
        for field in ["papa_count", "maman_count", "brothers_count", "sisters_count", "children_count", "offering_regular", "offering_preacher", "offering_tithe", "offering_thanksgiving"]:
            data[field] = 0
        form = ServiceReportForm(data=data)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save().currency, self.try_)

    def test_unassigned_member_cannot_aggregate_other_extensions_extras(self):
        unassigned = User.objects.create_user(username="currency-unassigned")
        UserProfile.objects.create(user=unassigned)
        ExtraIncome.objects.create(extension=self.ext, income_date="2026-09-17", amount=10, description="Private")
        totals, *_ = _aggregate_totals(ServiceReport.objects.none(), 2026, user=unassigned)
        self.assertEqual(totals["total_extras"], 0)

    def entry_payload(self):
        payload = {"extension": self.ext.pk, "currency": "", "service_type": "week", "service_date": "2026-09-20"}
        for field in ["papa_count", "maman_count", "brothers_count", "sisters_count", "children_count", "offering_regular", "offering_preacher", "offering_tithe", "offering_thanksgiving"]:
            payload[field] = 0
        payload["offering_regular"] = "1000"
        for prefix in ["expenses", "newcomers", "converts", "income_lines"]:
            payload[prefix + "-TOTAL_FORMS"] = "0"
            payload[prefix + "-INITIAL_FORMS"] = "0"
        payload["income_lines-TOTAL_FORMS"] = "2"
        for index, currency, amount in [(0, self.usd, "100"), (1, self.eur, "50")]:
            payload.update({f"income_lines-{index}-category": "offering_regular", f"income_lines-{index}-amount": amount, f"income_lines-{index}-currency": currency.pk})
        return payload

    @patch("apps.reports.views.publish_report_created")
    @patch("apps.notifications.email_service.send_report_submitted_email")
    def test_three_currency_report_preview_save_and_exports(self, email, publish):
        self.client.force_login(self.member)
        response = self.client.post(reverse("reports:financial_preview"), data=json.dumps({
            "extension_id": self.ext.pk, "offering_regular": "1000", "income_lines": [
                {"category": "offering_regular", "amount": "100", "currency": self.usd.pk},
                {"category": "offering_regular", "amount": "50", "currency": self.eur.pk},
            ],
        }), content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["totals"]["recettes"], "7500.00")
        response = self.client.post(reverse("reports:create"), self.entry_payload())
        self.assertEqual(response.status_code, 302)
        report = ServiceReport.objects.get(service_date="2026-09-20")
        self.assertEqual(report.currency, self.try_)
        self.assertEqual(report.total_offerings, Decimal("7500.00"))
        self.assertEqual(report.net_balance, Decimal("6000.00"))
        self.assertEqual(report.income_lines.count(), 2)
        self.assertEqual(report.income_lines.first().converted_amount, Decimal("4000.00"))
        self.assertEqual(report.income_lines.first().exchange_rate, Decimal("40"))
        Currency.objects.filter(pk=self.try_.pk).update(usd_rate=Decimal("0.05"))
        report.refresh_totals()
        report.refresh_from_db()
        self.assertEqual(report.total_offerings, Decimal("7500.00"))
        for route in ["reports:detail", "reports:print"]:
            self.assertContains(self.client.get(reverse(route, args=[report.pk])), "Entrées en devises")
        response = self.client.get(reverse("reports:export_detail", args=[report.pk, "csv"]))
        self.assertContains(response, "USD")
        self.assertContains(response, "EUR")

    def test_invalid_and_deleted_currency_lines_do_not_create_wrong_totals(self):
        self.client.force_login(self.member)
        for value in ["-10", "0", "1000000000000"]:
            payload = self.entry_payload()
            payload["income_lines-0-amount"] = value
            response = self.client.post(reverse("reports:create"), payload)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context["income_formset"].errors)
            self.assertFalse(ServiceReport.objects.filter(service_date="2026-09-20").exists())
        from apps.reports.forms import ReportIncomeLineFormSet
        payload = self.entry_payload()
        payload["income_lines-0-DELETE"] = "on"
        formset = ReportIncomeLineFormSet(data=payload, prefix="income_lines")
        self.assertTrue(formset.is_valid())
        self.assertEqual(len(formset.save(commit=False)), 1)

    def test_invalid_conversion_blocks_multicurrency_save_atomically(self):
        Currency.objects.filter(pk=self.eur.pk).update(usd_rate=0)
        self.client.force_login(self.member)
        response = self.client.post(reverse("reports:create"), self.entry_payload())
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].non_field_errors())
        self.assertFalse(ServiceReport.objects.filter(service_date="2026-09-20").exists())

    def test_register_converts_server_side_and_csv_identifies_original_currency(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("reports:export", args=["html"]))
        self.assertContains(response, "100,00 USD")
        self.assertNotContains(response, "FCFA")
        self.assertNotContains(response, "parseFloat")
        response = self.client.get(reverse("reports:export", args=["csv"]))
        self.assertContains(response, "TRY")
