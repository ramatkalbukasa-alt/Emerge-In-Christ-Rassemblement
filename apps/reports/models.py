from decimal import Decimal

from django.conf import settings
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

    offering_regular = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    offering_preacher = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    offering_tithe = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    offering_thanksgiving = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    extra_income = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    expenses = models.DecimalField(max_digits=12, decimal_places=2, default=0)

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
            )
        ]

    def __str__(self):
        return f"{self.extension} - {self.service_date}"

    def save(self, *args, **kwargs):
        setting = AppSetting.current()
        ventilation = compute_ventilation(
            self.offering_regular,
            self.offering_preacher,
            self.offering_tithe,
            self.offering_thanksgiving,
            setting.social_percentage,
        )
        self.total_attendance = self.men_count + self.women_count + self.children_count + self.visitors_count
        self.total_offerings = money(
            self.offering_regular + self.offering_preacher + self.offering_tithe + self.offering_thanksgiving
        )
        self.tithe_deduction = ventilation["total_dime"]
        self.social_deduction = ventilation["total_social"]
        self.net_balance = money(ventilation["offering_remainder"] + self.extra_income - self.expenses)
        super().save(*args, **kwargs)


class NewConvert(models.Model):
    report = models.ForeignKey(ServiceReport, on_delete=models.CASCADE, related_name="new_converts")
    full_name = models.CharField(max_length=160)
    phone = models.CharField(max_length=60, blank=True)
    address = models.CharField(max_length=220, blank=True)
    follow_up_owner = models.CharField(max_length=160, blank=True)

    def __str__(self):
        return self.full_name
