from decimal import Decimal
import unicodedata
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone


def normalized(value):
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


class OwnedRecord(models.Model):
    extension = models.ForeignKey("churches.ChurchExtension", on_delete=models.PROTECT, verbose_name="Extension")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Person(OwnedRecord):
    merged_into = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT, editable=False)
    full_name = models.CharField("Nom complet", max_length=160)
    phone = models.CharField("Téléphone", max_length=60, blank=True)
    address = models.CharField("Adresse", max_length=300, blank=True)
    is_active = models.BooleanField("Fiche active", default=True)
    is_worker = models.BooleanField("Ouvrier", default=False)
    marital_status = models.CharField("État civil", max_length=20, blank=True, choices=[("single", "Célibataire"), ("married", "Marié(e)"), ("widowed", "Veuf/veuve"), ("divorced", "Divorcé(e)")])
    service_start = models.DateField("Entrée en service", null=True, blank=True)
    name_key = models.CharField(max_length=160, editable=False, db_index=True)
    phone_key = models.CharField(max_length=60, editable=False, blank=True, db_index=True)

    class Meta:
        ordering = ["full_name", "pk"]

    def save(self, *args, **kwargs):
        self.name_key = normalized(self.full_name)
        self.phone_key = "".join(c for c in self.phone if c.isdigit())
        super().save(*args, **kwargs)

    def __str__(self):
        return self.full_name


class PersonEvent(OwnedRecord):
    class Kind(models.TextChoices):
        VISIT = "visit", "Nouveau venu"
        CONVERSION = "conversion", "Âme gagnée"

    person = models.ForeignKey(Person, on_delete=models.PROTECT, related_name="events")
    kind = models.CharField("Catégorie", max_length=12, choices=Kind.choices)
    date = models.DateField("Date de l’événement")
    invited_by = models.CharField("Invité par", max_length=160, blank=True)
    follow_up_owner = models.CharField("Responsable de suivi", max_length=160, blank=True)
    report = models.ForeignKey("reports.ServiceReport", null=True, blank=True, on_delete=models.SET_NULL)
    source = models.CharField(max_length=80, unique=True, null=True, blank=True, editable=False)
    date_inferred = models.BooleanField("Date reprise du culte, à vérifier", default=False)

    class Meta:
        ordering = ["-date", "-pk"]
        constraints = [models.UniqueConstraint(fields=["person", "kind"], name="one_initial_event_per_person")]

    def clean(self):
        if self.person_id and self.person.extension_id != self.extension_id:
            raise ValidationError("La personne doit appartenir à cette extension.")


class FollowUp(OwnedRecord):
    person = models.ForeignKey(Person, on_delete=models.PROTECT, related_name="followups")
    date = models.DateField("Date", default=timezone.localdate)
    owner = models.CharField("Responsable", max_length=160)
    status = models.CharField("Statut", max_length=20, choices=[("pending", "À contacter"), ("contacted", "Contacté"), ("accompanied", "Accompagné")])
    note = models.TextField("Note de suivi", blank=True)

    class Meta:
        ordering = ["-date", "-pk"]


DEPARTMENTS = ["Bergerie (pasteurs et bergers)", "Intercession et évangélisation", "Partenaires", "Diaconat", "Chorale", "Technique", "Coordination", "Femmes gardiennes de l’histoire", "Hommes influents", "Protocole et accueil", "Jeunesse", "ECODIM"]


class Department(OwnedRecord):
    name = models.CharField("Nom du département", max_length=160)
    name_key = models.CharField(max_length=160, editable=False)
    is_active = models.BooleanField("Département actif", default=True)

    class Meta:
        ordering = ["name"]
        constraints = [models.UniqueConstraint(fields=["extension", "name_key"], name="department_name_per_extension")]

    def clean(self):
        self.name_key = normalized(self.name)

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Assignment(OwnedRecord):
    person = models.ForeignKey(Person, on_delete=models.PROTECT, related_name="assignments", verbose_name="Ouvrier")
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="assignments", verbose_name="Département")
    role = models.CharField("Rôle", max_length=12, choices=[("member", "Membre"), ("head", "Chef"), ("deputy", "Chef adjoint")])
    start = models.DateField("Début", default=timezone.localdate)
    end = models.DateField("Fin", null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["person", "department"], condition=Q(end__isnull=True), name="one_active_department_assignment")]

    def clean(self):
        if self.person_id and (self.person.extension_id != self.extension_id or not self.person.is_worker or not self.person.is_active):
            raise ValidationError("Choisissez un ouvrier actif de cette extension.")
        if self.department_id and (self.department.extension_id != self.extension_id or not self.department.is_active):
            raise ValidationError("Choisissez un département actif de cette extension.")
        if self.end and self.end < self.start:
            raise ValidationError("La fin ne peut pas précéder le début.")


def rate(label, default):
    return models.DecimalField(label, max_digits=5, decimal_places=2, default=default, validators=[MinValueValidator(0), MaxValueValidator(100)])


class FinancialPolicy(OwnedRecord):
    extension = models.OneToOneField("churches.ChurchExtension", on_delete=models.PROTECT, verbose_name="Extension")
    regular_tithe = rate("Offrandes ordinaires — dîme (%)", 10)
    regular_social = rate("Offrandes ordinaires — social (%)", 10)
    tithe_tithe = rate("Dîmes reçues — dîme des dîmes (%)", 10)
    tithe_social = rate("Dîmes reçues — social (%)", 20)
    thanks_tithe = rate("Actions de grâce — dîme (%)", 10)
    thanks_social = rate("Actions de grâce — social (%)", 30)

    def clean(self):
        for prefix in ("regular", "tithe", "thanks"):
            tithe, social = getattr(self, prefix + "_tithe"), getattr(self, prefix + "_social")
            if tithe is not None and social is not None and tithe + social > 100:
                raise ValidationError("La somme dîme + social ne peut dépasser 100 %.")

    def snapshot(self):
        return {key: str(getattr(self, key)) for key in POLICY_FIELDS}


POLICY_FIELDS = [f"{category}_{kind}" for category in ("regular", "tithe", "thanks") for kind in ("tithe", "social")]


class Allocation(OwnedRecord):
    class Fund(models.TextChoices):
        TITHE = "tithe", "Dîmes des dîmes"
        SOCIAL = "social", "Social"
        EXTENSION = "extension", "Caisse de l’extension"
        PASTOR = "pastor", "Caisse du pasteur"
        BENEFICIARY = "beneficiary", "Bénéficiaires"

    report = models.ForeignKey("reports.ServiceReport", on_delete=models.PROTECT, related_name="allocations")
    category = models.CharField(max_length=30)
    fund = models.CharField(max_length=16, choices=Fund.choices)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.ForeignKey("churches.Currency", on_delete=models.PROTECT)
    beneficiary = models.CharField("Bénéficiaire", max_length=160, blank=True)

    class Meta:
        ordering = ["-report__service_date", "pk"]
        constraints = [models.UniqueConstraint(fields=["report", "category", "fund"], name="unique_report_fund_allocation")]


class Payment(models.Model):
    submission_key = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    allocation = models.ForeignKey(Allocation, on_delete=models.PROTECT, related_name="payments")
    date = models.DateField("Date de remise", default=timezone.localdate)
    amount = models.DecimalField("Montant remis", max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    beneficiary = models.CharField("Bénéficiaire", max_length=160)
    share = models.ForeignKey("BeneficiaryShare", null=True, blank=True, on_delete=models.PROTECT, related_name="payments", verbose_name="Part du bénéficiaire")
    currency = models.ForeignKey("churches.Currency", null=True, blank=True, on_delete=models.PROTECT, verbose_name="Devise remise")
    original_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, editable=False)
    exchange_rate = models.DecimalField(max_digits=24, decimal_places=12, default=1, editable=False)
    reference = models.CharField("Référence / justificatif", max_length=200, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
    cancelled_at = models.DateTimeField(null=True, editable=False)
    cancelled_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="cancelled_remittances")
    cancellation_reason = models.CharField(max_length=300, blank=True)


class AuditEntry(models.Model):
    extension = models.ForeignKey("churches.ChurchExtension", null=True, on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=60)
    target = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)


class BeneficiaryShare(models.Model):
    allocation = models.ForeignKey(Allocation, on_delete=models.PROTECT, related_name="shares")
    beneficiary = models.CharField("Bénéficiaire", max_length=160)
    amount = models.DecimalField("Part à remettre", max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])

    class Meta:
        constraints = [models.UniqueConstraint(fields=["allocation", "beneficiary"], name="unique_allocation_beneficiary")]

    def __str__(self):
        return f"{self.beneficiary} — {self.amount}"
