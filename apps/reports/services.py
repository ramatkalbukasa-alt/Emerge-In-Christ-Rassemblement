from decimal import Decimal, ROUND_HALF_UP


Money = Decimal


def money(value):
    if value is None:
        value = 0
    return Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def compute_ventilation(ordinaires, orateur, dimes, actions_grace, social_percentage):
    social_rate = money(social_percentage) / Decimal("100")

    def calc(amount, apply_dime=True, apply_social=True):
        amount = money(max(Decimal("0"), money(amount)))
        dime = money(amount * Decimal("0.10")) if apply_dime else money(0)
        social = money(amount * social_rate) if apply_social else money(0)
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
