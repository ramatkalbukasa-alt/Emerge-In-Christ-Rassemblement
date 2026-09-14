from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.core.exceptions import ValidationError

Money = Decimal


def money(value):
    if value is None:
        value = 0
    try:
        amount = Decimal(value)
        if not amount.is_finite():
            raise ValidationError("Le montant doit être un nombre fini.")
        return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError) as error:
        raise ValidationError("Montant invalide.") from error


def compute_ventilation(ordinaires, orateur, dimes, actions_grace, social_percentage):
    percentage = money(social_percentage)
    if not 0 <= percentage <= 90:
        raise ValidationError("Le taux social doit être compris entre 0 et 90 %.")
    social_rate = percentage / Decimal("100")

    def calc(amount, apply_dime=True, apply_social=True):
        amount = money(amount)
        if amount < 0:
            raise ValidationError("Les offrandes ne peuvent pas être négatives.")
        dime = money(amount * Decimal("0.10")) if apply_dime else money(0)
        social = min(money(amount * social_rate), amount - dime) if apply_social else money(0)
        reste = money(amount - dime - social)
        return {"dime": dime, "social": social, "reste": reste}

    ordinaires_v = calc(ordinaires)
    orateur_v = calc(orateur, apply_dime=False, apply_social=False)
    dimes_v = calc(dimes)
    actions_grace_v = calc(actions_grace)

    total_dime = money(ordinaires_v["dime"] + dimes_v["dime"] + actions_grace_v["dime"])
    total_social = money(ordinaires_v["social"] + dimes_v["social"] + actions_grace_v["social"])
    offering_remainder = money(
        ordinaires_v["reste"] + orateur_v["reste"] + dimes_v["reste"] + actions_grace_v["reste"]
    )

    return {
        "ordinaires": ordinaires_v,
        "orateur": orateur_v,
        "dimes": dimes_v,
        "actions_grace": actions_grace_v,
        "total_dime": total_dime,
        "total_social": total_social,
        "offering_remainder": offering_remainder,
    }
