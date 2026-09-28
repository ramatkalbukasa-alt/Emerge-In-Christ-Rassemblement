import calendar
import uuid
from datetime import date

from django import forms
from django.db.models import Q
from django.utils import timezone
from apps.churches.models import ChurchExtension
from apps.reports.permissions import user_is_admin, user_extension
from .models import Person, PersonEvent, Department, Assignment, FollowUp, FinancialPolicy, Payment, BeneficiaryShare, POLICY_FIELDS, DEPARTMENTS, normalized
from .services import scoped


def style(form):
    for field in form.fields.values():
        if not isinstance(field.widget, (forms.CheckboxInput, forms.CheckboxSelectMultiple)):
            field.widget.attrs.setdefault("class", "form-control")
        if isinstance(field, forms.DateField):
            field.widget = forms.DateInput(format="%Y-%m-%d", attrs={"type": "date", "class": "form-control"})


class OwnedForm(forms.ModelForm):
    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        extensions = ChurchExtension.objects.all()
        if not user_is_admin(user):
            ext = user_extension(user)
            extensions = extensions.filter(pk=ext.pk) if ext else extensions.none()
            self.fields["extension"].disabled = True
            self.initial["extension"] = ext
        if self.instance.pk:
            self.fields["extension"].disabled = True
            for key in ("person", "department", "kind"):
                if key in self.fields:
                    self.fields[key].disabled = True
        self.fields["extension"].queryset = extensions
        ext_id = self.instance.extension_id or (self.data.get("extension") if self.is_bound and user_is_admin(user) else self.initial.get("extension"))
        if hasattr(ext_id, "pk"):
            ext_id = ext_id.pk
        for name in ("person", "department"):
            if name in self.fields:
                qs = scoped(self.fields[name].queryset, user)
                if ext_id:
                    qs = qs.filter(extension_id=ext_id) if str(ext_id).isdigit() else qs.none()
                self.fields[name].queryset = qs
        style(self)


class PersonForm(OwnedForm):
    confirm_distinct = forms.BooleanField(required=False, label="J’ai vérifié les correspondances : il s’agit d’une autre personne.")

    class Meta:
        model = Person
        fields = ["extension", "full_name", "phone", "address", "is_worker", "marital_status", "service_start", "is_active"]

    def clean(self):
        data = super().clean()
        name = normalized(data.get("full_name", ""))
        phone = "".join(c for c in data.get("phone", "") if c.isdigit())
        condition = Q(name_key=name)
        if phone:
            condition |= Q(phone_key=phone)
        self.matches = scoped(Person.objects.filter(merged_into=None), self.user).filter(condition).exclude(pk=self.instance.pk)
        if data.get("extension"):
            self.matches = self.matches.filter(extension=data["extension"])
        if self.matches.exists() and not data.get("confirm_distinct"):
            raise forms.ValidationError("Une fiche similaire existe. Consultez les correspondances ou confirmez qu’il s’agit d’une autre personne.")
        return data


class EventForm(OwnedForm):
    class Meta:
        model = PersonEvent
        fields = ["extension", "person", "kind", "date", "invited_by", "follow_up_owner", "date_inferred"]


class FollowUpForm(OwnedForm):
    class Meta:
        model = FollowUp
        fields = ["extension", "person", "date", "owner", "status", "note"]
        widgets = {"note": forms.Textarea(attrs={"rows": 4})}

    def clean(self):
        data = super().clean()
        if data.get("person") and data.get("extension") and data["person"].extension_id != data["extension"].pk:
            raise forms.ValidationError("La personne doit appartenir à cette extension.")
        return data


class DepartmentForm(OwnedForm):
    class Meta:
        model = Department
        fields = ["extension", "name", "is_active"]


class AssignmentForm(OwnedForm):
    class Meta:
        model = Assignment
        fields = ["extension", "person", "department", "role", "start", "end"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["person"].queryset = self.fields["person"].queryset.filter(is_worker=True, is_active=True)
        self.fields["department"].queryset = self.fields["department"].queryset.filter(is_active=True)


class PolicyForm(OwnedForm):
    class Meta:
        model = FinancialPolicy
        fields = ["extension", *POLICY_FIELDS]


class PaymentForm(forms.ModelForm):
    submission_key = forms.UUIDField(initial=uuid.uuid4, widget=forms.HiddenInput)
    class Meta:
        model = Payment
        fields = ["date", "amount", "currency", "share", "beneficiary", "reference"]

    def __init__(self, *args, allocation, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["share"].queryset = allocation.shares.all()
        self.fields["currency"].empty_label = f"Devise de la caisse ({allocation.currency.code})"
        self.fields["currency"].queryset = self.fields["currency"].queryset.filter(is_active=True)
        if allocation.shares.exists():
            self.fields["share"].required = True
            self.fields["beneficiary"].required = False
        else:
            self.fields.pop("share")
        style(self)


class ShareForm(forms.ModelForm):
    class Meta:
        model = BeneficiaryShare
        fields = ["beneficiary", "amount"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style(self)


class MergeForm(forms.Form):
    target = forms.ModelChoiceField(label="Fiche à conserver", queryset=Person.objects.none())
    confirm = forms.BooleanField(label="Je confirme qu’il s’agit de la même personne. Les premières dates connues seront conservées.")

    def __init__(self, *args, source, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["target"].queryset = scoped(Person.objects.filter(extension=source.extension, merged_into=None, is_active=True), user).exclude(pk=source.pk)
        style(self)


class FilterForm(forms.Form):
    extension = forms.ModelChoiceField(label="Extension", queryset=ChurchExtension.objects.none(), required=False, empty_label="Toutes les extensions autorisées")
    q = forms.CharField(label="Rechercher", required=False, max_length=160)
    period = forms.ChoiceField(label="Période", required=False, choices=[("", "Toutes les dates"), ("month", "Mois"), ("quarter", "Trimestre"), ("year", "Année"), ("custom", "Dates personnalisées")])
    year = forms.IntegerField(label="Année", required=False, min_value=1900, max_value=9998)
    month = forms.TypedChoiceField(label="Mois", required=False, coerce=int, choices=[("", "—"), *[(i, label) for i, label in enumerate(["Janvier", "Février", "Mars", "Avril", "Mai", "Juin", "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"], 1)]])
    quarter = forms.TypedChoiceField(label="Trimestre", required=False, coerce=int, choices=[("", "—"), (1, "T1"), (2, "T2"), (3, "T3"), (4, "T4")])
    start = forms.DateField(label="Du", required=False)
    end = forms.DateField(label="Au", required=False)
    status = forms.ChoiceField(label="Statut", required=False, choices=[("", "Tous"), ("active", "Actifs"), ("archived", "Archivés")])
    department = forms.ModelChoiceField(label="Département", queryset=Department.objects.none(), required=False)
    role = forms.ChoiceField(label="Rôle", required=False, choices=[("", "Tous"), *Assignment._meta.get_field("role").choices])
    follow_up = forms.ChoiceField(label="Suivi", required=False, choices=[("", "Tous"), *FollowUp._meta.get_field("status").choices])

    def __init__(self, *args, user, fields=None, **kwargs):
        super().__init__(*args, **kwargs)
        if fields is not None:
            self.fields = {k: v for k, v in self.fields.items() if k in fields}
        if "extension" in self.fields:
            ext = user_extension(user)
            self.fields["extension"].queryset = ChurchExtension.objects.all() if user_is_admin(user) else ChurchExtension.objects.filter(pk=ext.pk) if ext else ChurchExtension.objects.none()
        if "department" in self.fields:
            self.fields["department"].queryset = scoped(Department.objects.all(), user)
        style(self)

    def clean(self):
        data = super().clean()
        period = data.get("period")
        year = data.get("year") or timezone.localdate().year
        if period in ("month", "quarter", "year"):
            month = data.get("month") if period == "month" else (data.get("quarter", 0) or 0) * 3 - 2 if period == "quarter" else 1
            if not month or month < 1:
                raise forms.ValidationError("Choisissez le mois ou le trimestre.")
            last_month = month if period == "month" else month + 2 if period == "quarter" else 12
            data["start"] = date(year, month, 1)
            data["end"] = date(year, last_month, calendar.monthrange(year, last_month)[1])
        elif period == "custom" and not (data.get("start") and data.get("end")):
            raise forms.ValidationError("Indiquez les deux dates de la période.")
        if data.get("start") and data.get("end") and data["start"] > data["end"]:
            raise forms.ValidationError("La date de fin doit suivre la date de début.")
        return data

    def apply(self, qs, date_field=None):
        if not self.is_valid():
            return qs.none()
        data = self.cleaned_data
        if data.get("extension"):
            qs = qs.filter(extension=data["extension"])
        if date_field:
            if data.get("start"):
                qs = qs.filter(**{date_field + "__gte": data["start"]})
            if data.get("end"):
                qs = qs.filter(**{date_field + "__lte": data["end"]})
        return qs


class CatalogForm(forms.Form):
    extension = forms.ModelChoiceField(label="Extension", queryset=ChurchExtension.objects.none())
    names = forms.MultipleChoiceField(label="Départements à ajouter", choices=[(x, x) for x in DEPARTMENTS], widget=forms.CheckboxSelectMultiple)

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        ext = user_extension(user)
        self.fields["extension"].queryset = ChurchExtension.objects.all() if user_is_admin(user) else ChurchExtension.objects.filter(pk=ext.pk) if ext else ChurchExtension.objects.none()
        if not user_is_admin(user):
            self.initial["extension"] = ext
            self.fields["extension"].disabled = True
        style(self)
