from decimal import Decimal, ROUND_HALF_UP
from django.db import models

from .models import Currency


class CurrencyConversionError(ValueError):
    """A conversion must never silently relabel an unconverted amount."""


def resolve_currency(currency):
    if isinstance(currency, str):
        code = currency.strip().upper()
        code = {"TL": "TRY"}.get(code, code)
        return Currency.objects.filter(code=code).first()
    return currency


def get_record_currency(record):
    return record.currency or get_currency_for_extension(record.extension)


def convert_currency(amount, from_currency, to_currency):
    """
    Convertit un montant d'une devise à une autre.

    Args:
        amount: Decimal - Le montant à convertir
        from_currency: Currency ou str - La devise source (objet Currency ou code ISO)
        to_currency: Currency ou str - La devise cible (objet Currency ou code ISO)

    Returns:
        Decimal - Le montant converti

    Exemple:
        >>> convert_currency(100, "EUR", "USD")
        Decimal('108.00')
    """
    if amount is None:
        return Decimal("0")

    amount = Decimal(str(amount))

    rate = get_exchange_rate(from_currency, to_currency)
    return (amount * rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def get_currency_for_extension(extension):
    """
    Retourne la devise d'une extension.
    Utilise la devise liée si disponible, sinon essaie de créer/matcher depuis les champs legacy.
    """
    if extension is None:
        return None
    if extension.currency:
        return extension.currency

    # Fallback: essayer de matcher depuis les champs legacy
    if extension.currency_code_legacy:
        currency = resolve_currency(extension.currency_code_legacy)
        if currency:
            return currency

    return None


def format_amount_with_currency(amount, currency):
    """
    Formate un montant avec le symbole de la devise.

    Args:
        amount: Decimal - Le montant à formater
        currency: Currency - L'objet Currency

    Returns:
        str - Le montant formaté (ex: "1 234,56 €")
    """
    if not currency:
        currency = Currency.get_default()

    symbol = currency.symbol if currency else "$"

    # Formatage avec espaces pour les milliers et virgule pour les décimales
    formatted = f"{amount:,.2f}".replace(",", " ").replace(".", ",")
    return f"{formatted} {symbol}"


def get_exchange_rate(from_currency, to_currency):
    """
    Retourne le taux de change entre deux devises.

    Args:
        from_currency: Currency ou str - Devise source
        to_currency: Currency ou str - Devise cible

    Returns:
        Decimal - Le taux de change (1 unité from = X unités to)
    """
    from_currency = resolve_currency(from_currency)
    to_currency = resolve_currency(to_currency)

    if not from_currency or not to_currency:
        raise CurrencyConversionError("Devise source ou cible manquante. Vérifiez la devise du rapport et de son extension.")

    for currency in (from_currency, to_currency):
        rate = Decimal(str(currency.usd_rate))
        if not rate.is_finite() or rate <= 0:
            raise CurrencyConversionError(f"Taux vers USD invalide pour {currency.code}.")
        if currency.code == "USD" and currency.usd_rate != 1:
            raise CurrencyConversionError("Le taux de la devise pivot USD doit être égal à 1.")
    if from_currency == to_currency:
        return Decimal("1")
    return Decimal(str(from_currency.usd_rate)) / Decimal(str(to_currency.usd_rate))


class CurrencyConverter:
    """
    Classe utilitaire pour les conversions de devises avec cache.
    """

    def __init__(self, base_currency=None):
        """
        Args:
            base_currency: Currency - La devise de base pour les conversions (par défaut USD)
        """
        self.base_currency = base_currency or Currency.get_default()

    def convert(self, amount, from_currency, to_currency=None):
        """
        Convertit un montant.

        Args:
            amount: Decimal - Le montant à convertir
            from_currency: Currency - La devise source
            to_currency: Currency - La devise cible (par défaut la devise de base)

        Returns:
            Decimal - Le montant converti
        """
        if to_currency is None:
            to_currency = self.base_currency

        return convert_currency(amount, from_currency, to_currency)

    def convert_to_base(self, amount, from_currency):
        """Convertit un montant vers la devise de base."""
        return self.convert(amount, from_currency, self.base_currency)

    def convert_from_base(self, amount, to_currency):
        """Convertit un montant depuis la devise de base."""
        return self.convert(amount, self.base_currency, to_currency)
