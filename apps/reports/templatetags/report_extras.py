from decimal import Decimal
from django import template

register = template.Library()


@register.filter
def application_admin(user):
    from apps.reports.permissions import user_is_admin
    return user_is_admin(user)


@register.filter(name="money_format")
def money_format(value):
    """
    Formate un montant numérique ou décimal avec séparateur de milliers
    et 2 décimales (ex: 1250.5 -> "1 250,50").
    """
    if value is None or value == "":
        return "0,00"
    try:
        val = Decimal(str(value))
        formatted = f"{val:,.2f}"
        # Remplacer la virgule par un espace (milliers) et le point par une virgule (décimales)
        parts = formatted.split(".")
        integer_part = parts[0].replace(",", " ")
        decimal_part = parts[1] if len(parts) > 1 else "00"
        return f"{integer_part},{decimal_part}"
    except Exception:
        return str(value)


@register.filter(name="startswith")
def startswith(text, starts):
    """
    Vérifie si la chaîne commence par le préfixe donné.
    Utile pour identifier les menus actifs par section.
    """
    if text is None or starts is None:
        return False
    return str(text).startswith(str(starts))
