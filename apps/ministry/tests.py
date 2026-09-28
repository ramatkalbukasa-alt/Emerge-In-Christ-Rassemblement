from datetime import date
from decimal import Decimal
from io import BytesIO
from unittest.mock import patch
from zipfile import ZipFile
from xml.etree import ElementTree as ET

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import UserProfile
from apps.churches.models import ChurchExtension, Currency
from apps.reports.models import ServiceReport, Newcomer, NewConvert
from .models import Person, PersonEvent, Department, Assignment, FinancialPolicy, Allocation, Payment
from .forms import PersonForm, FilterForm, PolicyForm
from .services import remit, cancel_payment, paid, add_share, merge_people, import_legacy_person


class MinistryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usd = Currency.objects.get(code="USD")
        cls.eur = Currency.objects.get(code="EUR")
        cls.eur.usd_rate = Decimal("1.25")
        cls.eur.save()
        cls.ext = ChurchExtension.objects.create(name="Locale", slug="ministry-local", currency=cls.usd, pastor_name="Pasteur local")
        cls.other = ChurchExtension.objects.create(name="Autre", slug="ministry-other", currency=cls.usd)
        cls.admin = User.objects.create_user(username="ministry-admin")
        UserProfile.objects.create(user=cls.admin, role="admin")
        cls.user = User.objects.create_user(username="ministry-secretary")
        UserProfile.objects.create(user=cls.user, extension=cls.ext, function="secretary")
        cls.outsider = User.objects.create_user(username="ministry-other")
        UserProfile.objects.create(user=cls.outsider, extension=cls.other)
        cls.orphan = User.objects.create_user(username="ministry-orphan")
        UserProfile.objects.create(user=cls.orphan)
        cls.report = ServiceReport.objects.create(extension=cls.ext, service_date=date(2026, 1, 2),
            offering_tithe=1000, offering_regular=1000, offering_thanksgiving=1000, offering_preacher=100,
            thanksgiving_beneficiary="Prédicateur invité", preacher="Orateur")
        cls.person = Person.objects.create(extension=cls.ext, full_name="Alice Exemple", phone="+33 6 11 22", is_worker=True)
        cls.foreign = Person.objects.create(extension=cls.other, full_name="Personne confidentielle")
        cls.department = Department.objects.create(extension=cls.ext, name="Chorale")

    def login(self, user=None):
        self.client.force_login(user or self.user)

    def test_confirmed_financial_split_and_single_allocation(self):
        v = self.report.ventilation()
        self.assertEqual(v["dimes"], {"dime": Decimal(100), "social": Decimal(200), "reste": Decimal(700)})
        self.assertEqual(v["actions_grace"], {"dime": Decimal(100), "social": Decimal(300), "reste": Decimal(600)})
        self.assertEqual(v["orateur"], {"dime": Decimal(0), "social": Decimal(0), "reste": Decimal(100)})
        self.assertEqual(self.report.net_balance, Decimal(800))
        total = sum(a.amount for a in self.report.allocations.all())
        self.assertEqual(total, self.report.total_offerings)
        count = self.report.allocations.count()
        self.report.refresh_totals()
        self.assertEqual(self.report.allocations.count(), count)

    def test_frozen_rates_and_currency(self):
        FinancialPolicy.objects.create(extension=self.ext, tithe_tithe=15, tithe_social=25)
        self.report.refresh_totals()
        self.assertEqual(self.report.ventilation()["dimes"]["reste"], Decimal(700))
        second = ServiceReport.objects.create(extension=self.ext, service_date="2026-01-03", offering_tithe=1000)
        self.assertEqual(second.ventilation()["dimes"]["reste"], Decimal(600))
        self.ext.currency = self.eur
        self.ext.save()
        second.refresh_from_db()
        self.assertEqual(second.currency, self.usd)
        second.offering_tithe = 2000
        with self.assertRaises(ValidationError):
            second.save()

    def test_legacy_calculation_not_rewritten_or_allocated(self):
        old = ServiceReport.objects.create(extension=self.ext, service_date="2025-12-01", financial_version=1, offering_tithe=1000, offering_thanksgiving=1000)
        old.refresh_totals()
        self.assertEqual(old.tithe_deduction, Decimal(1100))
        self.assertEqual(old.social_deduction, Decimal(100))
        self.assertEqual(old.net_balance, Decimal(800))
        self.assertFalse(old.allocations.exists())

    def test_rates_validation_and_cent_conservation(self):
        form = PolicyForm({"extension": self.ext.pk, "regular_tithe": 90, "regular_social": 20, "tithe_tithe": 10, "tithe_social": 20, "thanks_tithe": 10, "thanks_social": 30}, user=self.admin)
        self.assertFalse(form.is_valid())
        policy = FinancialPolicy.objects.create(extension=self.ext, tithe_tithe=50, tithe_social=50)
        report = ServiceReport.objects.create(extension=self.ext, service_date="2026-01-03", offering_tithe=Decimal("0.01"))
        self.assertEqual(sum(report.ventilation()["dimes"].values()), Decimal("0.01"))
        self.assertGreaterEqual(report.ventilation()["dimes"]["reste"], 0)

    def test_partial_remittance_excess_and_cancellation(self):
        allocation = self.report.allocations.get(fund="pastor")
        data = {"date": date(2026, 1, 3), "amount": Decimal(200), "beneficiary": "Pasteur local"}
        payment = remit(self.user, allocation.pk, data)
        self.assertEqual(paid(allocation), 200)
        with self.assertRaises(ValidationError):
            remit(self.user, allocation.pk, dict(data, amount=Decimal(501)))
        with self.assertRaises(Allocation.DoesNotExist):
            remit(self.outsider, allocation.pk, data)
        with self.assertRaises(ValidationError):
            cancel_payment(self.user, payment.pk, "")
        cancel_payment(self.user, payment.pk, "Erreur de saisie")
        cancel_payment(self.user, payment.pk, "Idempotence")
        self.assertEqual(paid(allocation), 0)
        self.assertEqual(Payment.objects.count(), 1)

    def test_payment_conversion_is_frozen(self):
        allocation = self.report.allocations.get(fund="pastor")
        payment = remit(self.user, allocation.pk, {"date": date(2026, 1, 3), "amount": Decimal(100), "currency": self.eur, "beneficiary": "Pasteur local"})
        self.assertEqual(payment.amount, Decimal(125))
        self.assertEqual(payment.original_amount, Decimal(100))
        self.eur.usd_rate = 2
        self.eur.save()
        payment.refresh_from_db()
        self.assertEqual(payment.amount, 125)
        self.assertEqual(payment.exchange_rate, Decimal("1.25"))

    def test_multiple_beneficiary_shares(self):
        allocation = self.report.allocations.get(fund="beneficiary", category="actions_grace")
        first = add_share(self.user, allocation.pk, {"beneficiary": "Marie", "amount": Decimal(200)})
        add_share(self.user, allocation.pk, {"beneficiary": "Paul", "amount": Decimal(400)})
        with self.assertRaises(ValidationError):
            add_share(self.user, allocation.pk, {"beneficiary": "Extra", "amount": Decimal(1)})
        payment = remit(self.user, allocation.pk, {"date": date(2026, 1, 3), "amount": Decimal(100), "share": first, "beneficiary": ""})
        self.assertEqual(payment.beneficiary, "Marie")
        with self.assertRaises(ValidationError):
            remit(self.user, allocation.pk, {"date": date(2026, 1, 3), "amount": Decimal(101), "share": first, "beneficiary": ""})

    def test_person_two_events_counted_by_own_dates(self):
        PersonEvent.objects.create(person=self.person, extension=self.ext, kind="visit", date="2026-01-31")
        PersonEvent.objects.create(person=self.person, extension=self.ext, kind="conversion", date="2026-04-01")
        self.login()
        for kind, quarter, expected in [("visit", 1, 1), ("conversion", 1, 0), ("conversion", 2, 1)]:
            response = self.client.get(reverse("ministry:events", args=[kind]), {"period": "quarter", "year": 2026, "quarter": quarter})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.context["totals"][0][1], expected)
        self.person.is_active = False
        self.person.save()
        response = self.client.get(reverse("ministry:events", args=["visit"]))
        self.assertEqual(response.context["totals"][0][1], 1)

    def test_report_registry_link_reuse_and_source_preservation(self):
        first = Newcomer.objects.create(report=self.report, person=self.person, full_name=self.person.full_name)
        second = Newcomer.objects.create(report=self.report, person=self.person, full_name=self.person.full_name)
        NewConvert.objects.create(report=self.report, person=self.person, full_name=self.person.full_name)
        self.assertEqual(self.person.events.count(), 2)
        import_legacy_person(first, "visit", inferred=True)
        self.assertEqual(self.person.events.count(), 2)
        second.refresh_from_db()
        self.assertEqual(second.person_id, self.person.pk)

    def test_duplicate_warning_does_not_merge_homonyms(self):
        data = {"extension": self.ext.pk, "full_name": "  ALICE   Exemple ", "is_active": True}
        form = PersonForm(data, user=self.user)
        self.assertFalse(form.is_valid())
        form = PersonForm(dict(data, confirm_distinct=True), user=self.user)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertNotEqual(form.save().pk, self.person.pk)

    def test_explicit_merge_keeps_earliest_dates_and_sources(self):
        duplicate = Person.objects.create(extension=self.ext, full_name="Alice doublon")
        PersonEvent.objects.create(person=self.person, extension=self.ext, kind="visit", date="2026-02-01")
        old = Newcomer.objects.create(report=self.report, person=duplicate, full_name=duplicate.full_name)
        merge_people(self.user, duplicate.pk, self.person.pk)
        self.assertEqual(self.person.events.get(kind="visit").date, date(2026, 1, 2))
        old.refresh_from_db()
        self.assertEqual(old.person_id, self.person.pk)
        duplicate.refresh_from_db()
        self.assertFalse(duplicate.is_active)
        self.assertEqual(duplicate.merged_into_id, self.person.pk)
        with self.assertRaises(PermissionDenied):
            merge_people(self.user, self.foreign.pk, self.person.pk)

    def test_multi_department_roles_and_unique_worker_count(self):
        tech = Department.objects.create(extension=self.ext, name="Technique")
        Assignment.objects.create(extension=self.ext, person=self.person, department=self.department, role="member")
        Assignment.objects.create(extension=self.ext, person=self.person, department=tech, role="deputy")
        self.login()
        response = self.client.get(reverse("ministry:workers"))
        self.assertEqual(response.context["page"].paginator.count, 1)
        response = self.client.get(reverse("ministry:workers"), {"department": tech.pk, "role": "member"})
        self.assertEqual(response.context["page"].paginator.count, 0)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Assignment.objects.create(extension=self.ext, person=self.person, department=tech, role="head")

    def test_all_interface_routes_and_forms_render(self):
        self.login(self.admin)
        paths = [reverse("ministry:" + name) for name in ("people", "workers", "departments", "catalog", "policies", "remittances")]
        paths += [reverse("ministry:events", args=[k]) for k in ("visit", "conversion")]
        paths += [reverse("ministry:financial", args=[k]) for k in ("dimes", "ordinaires", "actions_grace", "orateur", "social", "tithe")]
        paths += [reverse("ministry:funds", args=[k]) for k in Allocation.Fund.values]
        paths += [reverse("ministry:create", args=[k]) for k in ("person", "event", "followup", "assignment", "department", "policy")]
        paths += [reverse("ministry:person_detail", args=[self.person.pk]), reverse("ministry:allocation", args=[self.report.allocations.get(fund="pastor").pk])]
        for path in paths:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)

    def test_cross_extension_and_admin_only_access(self):
        self.login()
        for format_ in ("", "pdf", "xlsx"):
            for route, key in [("financial", "tithe"), ("funds", "tithe")]:
                self.assertEqual(self.client.get(reverse("ministry:" + route, args=[key]), {"export": format_}).status_code, 403)
        self.assertEqual(self.client.get(reverse("ministry:policies")).status_code, 403)
        self.assertEqual(self.client.get(reverse("ministry:person_detail", args=[self.foreign.pk])).status_code, 404)
        response = self.client.get(reverse("ministry:people"))
        self.assertNotContains(response, self.foreign.full_name)
        response = self.client.post(reverse("ministry:create", args=["event"]), {"extension": self.other.pk, "person": self.foreign.pk, "kind": "visit", "date": "2026-01-01"})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(PersonEvent.objects.filter(person=self.foreign).exists())
        self.login(self.orphan)
        response = self.client.get(reverse("ministry:people"))
        self.assertEqual(response.context["page"].paginator.count, 0)

    def test_exports_keep_filters_and_strings_are_not_excel_formulas(self):
        dangerous_name = "=HYPERLINK(\"bad\")"
        Person.objects.create(extension=self.ext, full_name=dangerous_name)
        self.login()
        response = self.client.get(reverse("ministry:people"), {"export": "xlsx"})
        self.assertEqual(response.status_code, 200)
        with ZipFile(BytesIO(response.content)) as archive:
            for name in archive.namelist():
                ET.fromstring(archive.read(name))
            sheet = archive.read("xl/worksheets/sheet1.xml").decode()
            self.assertIn("HYPERLINK", sheet)
            self.assertNotIn("<f>", sheet)
            self.assertNotIn(self.foreign.full_name, sheet)
        response = self.client.get(reverse("ministry:financial", args=["dimes"]), {"export": "pdf", "period": "year", "year": 2026})
        self.assertTrue(response.content.startswith(b"%PDF"))

    def test_invalid_period_does_not_return_all_records(self):
        self.login()
        response = self.client.get(reverse("ministry:financial", args=["dimes"]), {"period": "custom", "start": "2026-03-01", "end": "2026-01-01"})
        self.assertEqual(response.context["page"].paginator.count, 0)
        self.assertTrue(response.context["form"].errors)

    def test_create_report_through_form_uses_registry_and_financial_rules(self):
        self.login()
        data = {"currency": self.usd.pk, "service_date": "2026-02-01", "service_type": "sunday", "thanksgiving_beneficiary": "Invité"}
        for field in ("papa_count", "maman_count", "brothers_count", "sisters_count", "children_count", "offering_regular", "offering_preacher", "offering_tithe", "offering_thanksgiving"):
            data[field] = 0
        data["offering_tithe"] = 1000
        for prefix in ("expenses", "income_lines", "newcomers", "converts"):
            data[prefix + "-TOTAL_FORMS"] = 1 if prefix in ("newcomers", "converts") else 0
            data[prefix + "-INITIAL_FORMS"] = 0
        data.update({"newcomers-0-person": self.person.pk, "converts-0-person": self.person.pk})
        with patch("apps.notifications.email_service.send_report_submitted_email"):
            response = self.client.post(reverse("reports:create"), data)
        self.assertEqual(response.status_code, 302, response.context["form"].errors if response.status_code == 200 else "")
        report = ServiceReport.objects.get(service_date="2026-02-01")
        self.assertEqual(report.allocations.get(fund="pastor").amount, 700)
        self.assertEqual(self.person.events.count(), 2)
        self.assertEqual(Person.objects.filter(full_name=self.person.full_name).count(), 1)

    def test_payment_form_post_and_duplicate_submission(self):
        self.login()
        allocation = self.report.allocations.get(fund="pastor")
        url = reverse("ministry:allocation", args=[allocation.pk])
        response = self.client.get(url)
        key = str(response.context["form"]["submission_key"].value())
        data = {"date": "2026-02-01", "amount": "100", "beneficiary": "Pasteur local", "submission_key": key}
        first = self.client.post(url, data)
        self.assertEqual(first.status_code, 302, first.context["form"].errors if first.status_code == 200 else "")
        self.assertEqual(self.client.post(url, data).status_code, 302)
        self.assertEqual(allocation.payments.count(), 1)
        self.assertEqual(paid(allocation), Decimal(100))

    def test_archive_and_role_change_preserve_assignment_history(self):
        assignment = Assignment.objects.create(extension=self.ext, person=self.person, department=self.department, role="member", start="2026-01-01")
        self.login()
        response = self.client.post(reverse("ministry:edit", args=["assignment", assignment.pk]), {
            "person": self.person.pk, "department": self.department.pk, "role": "head", "start": "2026-01-01"})
        self.assertEqual(response.status_code, 302)
        assignment.refresh_from_db()
        self.assertIsNotNone(assignment.end)
        self.assertEqual(assignment.role, "member")
        self.assertEqual(self.person.assignments.get(end=None).role, "head")
        response = self.client.post(reverse("ministry:edit", args=["person", self.person.pk]), {
            "full_name": self.person.full_name, "phone": self.person.phone, "is_worker": "on"})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(self.person.assignments.filter(end=None).exists())

    def test_catalog_is_idempotent_and_scoped(self):
        from .models import DEPARTMENTS
        self.login()
        url = reverse("ministry:catalog")
        for _ in range(2):
            self.assertEqual(self.client.post(url, {"extension": self.other.pk, "names": DEPARTMENTS[:2]}).status_code, 302)
        self.assertEqual(Department.objects.filter(extension=self.ext).count(), 3)
        self.assertFalse(Department.objects.filter(extension=self.other).exists())

    def test_extension_ledger_excludes_beneficiaries_and_includes_expenses(self):
        from apps.reports.models import Expense, ExtraIncome, ExtraExpense
        Expense.objects.create(report=self.report, number=1, amount=50, reason="Local")
        self.report.refresh_totals()
        ExtraIncome.objects.create(extension=self.ext, currency=self.usd, income_date="2026-01-04", amount=20, description="Don")
        ExtraExpense.objects.create(extension=self.ext, currency=self.usd, expense_date="2026-01-04", amount=10, description="Achat")
        self.login()
        response = self.client.get(reverse("ministry:funds", args=["extension"]))
        totals = response.context["page"].object_list[-1]["cells"]
        self.assertEqual(totals[-3:], [Decimal(820), Decimal(60), Decimal(760)])

    def test_consolidation_rounds_each_record_before_sum(self):
        self.eur.usd_rate = Decimal("1.5")
        self.eur.save()
        for day in (3, 4):
            ServiceReport.objects.create(extension=self.ext, currency=self.eur, service_date=date(2026, 3, day), offering_regular=Decimal("0.01"))
        self.login(self.admin)
        response = self.client.get(reverse("ministry:financial", args=["ordinaires"]), {"period": "month", "year": 2026, "month": 3})
        self.assertEqual(response.context["totals"][0][1], Decimal("0.04"))

    def test_negative_amounts_do_not_increase_extension_balance(self):
        import json
        from apps.reports.forms import ExpenseForm, ExtraIncomeForm
        self.assertFalse(ExpenseForm({"amount": "-10", "reason": "Erreur"}).is_valid())
        self.assertFalse(ExtraIncomeForm({"extension": self.ext.pk, "currency": self.usd.pk, "income_date": "2026-01-01", "amount": "-10", "description": "Erreur"}).is_valid())
        self.login()
        for payload in ({"offering_tithe": "-10"}, {"expenses": ["-10"]}):
            response = self.client.post(reverse("reports:financial_preview"), data=json.dumps({"extension_id": self.ext.pk, **payload}), content_type="application/json")
            self.assertEqual(response.status_code, 400)
