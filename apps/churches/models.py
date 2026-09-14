from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class ChurchExtension(models.Model):
    name = models.CharField(max_length=160)
    slug = models.SlugField(max_length=180, unique=True)
    color = models.CharField(max_length=7, default="#166534")
    city = models.CharField(max_length=120, blank=True)
    country = models.CharField(max_length=120, blank=True)
    address = models.TextField(blank=True)
    created_on = models.DateField(null=True, blank=True)
    pastor_name = models.CharField(max_length=160, blank=True)
    pastor_email = models.EmailField(blank=True)
    pastor_phone = models.CharField(max_length=50, blank=True)
    coordinator = models.CharField(max_length=160, blank=True)
    secretary = models.CharField(max_length=160, blank=True)
    treasurer = models.CharField(max_length=160, blank=True)
    currency = models.CharField(max_length=8, default="EUR")
    currency_symbol = models.CharField(max_length=8, default="EUR")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class AppSetting(models.Model):
    social_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, default=5,
        validators=[MinValueValidator(0), MaxValueValidator(90)],
        help_text="De 0 à 90 %, en complément de la dîme de 10 %.",
    )
    church_name = models.CharField(max_length=160, default="Emerge in Christ")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(social_percentage__gte=0, social_percentage__lte=90),
                name="social_percentage_valid",
            ),
        ]

    def __str__(self):
        return "Parametres generaux"

    @classmethod
    def current(cls):
        setting, _ = cls.objects.get_or_create(pk=1)
        return setting
