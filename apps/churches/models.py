from django.db import models
from django.core.exceptions import ValidationError


class Currency(models.Model):
    """Modèle pour gérer les devises supportées par le système."""
    
    code = models.CharField(max_length=3, unique=True, verbose_name="Code ISO (ex: USD)")
    name = models.CharField(max_length=50, verbose_name="Nom de la devise")
    symbol = models.CharField(max_length=5, verbose_name="Symbole (ex: $)")
    # Taux de change vers USD (1 unité = X USD)
    usd_rate = models.DecimalField(
        max_digits=14,
        decimal_places=6,
        default=1,
        verbose_name="Taux vers USD",
        help_text="1 unité de cette devise équivaut à X dollars USD",
    )
    is_active = models.BooleanField(default=True, verbose_name="Active")
    is_default = models.BooleanField(default=False, verbose_name="Devise par défaut (Admin)")
    
    class Meta:
        verbose_name = "Devise"
        verbose_name_plural = "Devises"
        ordering = ["code"]
    
    def __str__(self):
        return f"{self.code} - {self.name} ({self.symbol})"

    def clean(self):
        super().clean()
        self.code = self.code.strip().upper()
        if self.usd_rate is None or self.usd_rate <= 0:
            raise ValidationError({"usd_rate": "Le taux doit être strictement positif."})
        if self.code == "USD" and self.usd_rate != 1:
            raise ValidationError({"usd_rate": "1 USD vaut toujours 1 USD : saisissez 1."})
        if self.is_default and not self.is_active:
            raise ValidationError({"is_active": "La devise administrateur doit être active."})
    
    @classmethod
    def get_default(cls):
        """Retourne la devise par défaut (USD pour l'admin)."""
        return cls.objects.filter(is_default=True).first() or cls.objects.filter(code="USD").first()
    
    @classmethod
    def initialize_currencies(cls):
        """Initialise les devises prédéfinies si elles n'existent pas."""
        currencies_data = [
            {"code": "USD", "name": "Dollar américain", "symbol": "$", "usd_rate": 1.0, "is_default": True},
            {"code": "EUR", "name": "Euro", "symbol": "€", "usd_rate": 1.08},
            {"code": "TRY", "name": "Livre turque", "symbol": "₺", "usd_rate": 0.031},
            {"code": "CDF", "name": "Franc congolais", "symbol": "FC", "usd_rate": 0.00037},
            {"code": "GBP", "name": "Livre sterling", "symbol": "£", "usd_rate": 1.27},
            {"code": "XAF", "name": "Franc CFA (Afrique centrale)", "symbol": "FCFA", "usd_rate": 0.0016},
        ]
        
        for data in currencies_data:
            cls.objects.get_or_create(
                code=data["code"],
                defaults=data
            )


class ChurchExtension(models.Model):
    name = models.CharField(max_length=160, verbose_name="Nom de l'extension")
    slug = models.SlugField(max_length=180, unique=True)
    logo = models.ImageField(
        upload_to="logos/",
        blank=True,
        null=True,
        verbose_name="Logo officiel",
    )
    color = models.CharField(max_length=7, default="#166534", verbose_name="Couleur")
    city = models.CharField(max_length=120, blank=True, verbose_name="Ville")
    country = models.CharField(max_length=120, blank=True, verbose_name="Pays")
    address = models.TextField(blank=True, verbose_name="Adresse")
    created_on = models.DateField(null=True, blank=True, verbose_name="Date de fondation")
    pastor_name = models.CharField(max_length=160, blank=True, verbose_name="Pasteur")
    pastor_email = models.EmailField(blank=True, verbose_name="Email du pasteur")
    pastor_phone = models.CharField(max_length=50, blank=True, verbose_name="Téléphone du pasteur")
    coordinator = models.CharField(max_length=160, blank=True, verbose_name="Coordinateur")
    secretary = models.CharField(max_length=160, blank=True, verbose_name="Secrétaire")
    treasurer = models.CharField(max_length=160, blank=True, verbose_name="Trésorier")
    
    # Devise de l'extension (lié au modèle Currency)
    currency = models.ForeignKey(
        Currency,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Devise par défaut",
        related_name="extensions",
    )
    
    # Champs conservés pour compatibilité avec les données existantes
    # (seront migrés vers le modèle Currency)
    currency_code_legacy = models.CharField(max_length=8, default="EUR", verbose_name="Code devise (legacy)")
    currency_symbol_legacy = models.CharField(max_length=8, default="€", verbose_name="Symbole devise (legacy)")
    usd_exchange_rate_legacy = models.DecimalField(
        max_digits=14,
        decimal_places=6,
        default=1,
        verbose_name="Taux de change (→ USD) (legacy)",
        help_text="1 unité de la devise locale équivaut à X dollars USD",
    )
    exchange_rate_updated = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Taux mis à jour le",
    )

    # ── Paramètres financiers ────────────────────────────────────────────────
    tithe_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=10,
        verbose_name="Pourcentage dîme (%)",
        help_text="Pourcentage prélevé à titre de dîme sur les offrandes ordinaires, dîmes et actions de grâce.",
    )
    social_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=10,
        verbose_name="Pourcentage fonds social (%)",
        help_text="Pourcentage prélevé pour le fonds social sur les offrandes ordinaires, dîmes et actions de grâce.",
    )

    is_active = models.BooleanField(default=True, verbose_name="Active")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Extension"
        verbose_name_plural = "Extensions"

    def __str__(self):
        return self.name


class AppSetting(models.Model):
    social_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=5,
        verbose_name="Pourcentage fonds social (%)",
    )
    church_name = models.CharField(
        max_length=160,
        default="Emerge in Christ",
        verbose_name="Nom de la communauté",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Paramètres généraux"
        verbose_name_plural = "Paramètres généraux"

    def __str__(self):
        return "Paramètres généraux"

    @classmethod
    def current(cls):
        setting, _ = cls.objects.get_or_create(pk=1)
        return setting
