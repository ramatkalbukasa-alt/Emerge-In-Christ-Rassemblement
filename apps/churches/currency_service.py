from decimal import Decimal
from django.db import models

from .models import Currency


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
    
    # Si les devises sont identiques, pas de conversion
    if from_currency == to_currency:
        return amount
    
    # Récupérer les objets Currency si ce sont des codes
    if isinstance(from_currency, str):
        from_currency = Currency.objects.filter(code=from_currency, is_active=True).first()
    if isinstance(to_currency, str):
        to_currency = Currency.objects.filter(code=to_currency, is_active=True).first()
    
    # Si une devise n'existe pas, retourner le montant original
    if not from_currency or not to_currency:
        return amount
    
    # Conversion via USD comme devise pivot
    # Montant en USD = montant * taux_from_currency_to_usd
    # Montant cible = montant_en_usd / taux_to_currency_to_usd
    
    usd_amount = amount * from_currency.usd_rate
    
    if to_currency.usd_rate and to_currency.usd_rate > 0:
        converted_amount = usd_amount / to_currency.usd_rate
    else:
        converted_amount = usd_amount
    
    return converted_amount.quantize(Decimal("0.01"))


def get_currency_for_extension(extension):
    """
    Retourne la devise d'une extension.
    Utilise la devise liée si disponible, sinon essaie de créer/matcher depuis les champs legacy.
    """
    if extension.currency:
        return extension.currency
    
    # Fallback: essayer de matcher depuis les champs legacy
    if extension.currency_code_legacy:
        currency = Currency.objects.filter(code=extension.currency_code_legacy, is_active=True).first()
        if currency:
            return currency
    
    # Fallback ultime: devise par défaut (USD)
    return Currency.get_default()


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
    if isinstance(from_currency, str):
        from_currency = Currency.objects.filter(code=from_currency, is_active=True).first()
    if isinstance(to_currency, str):
        to_currency = Currency.objects.filter(code=to_currency, is_active=True).first()
    
    if not from_currency or not to_currency:
        return Decimal("1")
    
    if from_currency == to_currency:
        return Decimal("1")
    
    # Taux via USD: rate = (from_to_usd) / (to_to_usd)
    if to_currency.usd_rate and to_currency.usd_rate > 0:
        return from_currency.usd_rate / to_currency.usd_rate
    
    return Decimal("1")


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
