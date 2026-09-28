from collections import defaultdict
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import transaction, IntegrityError
from django.db.models import Q, Count, OuterRef, Subquery
from django.http import Http404
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.churches.models import ChurchExtension, Currency
from apps.churches.currency_service import get_record_currency, convert_currency, CurrencyConversionError
from apps.reports.permissions import user_is_admin, reports_for_user
from apps.reports.models import ExtraIncome, ExtraExpense
from .models import Person, PersonEvent, Department, Assignment, FollowUp, FinancialPolicy, Allocation, Payment, BeneficiaryShare, normalized
from .forms import PersonForm, EventForm, DepartmentForm, AssignmentForm, FollowUpForm, PolicyForm, PaymentForm, FilterForm, CatalogForm, ShareForm, MergeForm
from .services import scoped, audit, available_allocations, paid, remit, cancel_payment, policy_for, add_share, merge_people, remove_share
from .exports import export_table

PERIOD_FIELDS = ["extension", "period", "year", "month", "quarter", "start", "end"]
CATEGORIES = {"ordinaires": ("Offrandes ordinaires", "offering_regular"), "dimes": ("Dîmes reçues", "offering_tithe"), "actions_grace": ("Actions de grâce", "offering_thanksgiving"), "orateur": ("Offrandes pour l’orateur", "offering_preacher")}
FORMS = {"person": (Person, PersonForm, "Personne"), "event": (PersonEvent, EventForm, "Événement d’accueil"), "department": (Department, DepartmentForm, "Département"), "assignment": (Assignment, AssignmentForm, "Affectation"), "followup": (FollowUp, FollowUpForm, "Suivi"), "policy": (FinancialPolicy, PolicyForm, "Règles financières")}


def querystring(request):
    params = request.GET.copy()
    for key in ("page", "export"):
        params.pop(key, None)
    return params.urlencode()


def period_label(form):
    if not form.is_valid():
        return "Filtres invalides"
    data = form.cleaned_data
    return f"{data.get('extension') or 'Extensions autorisées'} · {data.get('start') or 'Début'} — {data.get('end') or 'Toutes dates'}"


def table_page(request, title, headers, rows, *, form=None, subtitle="", actions=(), totals=(), note=""):
    if request.GET.get("export") and (form is None or form.is_valid()):
        export_rows = [r["cells"] for r in rows]
        for label, amount in totals:
            export_rows.append([label, amount, *[""] * (len(headers) - 2)])
        response = export_table(request.GET["export"], title, headers, export_rows, subtitle + (" · " + note if note else ""))
        if response is not None:
            return response
        raise Http404
    page = Paginator(rows, 25).get_page(request.GET.get("page"))
    return render(request, "ministry/table.html", {"title": title, "headers": headers, "page": page,
        "form": form, "subtitle": subtitle, "actions": actions, "totals": totals, "note": note,
        "query": querystring(request), "is_admin": user_is_admin(request.user)})


@login_required
def people(request, workers=False):
    form = FilterForm(request.GET, user=request.user, fields=["extension", "q", "status", "department", "role", "follow_up"])
    qs = form.apply(scoped(Person.objects.filter(merged_into=None).select_related("extension").prefetch_related("assignments__department"), request.user))
    if workers:
        qs = qs.filter(is_worker=True)
    if form.is_valid():
        data = form.cleaned_data
        if data.get("q"):
            phone = "".join(c for c in data["q"] if c.isdigit())
            match = Q(name_key__icontains=normalized(data["q"]))
            if phone:
                match |= Q(phone_key__contains=phone)
            qs = qs.filter(match)
        if data.get("status"):
            qs = qs.filter(is_active=data["status"] == "active")
        assignment_filters = {"assignments__end__isnull": True}
        if data.get("department"):
            assignment_filters["assignments__department"] = data["department"]
        if data.get("role"):
            assignment_filters["assignments__role"] = data["role"]
        if len(assignment_filters) > 1:
            qs = qs.filter(**assignment_filters).distinct()
        if data.get("follow_up"):
            latest = FollowUp.objects.filter(person=OuterRef("pk")).order_by("-date", "-pk").values("status")[:1]
            qs = qs.annotate(latest_status=Subquery(latest)).filter(latest_status=data["follow_up"])
    rows = []
    for person in qs:
        assignments = "; ".join(f"{a.department.name} : {a.get_role_display()}" for a in person.assignments.all() if a.end is None)
        rows.append({"cells": [person.full_name, person.extension.name, person.phone, person.address,
            person.get_marital_status_display(), assignments, "Actif" if person.is_active else "Archivé"],
            "url": reverse("ministry:person_detail", args=[person.pk]), "link_label": "Ouvrir"})
    return table_page(request, "Registre des ouvriers" if workers else "Registre des personnes", ["Nom", "Extension", "Téléphone", "Adresse", "État civil", "Départements et rôles", "Statut"], rows, form=form,
        subtitle=f"{len(rows)} personnes distinctes", actions=[("Ajouter un ouvrier" if workers else "Ajouter une personne", reverse("ministry:create", args=["person"]) + ("?worker=1" if workers else ""))])


@login_required
def person_detail(request, pk):
    person = get_object_or_404(scoped(Person.objects.select_related("extension"), request.user), pk=pk)
    if person.merged_into_id:
        return redirect("ministry:person_detail", pk=person.merged_into_id)
    return render(request, "ministry/person.html", {"person": person, "events": person.events.all(),
        "followups": person.followups.all(), "assignments": person.assignments.select_related("department").order_by("-start", "-pk")})


@login_required
def edit(request, kind, pk=None):
    if kind not in FORMS:
        raise Http404
    if kind == "policy" and not user_is_admin(request.user):
        raise PermissionDenied
    model, form_class, label = FORMS[kind]
    instance = get_object_or_404(scoped(model.objects.all(), request.user), pk=pk) if pk else None
    if kind == "person" and instance and instance.merged_into_id:
        return redirect("ministry:person_detail", pk=instance.merged_into_id)
    initial = {"is_worker": request.GET.get("worker") == "1"} if kind == "person" else {}
    person_id = request.GET.get("person")
    if person_id and kind in ("event", "followup", "assignment"):
        if not person_id.isdigit():
            raise Http404
        person = get_object_or_404(scoped(Person.objects.all(), request.user), pk=person_id)
        initial.update(person=person.pk, extension=person.extension_id)
    if kind == "policy" and not instance and request.GET.get("extension"):
        ext_id = request.GET["extension"]
        if not ext_id.isdigit():
            raise Http404
        ext = get_object_or_404(ChurchExtension, pk=ext_id)
        existing = FinancialPolicy.objects.filter(extension=ext).first()
        if existing:
            return redirect("ministry:edit", kind="policy", pk=existing.pk)
        initial.update(policy_for(ext), extension=ext.pk)
    form = form_class(request.POST if request.method == "POST" else None, instance=instance, initial=initial, user=request.user)
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                if instance:
                    model.objects.select_for_update().get(pk=instance.pk)
                obj = form.save(commit=False)
                if kind == "assignment" and instance and "role" in form.changed_data:
                    old = Assignment.objects.get(pk=pk)
                    if old.end is not None:
                        raise ValidationError("Une affectation terminée ne peut pas changer de rôle.")
                    Assignment.objects.filter(pk=old.pk).update(end=timezone.localdate())
                    obj.pk = None
                    obj.start = timezone.localdate()
                    obj.end = None
                obj.save()
                if kind == "person" and (not obj.is_active or not obj.is_worker):
                    obj.assignments.filter(end=None).update(end=timezone.localdate())
                if kind == "department" and not obj.is_active:
                    obj.assignments.filter(end=None).update(end=timezone.localdate())
                audit(request.user, obj, "modification" if pk else "création")
            messages.success(request, "Enregistrement effectué.")
            if kind == "person":
                return redirect("ministry:person_detail", pk=obj.pk)
            if kind in ("event", "assignment", "followup"):
                return redirect("ministry:person_detail", pk=obj.person_id)
            return redirect("ministry:policies" if kind == "policy" else "ministry:departments")
        except (ValidationError, IntegrityError) as exc:
            form.add_error(None, "; ".join(exc.messages) if isinstance(exc, ValidationError) else "Un enregistrement identique existe déjà. Actualisez la page.")
    return render(request, "ministry/form.html", {"form": form, "title": ("Modifier : " if pk else "Ajouter : ") + label,
        "matches": getattr(form, "matches", []), "note": "Les nouveaux taux s’appliquent aux prochains enregistrements. L’historique reste inchangé." if kind == "policy" else ""})


@login_required
def departments(request):
    form = FilterForm(request.GET, user=request.user, fields=["extension", "q", "status"])
    qs = form.apply(scoped(Department.objects.select_related("extension"), request.user))
    if form.is_valid():
        if form.cleaned_data.get("q"):
            qs = qs.filter(name_key__icontains=normalized(form.cleaned_data["q"]))
        if form.cleaned_data.get("status"):
            qs = qs.filter(is_active=form.cleaned_data["status"] == "active")
    qs = qs.annotate(worker_count=Count("assignments__person", distinct=True, filter=Q(assignments__end=None, assignments__person__is_active=True)))
    rows = [{"cells": [d.name, d.extension.name, d.worker_count, "Actif" if d.is_active else "Archivé"], "url": reverse("ministry:edit", args=["department", d.pk]), "link_label": "Modifier"} for d in qs]
    return table_page(request, "Départements", ["Département", "Extension", "Ouvriers actifs", "Statut"], rows, form=form,
        actions=[("Ajouter un département", reverse("ministry:create", args=["department"])), ("Choisir dans le catalogue", reverse("ministry:catalog"))])


@login_required
def catalog(request):
    form = CatalogForm(request.POST if request.method == "POST" else None, user=request.user)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            for name in form.cleaned_data["names"]:
                obj, created = Department.objects.get_or_create(extension=form.cleaned_data["extension"], name_key=normalized(name), defaults={"name": name})
                if created:
                    audit(request.user, obj, "création-catalogue")
        messages.success(request, "Les départements sélectionnés sont disponibles. Les personnalisations existantes sont conservées.")
        return redirect("ministry:departments")
    return render(request, "ministry/form.html", {"form": form, "title": "Catalogue des départements"})


@login_required
def events_report(request, kind):
    if kind not in PersonEvent.Kind.values:
        raise Http404
    form = FilterForm(request.GET, user=request.user, fields=[*PERIOD_FIELDS, "q"])
    qs = form.apply(scoped(PersonEvent.objects.filter(kind=kind, person__merged_into=None).select_related("person", "extension"), request.user), "date")
    if form.is_valid() and form.cleaned_data.get("q"):
        qs = qs.filter(person__name_key__icontains=normalized(form.cleaned_data["q"]))
    rows = [{"cells": [e.date, e.person.full_name, e.extension.name, e.person.phone, e.person.address,
        e.invited_by if kind == "visit" else e.follow_up_owner, "À vérifier" if e.date_inferred else "Confirmée"],
        "url": reverse("ministry:person_detail", args=[e.person_id]), "link_label": "Fiche"} for e in qs]
    return table_page(request, "Rapport des nouveaux venus" if kind == "visit" else "Rapport des âmes gagnées",
        ["Date", "Nom", "Extension", "Téléphone", "Adresse", "Invité par" if kind == "visit" else "Responsable", "Date reprise"], rows,
        form=form, subtitle=period_label(form), totals=[("Personnes distinctes", len(rows))],
        note="Les fiches archivées restent comptées dans leur période d’origine. Les dates reprises des anciens cultes doivent être vérifiées.",
        actions=[("Enregistrer un événement", reverse("ministry:create", args=["event"]))])


@login_required
def policies(request):
    if not user_is_admin(request.user):
        raise PermissionDenied
    rows = []
    for ext in ChurchExtension.objects.all():
        p = policy_for(ext)
        rows.append({"cells": [ext.name, p["regular_tithe"] + " / " + p["regular_social"], p["tithe_tithe"] + " / " + p["tithe_social"], p["thanks_tithe"] + " / " + p["thanks_social"]],
            "url": reverse("ministry:create", args=["policy"]) + f"?extension={ext.pk}", "link_label": "Configurer"})
    return table_page(request, "Règles financières", ["Extension", "Ordinaires : dîme / social (%)", "Dîmes : dîme / social (%)", "Actions de grâce : dîme / social (%)"], rows,
        subtitle="Prélèvements sur le brut · Offrandes pour l’orateur exemptées")


@login_required
def financial_report(request, kind="ordinaires"):
    if kind not in (*CATEGORIES, "social", "tithe"):
        raise Http404
    if kind == "tithe" and not user_is_admin(request.user):
        raise PermissionDenied
    form = FilterForm(request.GET, user=request.user, fields=PERIOD_FIELDS)
    reports = form.apply(reports_for_user(request.user).select_related("currency", "extension__currency"), "service_date")
    title = CATEGORIES[kind][0] if kind in CATEGORIES else "Social" if kind == "social" else "Dîmes des dîmes"
    headers = ["Date", "Extension", "Devise", "Brut", "Dîme", "Social", "Reste", "Règle"] if kind in CATEGORIES else ["Date", "Extension", "Devise", "Origine", "Montant", "Règle"]
    rows, totals = [], defaultdict(lambda: [Decimal(0)] * (4 if kind in CATEGORIES else 1))
    conversion_rows = []
    for report in reports:
        currency = get_record_currency(report)
        code = currency.code if currency else "Non renseignée"
        v = report.ventilation()
        version = "Historique" if report.financial_version == 1 else "Taux figés"
        if kind in CATEGORIES:
            amounts = [getattr(report, CATEGORIES[kind][1]), v[kind]["dime"], v[kind]["social"], v[kind]["reste"]]
            rows.append({"cells": [report.service_date, report.extension.name, code, *amounts, version]})
            totals[code] = [a + b for a, b in zip(totals[code], amounts)]
            conversion_rows.append((currency, amounts))
        else:
            if kind == "tithe" and report.financial_version == 1:
                continue
            for category, (label, _) in CATEGORIES.items():
                amount = v[category]["social" if kind == "social" else "dime"]
                if amount:
                    rows.append({"cells": [report.service_date, report.extension.name, code, label, amount, version]})
                    totals[code][0] += amount
                    conversion_rows.append((currency, [amount]))
    for code, amounts in sorted(totals.items()):
        rows.append({"cells": ["TOTAL", "", code, *amounts, ""] if kind in CATEGORIES else ["TOTAL", "", code, "", amounts[0], ""]})
    converted_totals = []
    target = Currency.get_default()
    note = "Montants par devise. Les anciens rapports conservent leur règle ; ils n’alimentent pas rétroactivement les nouvelles caisses."
    if user_is_admin(request.user) and target and totals:
        try:
            values = [Decimal(0)] * len(next(iter(totals.values())))
            for source, amounts in conversion_rows:
                for i, amount in enumerate(amounts):
                    values[i] += convert_currency(amount, source, target)
            labels = ["Brut", "Dîme", "Social", "Reste"] if kind in CATEGORIES else ["Montant"]
            converted_totals = [(f"{label} consolidé ({target.code})", value) for label, value in zip(labels, values)]
            note += " Consolidation aux taux de change actuellement configurés."
        except CurrencyConversionError as exc:
            note += f" Consolidation indisponible : {exc}"
    return table_page(request, "Rapport — " + title, headers, rows, form=form, subtitle=period_label(form), totals=converted_totals, note=note)


@login_required
def funds(request, fund="pastor"):
    if fund not in Allocation.Fund.values:
        raise Http404
    if fund == "tithe" and not user_is_admin(request.user):
        raise PermissionDenied
    if fund == "extension":
        return extension_ledger(request)
    form = FilterForm(request.GET, user=request.user, fields=[*PERIOD_FIELDS, "q"])
    qs = form.apply(available_allocations(request.user).filter(fund=fund).exclude(amount=0), "report__service_date")
    if form.is_valid() and form.cleaned_data.get("q"):
        qs = qs.filter(Q(beneficiary__icontains=form.cleaned_data["q"]) | Q(payments__beneficiary__icontains=form.cleaned_data["q"])).distinct()
    rows, totals = [], defaultdict(lambda: [Decimal(0), Decimal(0), Decimal(0)])
    for allocation in qs:
        amount_paid = paid(allocation)
        values = [allocation.amount, amount_paid, allocation.amount - amount_paid]
        totals[allocation.currency.code] = [a + b for a, b in zip(totals[allocation.currency.code], values)]
        rows.append({"cells": [allocation.report.service_date, allocation.extension.name, CATEGORIES[allocation.category][0], allocation.beneficiary or "À renseigner", allocation.currency.code, *values],
            "url": reverse("ministry:allocation", args=[allocation.pk]) if fund in ("pastor", "beneficiary") else "", "link_label": "Remises"})
    for code, values in sorted(totals.items()):
        rows.append({"cells": ["TOTAL", "", "", "", code, *values]})
    if fund in ("social", "tithe"):
        rows = [{"cells": [row["cells"][i] for i in (0, 1, 2, 4, 5)]} for row in rows]
        return table_page(request, dict(Allocation.Fund.choices)[fund], ["Date", "Extension", "Origine", "Devise", "Affecté"], rows,
            form=form, subtitle=period_label(form), note="Prélèvements affectés à cette caisse depuis les nouveaux rapports. Ces montants ne constituent pas une preuve de versement ni un solde bancaire.")
    return table_page(request, dict(Allocation.Fund.choices)[fund], ["Date de recette", "Extension", "Origine", "Bénéficiaire", "Devise", "Affecté", "Remis", "Reste à remettre"], rows,
        form=form, subtitle=period_label(form), note="Allocations issues des nouveaux rapports uniquement. Les remises affichées sont toutes celles des recettes sélectionnées, quelle que soit leur date. Pour le social et l’extension, il s’agit d’affectations avant dépenses, pas d’un solde bancaire.")


def extension_ledger(request):
    form = FilterForm(request.GET, user=request.user, fields=PERIOD_FIELDS)
    rows, totals = [], defaultdict(lambda: [Decimal(0), Decimal(0), Decimal(0)])
    def add(day, extension, currency, label, income, expense):
        code = currency.code if currency else "Non renseignée"
        values = [income, expense, income - expense]
        rows.append({"cells": [day, extension.name, label, code, *values]})
        totals[code] = [a + b for a, b in zip(totals[code], values)]
    reports = form.apply(reports_for_user(request.user).select_related("currency", "extension__currency"), "service_date")
    for report in reports:
        add(report.service_date, report.extension, get_record_currency(report),
            "Culte — règle historique" if report.financial_version == 1 else "Culte — net des offrandes ordinaires",
            report.net_balance + report.total_expenses, report.total_expenses)
    for model, date_field, is_expense in [(ExtraIncome, "income_date", False), (ExtraExpense, "expense_date", True)]:
        for entry in form.apply(scoped(model.objects.select_related("currency", "extension__currency"), request.user), date_field):
            add(getattr(entry, date_field), entry.extension, get_record_currency(entry), entry.description,
                Decimal(0) if is_expense else entry.amount, entry.amount if is_expense else Decimal(0))
    rows.sort(key=lambda row: row["cells"][0], reverse=True)
    for code, values in sorted(totals.items()):
        rows.append({"cells": ["TOTAL", "", "", code, *values]})
    return table_page(request, "Caisse de l’extension", ["Date", "Extension", "Origine", "Devise", "Entrées nettes", "Dépenses", "Solde de période"], rows,
        form=form, subtitle=period_label(form), note="Les nouveaux cultes alimentent cette caisse avec le net des offrandes ordinaires. Les recettes et dépenses supplémentaires sont incluses ; les anciens cultes conservent leur solde historique. Le solde de période exclut tout solde d’ouverture non enregistré.")


@login_required
def allocation_detail(request, pk):
    allocation = get_object_or_404(available_allocations(request.user), pk=pk)
    if allocation.fund not in ("pastor", "beneficiary"):
        raise PermissionDenied
    share_action = request.POST.get("action") == "share"
    form = PaymentForm(request.POST if request.method == "POST" and not share_action else None, allocation=allocation, initial={"beneficiary": allocation.beneficiary})
    share_form = ShareForm(request.POST if request.method == "POST" and share_action else None, prefix="share")
    if request.method == "POST" and share_action and share_form.is_valid():
        try:
            add_share(request.user, allocation.pk, share_form.cleaned_data)
            return redirect("ministry:allocation", pk=pk)
        except ValidationError as exc:
            share_form.add_error(None, exc)
    if request.method == "POST" and not share_action and form.is_valid():
        try:
            remit(request.user, allocation.pk, form.cleaned_data)
            messages.success(request, "Remise enregistrée.")
            return redirect("ministry:allocation", pk=pk)
        except ValidationError as exc:
            form.add_error(None, exc)
    shares = list(allocation.shares.prefetch_related("payments"))
    for share in shares:
        share.paid_amount = sum((p.amount for p in share.payments.all() if p.cancelled_at is None), Decimal(0))
        share.remaining_amount = share.amount - share.paid_amount
    return render(request, "ministry/allocation.html", {"allocation": allocation, "form": form,
        "paid": paid(allocation), "remaining": allocation.amount - paid(allocation), "payments": allocation.payments.select_related("currency").order_by("-date", "-pk"),
        "share_form": share_form, "shares": shares, "can_split": not allocation.payments.exists()})


@login_required
@require_POST
def delete_share(request, pk):
    share = get_object_or_404(BeneficiaryShare, pk=pk, allocation__in=available_allocations(request.user))
    allocation_id = share.allocation_id
    try:
        remove_share(request.user, pk)
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
    return redirect("ministry:allocation", pk=allocation_id)


@login_required
def merge_person(request, pk):
    source = get_object_or_404(scoped(Person.objects.filter(merged_into=None), request.user), pk=pk)
    form = MergeForm(request.POST if request.method == "POST" else None, source=source, user=request.user)
    if request.method == "POST" and form.is_valid():
        try:
            target = merge_people(request.user, source.pk, form.cleaned_data["target"].pk)
            messages.success(request, "Fiches rapprochées. La fiche source reste archivée et le rapprochement est tracé.")
            return redirect("ministry:person_detail", pk=target.pk)
        except ValidationError as exc:
            form.add_error(None, exc)
    return render(request, "ministry/form.html", {"form": form, "title": "Rapprocher : " + source.full_name,
        "note": "Vérifiez les coordonnées avant de confirmer. Cette action regroupe les événements, les suivis et les affectations."})


@login_required
@require_POST
def cancel_remittance(request, pk):
    payment = get_object_or_404(Payment, pk=pk, allocation__in=available_allocations(request.user))
    try:
        cancel_payment(request.user, pk, request.POST.get("reason", ""))
        messages.success(request, "Remise annulée ; l’historique est conservé.")
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
    return redirect("ministry:allocation", pk=payment.allocation_id)


@login_required
def remittances(request):
    form = FilterForm(request.GET, user=request.user, fields=[*PERIOD_FIELDS, "q"])
    allocations = available_allocations(request.user)
    if form.is_valid() and form.cleaned_data.get("extension"):
        allocations = allocations.filter(extension=form.cleaned_data["extension"])
    payments = Payment.objects.filter(allocation__in=allocations).select_related("allocation__currency", "allocation__extension", "currency").order_by("-date", "-pk")
    if not form.is_valid():
        payments = payments.none()
    else:
        data = form.cleaned_data
        if data.get("start"):
            payments = payments.filter(date__gte=data["start"])
        if data.get("end"):
            payments = payments.filter(date__lte=data["end"])
        if data.get("q"):
            payments = payments.filter(beneficiary__icontains=data["q"])
    rows = [{"cells": [p.date, p.allocation.extension.name, p.beneficiary, p.allocation.get_fund_display(), p.original_amount, p.currency.code if p.currency else p.allocation.currency.code,
        f"{p.amount} {p.allocation.currency.code}", p.reference, "Annulée" if p.cancelled_at else "Effectuée"], "url": reverse("ministry:allocation", args=[p.allocation_id]), "link_label": "Détail"} for p in payments]
    return table_page(request, "Registre des remises", ["Date", "Extension", "Bénéficiaire", "Caisse", "Montant remis", "Devise", "Imputé en caisse", "Référence", "Statut"], rows, form=form, subtitle=period_label(form))
