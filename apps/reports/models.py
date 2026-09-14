from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.churches.models import AppSetting, ChurchExtension

from .services import compute_ventilation, money


class ServiceReport(models.Model):
    class ServiceType(models.TextChoices):
        SUNDAY = "sunday", "Culte dominical"
        WEEK = "week", "Culte de semaine"
        SPECIAL = "special", "Culte special"

    extension = models.ForeignKey(ChurchExtension, on_delete=models.PROTECT, related_name="reports")
    service_type = models.CharField(max_length=20, choices=ServiceType.choices, default=ServiceType.SUNDAY)
    service_date = models.DateField()
    preacher = models.CharField(max_length=160, blank=True)
    theme = models.CharField(max_length=220, blank=True)

    men_count = models.PositiveIntegerField(default=0)
    women_count = models.PositiveIntegerField(default=0)
    children_count = models.PositiveIntegerField(default=0)
    visitors_count = models.PositiveIntegerField(default=0)

    offering_regular = models.DecimalField(
        max_digits=12, decimal_places=2, default=0, validators=[MinValueValidator(0)]
    )
    offering_preacher = models.DecimalField(
        max_digits=12, decimal_places=2, default=0, validators=[MinValueValidator(0)]
    )
    offering_tithe = models.DecimalField(
        max_digits=12, decimal_places=2, default=0, validators=[MinValueValidator(0)]
    )
    offering_thanksgiving = models.DecimalField(
        max_digits=12, decimal_places=2, default=0, validators=[MinValueValidator(0)]
    )
    extra_income = models.DecimalField(
        max_digits=12, decimal_places=2, default=0, validators=[MinValueValidator(0)]
    )
    expenses = models.DecimalField(
        max_digits=12, decimal_places=2, default=0, validators=[MinValueValidator(0)]
    )
    social_percentage_applied = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True, editable=False,
        validators=[MinValueValidator(0), MaxValueValidator(90)],
    )
    calculation_version = models.PositiveSmallIntegerField(null=True, blank=True, editable=False)
    currency = models.CharField(max_length=8, null=True, blank=True, editable=False)

    total_attendance = models.PositiveIntegerField(default=0, editable=False)
    total_offerings = models.DecimalField(max_digits=12, decimal_places=2, default=0, editable=False)
    tithe_deduction = models.DecimalField(max_digits=12, decimal_places=2, default=0, editable=False)
    social_deduction = models.DecimalField(max_digits=12, decimal_places=2, default=0, editable=False)
    net_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0, editable=False)

    notes = models.TextField(blank=True)
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="submitted_reports",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-service_date", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["extension", "service_date", "service_type"],
                name="unique_extension_report_per_service",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    offering_regular__gte=0, offering_preacher__gte=0, offering_tithe__gte=0,
                    offering_thanksgiving__gte=0, extra_income__gte=0, expenses__gte=0,
                ),
                name="report_inputs_nonnegative",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(social_percentage_applied__isnull=True)
                    | models.Q(social_percentage_applied__gte=0, social_percentage_applied__lte=90)
                ),
                name="report_social_percentage_valid",
            ),
        ]

    def __str__(self):
        return f"{self.extension} - {self.service_date}"

    @property
    def total_deductions(self):
        return money(self.tithe_deduction + self.social_deduction)

    @property
    def currency_label(self):
        return self.currency or "Devise historique inconnue"

    @property
    def financial_inputs(self):
        return {
            "offering_regular": self.offering_regular,
            "offering_preacher": self.offering_preacher,
            "offering_tithe": self.offering_tithe,
            "offering_thanksgiving": self.offering_thanksgiving,
            "extra_income": self.extra_income,
            "expenses": self.expenses,
        }

    @property
    def attendance_inputs(self):
        return {
            "men_count": self.men_count,
            "women_count": self.women_count,
            "children_count": self.children_count,
            "visitors_count": self.visitors_count,
        }

    def _prepare_values(self, update_fields=None):
        if not self.extension_id:
            return
        previous = type(self).objects.filter(pk=self.pk).first() if self.pk else None
        finances = self.financial_inputs
        attendance = self.attendance_inputs
        if previous:
            if update_fields is not None:
                finances = previous.financial_inputs | {
                    key: value for key, value in finances.items() if key in update_fields
                }
                attendance = previous.attendance_inputs | {
                    key: value for key, value in attendance.items() if key in update_fields
                }
            self.social_percentage_applied = previous.social_percentage_applied
            self.calculation_version = previous.calculation_version
            self.currency = previous.currency
        else:
            self.social_percentage_applied = AppSetting.current().social_percentage
            self.calculation_version = 1
            self.currency = self.extension.currency.strip().upper()
            if not self.currency:
                raise ValidationError({"extension": "Renseignez la devise de cette extension."})

        if previous and finances == previous.financial_inputs:
            self.total_offerings = previous.total_offerings
            self.tithe_deduction = previous.tithe_deduction
            self.social_deduction = previous.social_deduction
            self.net_balance = previous.net_balance
        else:
            if self.calculation_version != 1 or self.social_percentage_applied is None:
                raise ValidationError(
                    "Les finances de ce rapport historique sont verrouillées : "
                    "le taux et la règle appliqués ne sont pas connus."
                )
            ventilation = compute_ventilation(
                finances["offering_regular"], finances["offering_preacher"],
                finances["offering_tithe"], finances["offering_thanksgiving"],
                self.social_percentage_applied,
            )
            self.total_offerings = money(
                money(finances["offering_regular"]) + money(finances["offering_preacher"])
                + money(finances["offering_tithe"]) + money(finances["offering_thanksgiving"])
            )
            self.tithe_deduction = ventilation["total_dime"]
            self.social_deduction = ventilation["total_social"]
            self.net_balance = money(
                ventilation["offering_remainder"] + money(finances["extra_income"]) - money(finances["expenses"])
            )
        try:
            self.total_attendance = sum(attendance.values())
        except TypeError as error:
            raise ValidationError("Les effectifs doivent être des nombres entiers.") from error
        calculated_values = {
            "total_attendance": self.total_attendance,
            "total_offerings": self.total_offerings,
            "tithe_deduction": self.tithe_deduction,
            "social_deduction": self.social_deduction,
            "net_balance": self.net_balance,
            "social_percentage_applied": self.social_percentage_applied,
            "currency": self.currency,
        }
        for name, value in calculated_values.items():
            try:
                self._meta.get_field(name).clean(value, self)
            except ValidationError as error:
                raise ValidationError(f"{name} : {', '.join(error.messages)}") from error

    def clean(self):
        super().clean()
        self._prepare_values()

    def save(self, *, force_insert=False, force_update=False, using=None, update_fields=None):
        fields = set(update_fields) if update_fields is not None else None
        if fields == set():
            return
        excluded = {
            field.name for field in self._meta.concrete_fields
            if fields is not None and field.name not in fields and field.attname not in fields
        }
        self.clean_fields(exclude=excluded)
        self._prepare_values(fields)
        self.validate_unique(exclude=excluded)
        self.validate_constraints(exclude=excluded)
        if fields is not None:
            if fields.intersection(self.financial_inputs):
                fields.update(("total_offerings", "tithe_deduction", "social_deduction", "net_balance"))
            if fields.intersection(self.attendance_inputs):
                fields.add("total_attendance")
        super().save(force_insert=force_insert, force_update=force_update, using=using, update_fields=fields)


class NewConvert(models.Model):
    report = models.ForeignKey(ServiceReport, on_delete=models.CASCADE, related_name="new_converts")
    full_name = models.CharField(max_length=160)
    phone = models.CharField(max_length=60, blank=True)
    address = models.CharField(max_length=220, blank=True)
    follow_up_owner = models.CharField(max_length=160, blank=True)

    def __str__(self):
        return self.full_name
