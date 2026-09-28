from decimal import Decimal
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from apps.reports.permissions import user_is_admin, user_extension
from apps.reports.services import money
from .models import FinancialPolicy, Allocation, Payment, AuditEntry, Person, PersonEvent, BeneficiaryShare, Assignment, FollowUp


def scoped(queryset, user):
    if not user.is_authenticated or not user.is_active:
        return queryset.none()
    if user_is_admin(user):
        return queryset
    extension = user_extension(user)
    return queryset.filter(extension=extension) if extension else queryset.none()


def policy_for(extension):
    policy = FinancialPolicy.objects.filter(extension=extension).first()
    if not policy:
        policy = FinancialPolicy(extension=extension, regular_tithe=extension.tithe_percentage)
    policy.clean()
    for value in policy.snapshot().values():
        if not Decimal(value).is_finite() or not 0 <= Decimal(value) <= 100:
            raise ValidationError("Les taux doivent être compris entre 0 et 100 %.")
    return policy.snapshot()


def audit(user, obj, action):
    AuditEntry.objects.create(actor=user if user and user.is_authenticated else None,
        extension_id=getattr(obj, "extension_id", None), action=action,
        target=f"{obj._meta.label}:{obj.pk}")


def available_allocations(user):
    qs = scoped(Allocation.objects.select_related("report", "extension", "currency").prefetch_related("payments"), user)
    return qs if user_is_admin(user) else qs.exclude(fund=Allocation.Fund.TITHE)


def paid(allocation):
    return sum((p.amount for p in allocation.payments.all() if p.cancelled_at is None), Decimal("0.00"))


@transaction.atomic
def remit(user, allocation_id, data):
    allocation = available_allocations(user).select_for_update().get(pk=allocation_id)
    if allocation.fund not in (Allocation.Fund.PASTOR, Allocation.Fund.BENEFICIARY):
        raise ValidationError("Cette caisse ne correspond pas à une remise à un bénéficiaire.")
    from apps.churches.currency_service import get_exchange_rate, CurrencyConversionError
    payment = Payment(allocation=allocation, created_by=user, **data)
    previous = Payment.objects.filter(submission_key=payment.submission_key).first()
    if previous:
        if previous.allocation_id != allocation.pk or previous.created_by_id != user.pk:
            raise ValidationError("Identifiant de remise déjà utilisé.")
        return previous
    payment.currency = payment.currency or allocation.currency
    payment.original_amount = payment.amount
    try:
        payment.exchange_rate = get_exchange_rate(payment.currency, allocation.currency).quantize(Decimal("0.000000000001"))
        payment.amount = money(payment.amount * payment.exchange_rate)
    except CurrencyConversionError as exc:
        raise ValidationError(str(exc)) from exc
    shares = allocation.shares.all()
    if shares.exists():
        if shares.aggregate(total=Sum("amount"))["total"] != allocation.amount:
            raise ValidationError("Répartissez la totalité du montant entre les bénéficiaires avant la première remise.")
        if not payment.share_id or not shares.filter(pk=payment.share_id).exists():
            raise ValidationError("Sélectionnez une part appartenant à cette recette.")
        payment.beneficiary = payment.share.beneficiary
        share_paid = Payment.objects.filter(share=payment.share, cancelled_at=None).aggregate(total=Sum("amount"))["total"] or Decimal(0)
        if payment.amount > payment.share.amount - share_paid:
            raise ValidationError("Le montant dépasse la part restant à remettre à ce bénéficiaire.")
    elif payment.share_id:
        raise ValidationError("Part de bénéficiaire invalide.")
    elif allocation.beneficiary and payment.beneficiary != allocation.beneficiary:
        raise ValidationError("Respectez le bénéficiaire désigné ou répartissez d’abord la recette en parts.")
    payment.full_clean()
    if payment.date < allocation.report.service_date:
        raise ValidationError("La remise ne peut précéder la recette.")
    # Database aggregate after the allocation row lock, not a stale prefetched relation.
    total = Payment.objects.filter(allocation=allocation, cancelled_at=None).aggregate(total=Sum("amount"))["total"] or Decimal(0)
    if payment.amount > allocation.amount - total:
        raise ValidationError("Le montant dépasse le reste à remettre.")
    payment.save()
    audit(user, allocation, f"remise:{payment.pk}")
    return payment


@transaction.atomic
def add_share(user, allocation_id, data):
    allocation = available_allocations(user).select_for_update().get(pk=allocation_id)
    if allocation.fund not in ("pastor", "beneficiary"):
        raise ValidationError("Cette caisse ne permet pas de parts bénéficiaires.")
    if allocation.payments.exists():
        raise ValidationError("Définissez toutes les parts avant la première remise.")
    share = BeneficiaryShare(allocation=allocation, **data)
    share.full_clean()
    total = allocation.shares.aggregate(total=Sum("amount"))["total"] or Decimal(0)
    if total + share.amount > allocation.amount:
        raise ValidationError("La somme des parts dépasse le montant affecté.")
    share.save()
    audit(user, allocation, f"part-bénéficiaire:{share.pk}")
    return share


@transaction.atomic
def remove_share(user, share_id):
    share = BeneficiaryShare.objects.get(pk=share_id)
    allocation = available_allocations(user).select_for_update().get(pk=share.allocation_id)
    if allocation.payments.exists():
        raise ValidationError("La répartition ne peut plus être modifiée après une remise.")
    audit(user, allocation, f"suppression-part:{share.pk}")
    share.delete()


@transaction.atomic
def merge_people(user, source_id, target_id):
    if source_id == target_id:
        raise ValidationError("Choisissez deux fiches différentes.")
    people = {p.pk: p for p in scoped(Person.objects.all(), user).select_for_update().filter(pk__in=[source_id, target_id]).order_by("pk")}
    if len(people) != 2:
        raise PermissionDenied
    source, target = people[source_id], people[target_id]
    if source.extension_id != target.extension_id or source.merged_into_id or target.merged_into_id:
        raise ValidationError("Choisissez deux fiches non fusionnées de la même extension.")
    for event in source.events.all():
        existing = target.events.filter(kind=event.kind).first()
        if existing:
            # The user explicitly confirms that these are the same person. Keep earliest event.
            if event.date < existing.date:
                existing.date, existing.date_inferred = event.date, event.date_inferred
                existing.report, existing.extension = event.report, event.extension
            existing.invited_by = existing.invited_by or event.invited_by
            existing.follow_up_owner = existing.follow_up_owner or event.follow_up_owner
            existing.save()
            # Keep the source event on the archived duplicate as provenance.
            # Reporting excludes merged source identities, not ordinary archives.
        else:
            event.person = target
            event.save()
    for assignment in source.assignments.all():
        if assignment.end is None and target.assignments.filter(department=assignment.department, end=None).exists():
            raise ValidationError("Terminez l’une des affectations en double dans le département avant la fusion.")
        assignment.person = target
        assignment.save()
    FollowUp.objects.filter(person=source).update(person=target)
    from apps.reports.models import Newcomer, NewConvert
    for model in (Newcomer, NewConvert):
        model.objects.filter(person=source).update(person=target)
    target.phone, target.address = target.phone or source.phone, target.address or source.address
    target.is_worker = target.is_worker or source.is_worker
    target.marital_status = target.marital_status or source.marital_status
    target.service_start = target.service_start or source.service_start
    target.save()
    source.is_active, source.merged_into = False, target
    source.save()
    audit(user, target, f"fusion-personne:{source.pk}")
    return target


@transaction.atomic
def cancel_payment(user, payment_id, reason):
    original = Payment.objects.select_related("allocation").get(pk=payment_id)
    allocation = available_allocations(user).select_for_update().get(pk=original.allocation_id)
    payment = Payment.objects.select_for_update().get(pk=payment_id)
    if not reason.strip():
        raise ValidationError("Indiquez le motif de l’annulation.")
    if payment.cancelled_at is None:
        payment.cancelled_at = timezone.now()
        payment.cancelled_by = user
        payment.cancellation_reason = reason.strip()[:300]
        payment.save()
        audit(user, allocation, f"annulation-remise:{payment.pk}")


def sync_allocations(report):
    if report.financial_version < 2:
        return
    from apps.churches.currency_service import get_record_currency
    currency = get_record_currency(report)
    if not currency:
        raise ValidationError("Une devise est requise pour alimenter les caisses.")
    ventilation = report.ventilation()
    created_any = False
    for category, destination, beneficiary in [
        ("ordinaires", "extension", ""), ("dimes", "pastor", report.extension.pastor_name),
        ("actions_grace", "beneficiary", report.thanksgiving_beneficiary),
        ("orateur", "beneficiary", report.preacher),
    ]:
        for part, fund in [("dime", "tithe"), ("social", "social"), ("reste", destination)]:
            amount = ventilation[category][part]
            _, created = Allocation.objects.get_or_create(report=report, category=category, fund=fund,
                defaults={"extension": report.extension, "currency": currency, "amount": amount,
                          "beneficiary": beneficiary if part == "reste" else ""})
            created_any |= created
    if created_any:
        audit(report.submitted_by, report, "création-allocations")


@transaction.atomic
def import_legacy_person(record, kind, inferred=False):
    source = f"{record._meta.label}:{record.pk}"
    existing = PersonEvent.objects.filter(source=source).first()
    if existing:
        return existing
    person = record.person if record.person_id else Person.objects.create(
        extension=record.report.extension, full_name=record.full_name,
        phone=getattr(record, "phone", ""), address=getattr(record, "address", ""))
    if person.extension_id != record.report.extension_id:
        raise ValidationError("La personne appartient à une autre extension.")
    record.__class__.objects.filter(pk=record.pk).update(person=person)
    event, _ = PersonEvent.objects.get_or_create(person=person, kind=kind, defaults={
        "extension": record.report.extension, "date": record.report.service_date,
        "report": record.report, "source": source, "date_inferred": inferred,
        "invited_by": getattr(record, "invited_by", ""), "follow_up_owner": getattr(record, "follow_up_owner", "")})
    return event
