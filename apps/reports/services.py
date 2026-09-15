from decimal import Decimal, ROUND_HALF_UP


Money = Decimal


def money(value):
    if value is None:
        value = 0
    return Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def compute_ventilation(ordinaires, orateur, dimes, actions_grace, tithe_percentage, social_percentage):
    """Calcule la ventilation des offrandes.

    Les offrandes pour l'orateur ne subissent aucun prélèvement (reste = 100%).
    Les dîmes subissent 100% de prélèvement dîme (dîme = 100%, social = 0%, reste = 0%).
    Les autres catégories (ordinaires, actions de grâce) sont soumises à :
      - dîme   = montant × tithe_percentage / 100
      - social  = montant × social_percentage / 100
      - reste   = montant − dîme − social
    """
    tithe_rate = money(tithe_percentage) / Decimal("100")
    social_rate = money(social_percentage) / Decimal("100")

    def calc(amount, apply_deductions=True):
        amount = money(max(Decimal("0"), money(amount)))
        dime   = money(amount * tithe_rate)  if apply_deductions else money(0)
        social = money(amount * social_rate) if apply_deductions else money(0)
        reste  = money(amount - dime - social)
        return {"dime": dime, "social": social, "reste": reste}

    def calc_dimes(amount):
        amount = money(max(Decimal("0"), money(amount)))
        return {"dime": amount, "social": money(0), "reste": money(0)}

    ordinaires_v    = calc(ordinaires)
    orateur_v       = calc(orateur,    apply_deductions=False)
    dimes_v         = calc_dimes(dimes)
    actions_grace_v = calc(actions_grace)

    total_dime = money(
        ordinaires_v["dime"] + dimes_v["dime"] + actions_grace_v["dime"]
    )
    total_social = money(
        ordinaires_v["social"] + dimes_v["social"] + actions_grace_v["social"]
    )
    offering_remainder = money(
        ordinaires_v["reste"]
        + orateur_v["reste"]
        + dimes_v["reste"]
        + actions_grace_v["reste"]
    )

    return {
        "ordinaires":    ordinaires_v,
        "orateur":       orateur_v,
        "dimes":         dimes_v,
        "actions_grace": actions_grace_v,
        "total_dime":    total_dime,
        "total_social":  total_social,
        "offering_remainder": offering_remainder,
    }


def convert_to_usd(amount, extension):
    """Convertit un montant de la devise locale de l'extension vers USD."""
    from apps.churches.currency_service import convert_currency, get_currency_for_extension
    from apps.churches.models import Currency

    from_currency = get_currency_for_extension(extension)
    usd = Currency.objects.filter(code="USD", is_active=True).first()
    if not from_currency or not usd:
        return money(amount)
    return money(convert_currency(amount, from_currency, usd))


def format_currency(amount, extension):
    """Formate un montant avec le symbole de la devise de l'extension."""
    from apps.churches.currency_service import get_currency_for_extension

    currency = get_currency_for_extension(extension)
    sym = currency.symbol if currency else ""
    return f"{sym} {amount:,.2f}".replace(",", " ").replace(".", ",")
