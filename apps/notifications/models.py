from django.conf import settings
from django.db import models


class Notification(models.Model):
    class Type(models.TextChoices):
        REPORT_CREATED = "report_created", "Nouveau rapport"
        REPORT_WEEKLY = "report_weekly", "Récapitulatif hebdomadaire"
        REPORT_MONTHLY = "report_monthly", "Récapitulatif mensuel"
        SYSTEM = "system", "Système"

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
        verbose_name="Destinataire",
    )
    notification_type = models.CharField(
        max_length=30,
        choices=Type.choices,
        default=Type.SYSTEM,
        verbose_name="Type",
    )
    title = models.CharField(max_length=200, verbose_name="Titre")
    body = models.TextField(verbose_name="Message")
    link = models.CharField(max_length=300, blank=True, verbose_name="Lien")
    is_read = models.BooleanField(default=False, verbose_name="Lu")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Créé le")

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"

    def __str__(self):
        return f"{self.title} → {self.recipient.username}"
