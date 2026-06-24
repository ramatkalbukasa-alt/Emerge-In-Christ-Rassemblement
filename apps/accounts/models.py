from django.conf import settings
from django.db import models


class UserProfile(models.Model):
    class Role(models.TextChoices):
        ADMIN = "admin", "Administrateur"
        EXTENSION = "extension", "Extension"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.EXTENSION)
    extension = models.ForeignKey(
        "churches.ChurchExtension",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="users",
    )

    def __str__(self):
        return f"{self.user.username} ({self.role})"
