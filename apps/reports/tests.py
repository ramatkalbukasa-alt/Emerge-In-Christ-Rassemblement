from decimal import Decimal
from django.contrib.auth.models import User
from django.test import TestCase
from apps.accounts.models import UserProfile
from apps.churches.models import ChurchExtension, Currency
from apps.reports.models import ServiceReport, Expense
from apps.reports.services import compute_ventilation, money

class FinancialLogicTestCase(TestCase):
    def test_detail_preserves_decimal_amounts_in_french(self):
        import json
        import re
        from django.urls import reverse
        from django.utils.translation import override

        report = ServiceReport.objects.create(
            extension=self.extension,
            service_date="2026-09-14",
            offering_regular=Decimal("860.25"),
            offering_preacher=Decimal("12.75"),
        )
        self.client.force_login(self.admin_user)
        with override("fr"):
            response = self.client.get(reverse("reports:detail", args=[report.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_deductions"], report.tithe_deduction + report.social_deduction)
        chart = re.search(r"const financeValues = (\[.*?\]);", response.content.decode(), re.S)
        self.assertIsNotNone(chart)
        values = json.loads(chart.group(1))
        self.assertEqual(values, [860.25, 12.75, 0, 0, 0])

    def setUp(self):
        # Initialiser les devises (USD, EUR, ...)
        Currency.initialize_currencies()
        self.usd = Currency.objects.get(code="USD")
        self.eur = Currency.objects.get(code="EUR")
        # Taux déterministe pour les tests : 1 EUR = 1.2 USD
        self.eur.usd_rate = Decimal("1.2")
        self.eur.save()

        # Création d'une extension de test avec les taux par défaut (10% dîme, 10% social)
        self.extension = ChurchExtension.objects.create(
            name="Extension Test",
            slug="extension-test",
            tithe_percentage=Decimal("10"),
            social_percentage=Decimal("10"),
            currency=self.eur,
        )

        # Utilisateur admin pour les tests de consolidation
        self.admin_user = User.objects.create_user(username="admin-test", password="x")
        UserProfile.objects.create(user=self.admin_user, role=UserProfile.Role.ADMIN)

    def test_compute_ventilation_standard(self):
        """Test direct du service de ventilation avec les exemples de la consigne."""
        # Exemple 1 : Offrandes ordinaires (860)
        res = compute_ventilation(
            ordinaires=Decimal("860"),
            orateur=Decimal("0"),
            dimes=Decimal("0"),
            actions_grace=Decimal("0"),
            tithe_percentage=Decimal("10"),
            social_percentage=Decimal("10")
        )
        self.assertEqual(res["ordinaires"]["dime"], Decimal("86.00"))
        self.assertEqual(res["ordinaires"]["social"], Decimal("86.00"))
        self.assertEqual(res["ordinaires"]["reste"], Decimal("688.00"))

        # Exemple 2 : Offrandes pour Orateur (300)
        res = compute_ventilation(
            ordinaires=Decimal("0"),
            orateur=Decimal("300"),
            dimes=Decimal("0"),
            actions_grace=Decimal("0"),
            tithe_percentage=Decimal("10"),
            social_percentage=Decimal("10")
        )
        self.assertEqual(res["orateur"]["dime"], Decimal("0.00"))
        self.assertEqual(res["orateur"]["social"], Decimal("0.00"))
        self.assertEqual(res["orateur"]["reste"], Decimal("300.00"))

        # Exemple 3 : Dîmes (500)
        res = compute_ventilation(
            ordinaires=Decimal("0"),
            orateur=Decimal("0"),
            dimes=Decimal("500"),
            actions_grace=Decimal("0"),
            tithe_percentage=Decimal("10"),
            social_percentage=Decimal("10")
        )
        self.assertEqual(res["dimes"]["dime"], Decimal("500.00"))
        self.assertEqual(res["dimes"]["social"], Decimal("0.00"))
        self.assertEqual(res["dimes"]["reste"], Decimal("0.00"))

        # Exemple 4 : Actions de Grâce (95)
        res = compute_ventilation(
            ordinaires=Decimal("0"),
            orateur=Decimal("0"),
            dimes=Decimal("0"),
            actions_grace=Decimal("95"),
            tithe_percentage=Decimal("10"),
            social_percentage=Decimal("10")
        )
        self.assertEqual(res["actions_grace"]["dime"], Decimal("9.50"))
        self.assertEqual(res["actions_grace"]["social"], Decimal("9.50"))
        self.assertEqual(res["actions_grace"]["reste"], Decimal("76.00"))

        # Global test combining all of them
        res_global = compute_ventilation(
            ordinaires=Decimal("860"),
            orateur=Decimal("300"),
            dimes=Decimal("500"),
            actions_grace=Decimal("95"),
            tithe_percentage=Decimal("10"),
            social_percentage=Decimal("10")
        )
        self.assertEqual(res_global["total_dime"], Decimal("595.50"))      # 86 + 500 + 9.5
        self.assertEqual(res_global["total_social"], Decimal("95.50"))       # 86 + 0 + 9.5
        self.assertEqual(res_global["offering_remainder"], Decimal("1064.00")) # 688 + 300 + 0 + 76

    def test_service_report_recalculation_and_snapshots(self):
        """Test de la sauvegarde du rapport, des snapshots de taux, et du recalcul."""
        # Création du rapport de culte
        report = ServiceReport.objects.create(
            extension=self.extension,
            service_date="2026-06-25",
            offering_regular=Decimal("860"),
            offering_preacher=Decimal("300"),
            offering_tithe=Decimal("500"),
            offering_thanksgiving=Decimal("95")
        )

        # Ajout d'une dépense
        Expense.objects.create(report=report, number=1, amount=Decimal("950"), reason="Frais divers")
        report.refresh_totals()

        # Vérification des snapshots
        self.assertEqual(report.tithe_percentage_snapshot, Decimal("10"))
        self.assertEqual(report.social_percentage_snapshot, Decimal("10"))

        # Vérification des montants calculés sur le modèle
        self.assertEqual(report.total_offerings, Decimal("1755.00")) # 860 + 300 + 500 + 95
        self.assertEqual(report.tithe_deduction, Decimal("595.50"))
        self.assertEqual(report.social_deduction, Decimal("95.50"))
        self.assertEqual(report.total_expenses, Decimal("950.00"))
        self.assertEqual(report.net_balance, Decimal("114.00")) # 1064 - 950 = 114

        # Modification des taux configurés sur l'extension
        self.extension.tithe_percentage = Decimal("12")
        self.extension.social_percentage = Decimal("8")
        self.extension.save()

        # Si on rafraîchit ou modifie le rapport existant, les taux appliqués doivent rester les snapshots d'origine (10% / 10%)
        report.offering_regular = Decimal("860")
        report.save()
        self.assertEqual(report.tithe_percentage_snapshot, Decimal("10"))
        self.assertEqual(report.social_percentage_snapshot, Decimal("10"))
        self.assertEqual(report.tithe_deduction, Decimal("595.50"))
        self.assertEqual(report.social_deduction, Decimal("95.50"))
        self.assertEqual(report.net_balance, Decimal("114.00"))

        # Par contre, un nouveau rapport doit utiliser les nouveaux taux (12% / 8%)
        new_report = ServiceReport.objects.create(
            extension=self.extension,
            service_date="2026-06-26",
            offering_regular=Decimal("1000")
        )
        self.assertEqual(new_report.tithe_percentage_snapshot, Decimal("12"))
        self.assertEqual(new_report.social_percentage_snapshot, Decimal("8"))
        # 1000 ordinaires -> 12% dîme (120), 8% social (80), reste = 800
        self.assertEqual(new_report.tithe_deduction, Decimal("120.00"))
        self.assertEqual(new_report.social_deduction, Decimal("80.00"))
        self.assertEqual(new_report.net_balance, Decimal("800.00"))

    def test_aggregate_totals_periodic(self):
        """Test de la fonction _aggregate_totals avec filtrage et consolidation USD."""
        from apps.reports.views import _aggregate_totals
        from apps.reports.models import ExtraIncome, ExtraExpense

        # Deuxième extension en USD (taux EUR = 1.2 défini dans setUp)
        extension_usd = ChurchExtension.objects.create(
            name="Extension USD",
            slug="extension-usd",
            tithe_percentage=Decimal("10"),
            social_percentage=Decimal("10"),
            currency=self.usd,
        )

        # Rapport pour l'extension 1 (en EUR)
        r1 = ServiceReport.objects.create(
            extension=self.extension,
            service_date="2026-06-05",
            offering_regular=Decimal("100"),  # EUR
        )

        # Rapport pour l'extension 2 (en USD)
        r2 = ServiceReport.objects.create(
            extension=extension_usd,
            service_date="2026-06-10",
            offering_regular=Decimal("100"),  # USD
        )

        # Recette/dépense supplémentaires hors-culte
        ExtraIncome.objects.create(
            extension=self.extension,
            income_date="2026-06-15",
            amount=Decimal("50"),  # EUR
            description="Donation EUR"
        )
        ExtraExpense.objects.create(
            extension=extension_usd,
            expense_date="2026-06-20",
            amount=Decimal("30"),  # USD
            description="Achat matériel USD"
        )

        reports_qs = ServiceReport.objects.filter(service_date__year=2026, service_date__month=6)

        # 1. Mode Filtré (Extension 1 uniquement - EUR)
        totals_eur, selected_ext, is_consolidated, reports_filtered, extras_income, extras_expense = _aggregate_totals(
            reports_qs, year=2026, month=6, extension_id=self.extension.id
        )
        self.assertFalse(is_consolidated)
        self.assertEqual(selected_ext, self.extension)
        self.assertEqual(reports_filtered.count(), 1)
        self.assertEqual(totals_eur["total_offrandes"], Decimal("100.00"))  # 100 EUR
        self.assertEqual(totals_eur["total_extras"], Decimal("50.00"))      # 50 EUR extra
        self.assertEqual(totals_eur["total_extra_expenses"], Decimal("0.00"))
        # Reste = 80 (reste culte) + 50 (recette supp) - 0 = 130 EUR
        self.assertEqual(totals_eur["total_reste"], Decimal("130.00"))

        # 2. Mode Consolidé (Toutes les extensions - USD, requiert un admin)
        totals_consolidated, selected_ext, is_consolidated, reports_filtered, extras_income, extras_expense = _aggregate_totals(
            reports_qs, year=2026, month=6, user=self.admin_user
        )
        self.assertTrue(is_consolidated)
        self.assertIsNone(selected_ext)
        self.assertEqual(reports_filtered.count(), 2)
        
        # Consolidation en USD :
        # r1 (EUR) : 100 EUR * 1.2 = 120 USD. Dîme = 10 USD, Social = 10 USD, Reste = 100 USD (attendu)
        # r1 réel en EUR : Offrandes = 100 EUR, Dîme = 10 EUR, Social = 10 EUR, Reste = 80 EUR.
        # r1 en USD : Offrandes = 100*1.2 = 120 USD. Dîme = 10*1.2 = 12 USD. Social = 10*1.2 = 12 USD. Reste = 80*1.2 = 96 USD.
        # r2 réel en USD : Offrandes = 100 USD. Dîme = 10 USD. Social = 10 USD. Reste = 80 USD.
        # Total offrandes USD = 120 + 100 = 220 USD
        # Total dîmes USD = 12 + 10 = 22 USD
        # Total social USD = 12 + 10 = 22 USD
        # Total reste culte USD = 96 + 80 = 176 USD
        # Extra income (EUR) = 50 EUR * 1.2 = 60 USD
        # Extra expense (USD) = 30 USD
        # Reste final USD = 176 (reste culte) + 60 (extra income) - 30 (extra expense) = 206 USD
        
        self.assertEqual(totals_consolidated["total_offrandes"], Decimal("220.00"))
        self.assertEqual(totals_consolidated["total_dimes"], Decimal("22.00"))
        self.assertEqual(totals_consolidated["total_social"], Decimal("22.00"))
        self.assertEqual(totals_consolidated["total_extras"], Decimal("60.00"))
        self.assertEqual(totals_consolidated["total_extra_expenses"], Decimal("30.00"))
        self.assertEqual(totals_consolidated["total_reste"], Decimal("206.00"))
