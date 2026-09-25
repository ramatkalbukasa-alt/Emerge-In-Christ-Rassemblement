from decimal import Decimal

from django.conf import settings
from django.db import models

from apps.churches.models import ChurchExtension, Currency

from .services import compute_ventilation, money


class ServiceReport(models.Model):
    class ServiceType(models.TextChoices):
        SUNDAY = "sunday", "Culte dominical"
        WEEK = "week", "Culte de semaine"
        SPECIAL = "special", "Culte spécial"

    extension = models.ForeignKey(
        ChurchExtension,
        on_delete=models.PROTECT,
        related_name="reports",
        verbose_name="Extension",
    )
    service_type = models.CharField(
        max_length=20,
        choices=ServiceType.choices,
        default=ServiceType.SUNDAY,
        verbose_name="Type de culte",
    )
    service_date = models.DateField(verbose_name="Date du culte")
    
    # Devise utilisée pour ce rapport (peut différer de la devise de l'extension)
    currency = models.ForeignKey(
        Currency,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        verbose_name="Devise",
        related_name="service_reports",
        help_text="Devise dans laquelle les montants sont exprimés",
    )
    service_time_start = models.TimeField(
        null=True, blank=True, verbose_name="Heure de début"
    )
    service_time_end = models.TimeField(
        null=True, blank=True, verbose_name="Heure de fin"
    )
    preacher = models.CharField(max_length=160, blank=True, verbose_name="Prédicateur")
    moderator = models.CharField(max_length=160, blank=True, verbose_name="Modérateur")
    interpreter = models.CharField(max_length=160, blank=True, verbose_name="Interprète")
    scripture_text = models.CharField(
        max_length=300, blank=True, verbose_name="Textes bibliques"
    )
    theme = models.CharField(max_length=220, blank=True, verbose_name="Thème")

    # ── Présence ──────────────────────────────────────────────────────────
    papa_count = models.PositiveIntegerField(default=0, verbose_name="Papa")
    maman_count = models.PositiveIntegerField(default=0, verbose_name="Maman")
    brothers_count = models.PositiveIntegerField(default=0, verbose_name="Frères")
    sisters_count = models.PositiveIntegerField(default=0, verbose_name="Sœurs")
    children_count = models.PositiveIntegerField(default=0, verbose_name="Enfants")

    # ── Offrandes ─────────────────────────────────────────────────────────
    offering_regular = models.DecimalField(
        max_digits=12, decimal_places=2, default=0, verbose_name="Offrandes ordinaires"
    )
    offering_preacher = models.DecimalField(
        max_digits=12, decimal_places=2, default=0, verbose_name="Offrandes pour l'orateur"
    )
    offering_tithe = models.DecimalField(
        max_digits=12, decimal_places=2, default=0, verbose_name="Dîmes"
    )
    offering_thanksgiving = models.DecimalField(
        max_digits=12, decimal_places=2, default=0, verbose_name="Actions de grâce"
    )

    # ── Champs calculés ───────────────────────────────────────────────────
    total_attendance = models.PositiveIntegerField(
        default=0, editable=False, verbose_name="Présence totale"
    )
    total_offerings = models.DecimalField(
        max_digits=12, decimal_places=2, default=0, editable=False,
        verbose_name="Total offrandes (brut)",
    )
    total_expenses = models.DecimalField(
        max_digits=12, decimal_places=2, default=0, editable=False,
        verbose_name="Total dépenses",
    )
    tithe_deduction = models.DecimalField(
        max_digits=12, decimal_places=2, default=0, editable=False,
        verbose_name="Prélèvement dîmes",
    )
    social_deduction = models.DecimalField(
        max_digits=12, decimal_places=2, default=0, editable=False,
        verbose_name="Prélèvement fonds social",
    )
    net_balance = models.DecimalField(
        max_digits=12, decimal_places=2, default=0, editable=False,
        verbose_name="Solde net / Reste final",
    )

    # ── Snapshot des taux au moment de la création ─────────────────────────
    # Ces champs sont figés dès le premier save et ne changent plus,
    # même si l'administrateur modifie les paramètres de l'extension.
    tithe_percentage_snapshot = models.DecimalField(
        max_digits=5, decimal_places=2, default=10, editable=False,
        verbose_name="Taux dîme utilisé (%)",
    )
    social_percentage_snapshot = models.DecimalField(
        max_digits=5, decimal_places=2, default=10, editable=False,
        verbose_name="Taux fonds social utilisé (%)",
    )

    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="submitted_reports",
        verbose_name="Soumis par",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-service_date", "-created_at"]
        verbose_name = "Rapport de culte"
        verbose_name_plural = "Rapports de culte"
        constraints = [
            models.UniqueConstraint(
                fields=["extension", "service_date", "service_type"],
                name="unique_extension_report_per_service",
            )
        ]

    def __str__(self):
        return f"{self.extension} — {self.service_date}"

    def _get_rates(self):
        """Retourne (tithe_rate, social_rate) depuis les snapshots ou l'extension.

        - Si le rapport est déjà enregistré (pk non nul) → utilise les snapshots
          figés lors de la création pour ne jamais recalculer l'historique.
        - Si c'est un nouveau rapport → lit les taux courants de l'extension.
        """
        if self.pk:  # rapport existant : on préserve les taux d'origine
            return self.tithe_percentage_snapshot, self.social_percentage_snapshot
        # Nouveau rapport : on lit les taux de l'extension
        if self.extension_id:
            try:
                ext = ChurchExtension.objects.get(pk=self.extension_id)
                return ext.tithe_percentage, ext.social_percentage
            except ChurchExtension.DoesNotExist:
                pass
        # Fallback : valeurs par défaut
        return Decimal("10"), Decimal("10")

    def recalculate(self):
        """Recalcule tous les champs agrégés sans sauvegarder."""
        tithe_pct, social_pct = self._get_rates()
        ventilation = compute_ventilation(
            self.offering_regular,
            self.offering_preacher,
            self.offering_tithe,
            self.offering_thanksgiving,
            tithe_pct,
            social_pct,
        )
        self.total_attendance = (
            self.papa_count
            + self.maman_count
            + self.brothers_count
            + self.sisters_count
            + self.children_count
        )
        self.total_offerings = money(
            self.offering_regular
            + self.offering_preacher
            + self.offering_tithe
            + self.offering_thanksgiving
        )
        self.tithe_deduction  = ventilation["total_dime"]
        self.social_deduction = ventilation["total_social"]
        self.net_balance = money(
            ventilation["offering_remainder"]
            - self.total_expenses
        )

    def save(self, *args, **kwargs):
        # Figer les taux de l'extension au premier save uniquement
        if not self.pk and self.extension_id:
            try:
                ext = ChurchExtension.objects.get(pk=self.extension_id)
                self.tithe_percentage_snapshot  = ext.tithe_percentage
                self.social_percentage_snapshot = ext.social_percentage
            except ChurchExtension.DoesNotExist:
                pass
        self.recalculate()
        super().save(*args, **kwargs)

    def refresh_totals(self):
        """Recalcule les totaux des lignes et sauvegarde. Appelé après ajout/modif de lignes."""
        self.total_expenses = money(
            sum(e.amount for e in self.expense_items.all())
        )
        self.save()


class ReportIncomeLine(models.Model):
    """Original additional receipts, included in the report's stored category totals."""
    class Category(models.TextChoices):
        REGULAR = "offering_regular", "Offrandes ordinaires"
        PREACHER = "offering_preacher", "Offrandes pour l’orateur"
        TITHE = "offering_tithe", "Dîmes"
        THANKSGIVING = "offering_thanksgiving", "Actions de grâce"

    report = models.ForeignKey(ServiceReport, on_delete=models.CASCADE, related_name="income_lines")
    category = models.CharField(max_length=30, choices=Category.choices, verbose_name="Catégorie")
    amount = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Montant reçu")
    currency = models.ForeignKey(Currency, on_delete=models.PROTECT, verbose_name="Devise reçue")
    exchange_rate = models.DecimalField(max_digits=24, decimal_places=12, editable=False)
    converted_amount = models.DecimalField(max_digits=12, decimal_places=2, editable=False)

    class Meta:
        ordering = ["pk"]
        verbose_name = "Entrée en devise"
        verbose_name_plural = "Entrées en devises"


class Expense(models.Model):
    """Ligne de dépense détaillée liée à un rapport de culte."""

    report = models.ForeignKey(
        ServiceReport,
        on_delete=models.CASCADE,
        related_name="expense_items",
        verbose_name="Rapport",
    )
    number = models.PositiveIntegerField(verbose_name="N°")
    amount = models.DecimalField(
        max_digits=12, decimal_places=2, verbose_name="Montant"
    )
    reason = models.CharField(max_length=300, verbose_name="Motif")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["number"]
        verbose_name = "Dépense"
        verbose_name_plural = "Dépenses"

    def __str__(self):
        return f"Dépense #{self.number} — {self.reason}"


class ExtraIncome(models.Model):
    """Ligne de recette supplémentaire indépendante d'un culte."""

    extension = models.ForeignKey(
        ChurchExtension,
        on_delete=models.CASCADE,
        related_name="extra_incomes",
        verbose_name="Extension",
    )
    income_date = models.DateField(verbose_name="Date")
    amount = models.DecimalField(
        max_digits=12, decimal_places=2, verbose_name="Montant"
    )
    description = models.CharField(max_length=300, verbose_name="Description")
    
    # Devise utilisée pour cette recette
    currency = models.ForeignKey(
        Currency,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        verbose_name="Devise",
        related_name="extra_incomes",
        help_text="Devise dans laquelle le montant est exprimé",
    )
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-income_date", "-created_at"]
        verbose_name = "Recette supplémentaire"
        verbose_name_plural = "Recettes supplémentaires"

    def __str__(self):
        return f"{self.amount} ({self.income_date}) — {self.description}"


class ExtraExpense(models.Model):
    """Ligne de dépense supplémentaire indépendante d'un culte."""

    extension = models.ForeignKey(
        ChurchExtension,
        on_delete=models.CASCADE,
        related_name="extra_expenses",
        verbose_name="Extension",
    )
    expense_date = models.DateField(verbose_name="Date")
    amount = models.DecimalField(
        max_digits=12, decimal_places=2, verbose_name="Montant"
    )
    description = models.CharField(max_length=300, verbose_name="Motif")
    
    # Devise utilisée pour cette dépense
    currency = models.ForeignKey(
        Currency,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        verbose_name="Devise",
        related_name="extra_expenses",
        help_text="Devise dans laquelle le montant est exprimé",
    )
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-expense_date", "-created_at"]
        verbose_name = "Dépense supplémentaire"
        verbose_name_plural = "Dépenses supplémentaires"

    def __str__(self):
        return f"{self.amount} ({self.expense_date}) — {self.description}"


class NewConvert(models.Model):
    report = models.ForeignKey(
        ServiceReport,
        on_delete=models.CASCADE,
        related_name="new_converts",
        verbose_name="Rapport",
    )
    full_name = models.CharField(max_length=160, verbose_name="Nom complet")
    phone = models.CharField(max_length=60, blank=True, verbose_name="Téléphone")
    address = models.CharField(max_length=220, blank=True, verbose_name="Adresse")
    follow_up_owner = models.CharField(
        max_length=160, blank=True, verbose_name="Responsable de suivi"
    )

    class Meta:
        verbose_name = "Nouveau converti"
        verbose_name_plural = "Nouveaux convertis"

    def __str__(self):
        return self.full_name


class Newcomer(models.Model):
    report = models.ForeignKey(
        ServiceReport,
        on_delete=models.CASCADE,
        related_name="newcomers",
        verbose_name="Rapport",
    )
    full_name = models.CharField(max_length=160, verbose_name="Nom complet")
    invited_by = models.CharField(max_length=160, blank=True, verbose_name="Invité par")

    class Meta:
        verbose_name = "Nouveau venu"
        verbose_name_plural = "Nouveaux venus"

    def __str__(self):
        return self.full_name
