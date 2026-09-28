from django import forms
from django.forms import inlineformset_factory

from apps.churches.models import Currency
from decimal import Decimal
from .models import ReportIncomeLine
from .models import Expense, ExtraIncome, ExtraExpense, NewConvert, Newcomer, ServiceReport


class RecordCurrencyForm(forms.ModelForm):
    def clean(self):
        data = super().clean()
        if data.get("amount") is not None and data["amount"] < 0:
            self.add_error("amount", "Le montant ne peut pas être négatif.")
        if not data.get("currency") and data.get("extension"):
            from apps.churches.currency_service import get_currency_for_extension
            data["currency"] = get_currency_for_extension(data["extension"])
            if not data["currency"]:
                self.add_error("currency", "Sélectionnez la devise des montants saisis.")
        return data


class ServiceReportForm(RecordCurrencyForm):
    def clean(self):
        from django.core.exceptions import ValidationError
        from apps.ministry.services import policy_for
        data = super().clean()
        for field in ReportIncomeLine.Category.values:
            if data.get(field) is not None and data[field] < 0:
                self.add_error(field, "Le montant ne peut pas être négatif.")
        if data.get("extension"):
            try:
                policy_for(data["extension"])
            except ValidationError as exc:
                self.add_error(None, exc)
        return data

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")
        
        # Filtrer les devises actives
        self.fields['currency'].queryset = Currency.objects.filter(is_active=True)
        self.fields['currency'].empty_label = "Devise de l’extension (automatique)"

    class Meta:
        model = ServiceReport
        fields = [
            "extension",
            "service_type",
            "service_date",
            "currency",
            "service_time_start",
            "service_time_end",
            "preacher",
            "moderator",
            "interpreter",
            "scripture_text",
            "theme",
            "papa_count",
            "maman_count",
            "brothers_count",
            "sisters_count",
            "children_count",
            "offering_regular",
            "offering_preacher",
            "offering_tithe",
            "offering_thanksgiving",
            "thanksgiving_beneficiary",
        ]
        widgets = {
            "service_date": forms.DateInput(attrs={"type": "date"}),
            "service_time_start": forms.TimeInput(attrs={"type": "time"}),
            "service_time_end": forms.TimeInput(attrs={"type": "time"}),
            "currency": forms.Select(attrs={"class": "form-control"}),
        }
        labels = {
            "papa_count": "Papa",
            "maman_count": "Maman",
            "brothers_count": "Frères",
            "sisters_count": "Sœurs",
            "children_count": "Enfants",
        }


class ExpenseForm(forms.ModelForm):
    def clean_amount(self):
        amount = self.cleaned_data["amount"]
        if amount < 0:
            raise forms.ValidationError("Une dépense ne peut pas être négative.")
        return amount

    class Meta:
        model = Expense
        fields = ["amount", "reason"]
        widgets = {
            "amount": forms.NumberInput(attrs={"step": "0.01", "min": "0", "class": "form-control"}),
            "reason": forms.TextInput(attrs={"class": "form-control", "placeholder": "Motif de la dépense"}),
        }


class ReportIncomeLineForm(forms.ModelForm):
    amount = forms.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"), label="Montant reçu")

    class Meta:
        model = ReportIncomeLine
        fields = ["category", "amount", "currency"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["currency"].queryset = Currency.objects.filter(is_active=True)
        self.fields["currency"].empty_label = "Sélectionner une devise"
        self.fields["category"].initial = None
        self.fields["category"].choices = [("", "Sélectionner une catégorie"), *ReportIncomeLine.Category.choices]
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"


ReportIncomeLineFormSet = inlineformset_factory(
    ServiceReport, ReportIncomeLine, form=ReportIncomeLineForm,
    extra=0, can_delete=True, max_num=100, validate_max=True, absolute_max=100,
)


class ExtraIncomeForm(RecordCurrencyForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")
        
        # Filtrer les devises actives
        self.fields['currency'].queryset = Currency.objects.filter(is_active=True)
        self.fields['currency'].empty_label = "Devise de l’extension (automatique)"

    class Meta:
        model = ExtraIncome
        fields = ["amount", "description", "income_date", "extension", "currency"]
        widgets = {
            "amount": forms.NumberInput(attrs={"step": "0.01", "min": "0", "class": "form-control"}),
            "description": forms.TextInput(attrs={"class": "form-control", "placeholder": "Description"}),
            "income_date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "extension": forms.Select(attrs={"class": "form-control"}),
            "currency": forms.Select(attrs={"class": "form-control"}),
        }


ExpenseFormSet = inlineformset_factory(
    ServiceReport,
    Expense,
    form=ExpenseForm,
    extra=1,
    can_delete=True,
)

class ExtraExpenseForm(RecordCurrencyForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")
        
        # Filtrer les devises actives
        self.fields['currency'].queryset = Currency.objects.filter(is_active=True)
        self.fields['currency'].empty_label = "Devise de l’extension (automatique)"

    class Meta:
        model = ExtraExpense
        fields = ["amount", "description", "expense_date", "extension", "currency"]
        widgets = {
            "amount": forms.NumberInput(attrs={"step": "0.01", "min": "0", "class": "form-control"}),
            "description": forms.TextInput(attrs={"class": "form-control", "placeholder": "Motif"}),
            "expense_date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "extension": forms.Select(attrs={"class": "form-control"}),
            "currency": forms.Select(attrs={"class": "form-control"}),
        }


class RegistryPersonForm(forms.ModelForm):
    confirm_distinct = forms.BooleanField(required=False, label="Fiche similaire vérifiée : personne distincte")

    def __init__(self, *args, people=None, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.ministry.models import Person
        self.fields["person"].queryset = people if people is not None else Person.objects.none()
        self.fields["full_name"].required = False
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")

    def clean(self):
        from apps.ministry.models import normalized
        data = super().clean()
        if data.get("person"):
            person = data["person"]
            data["full_name"] = person.full_name
            if "phone" in self.fields:
                data["phone"] = person.phone
                data["address"] = person.address
        elif data.get("full_name"):
            matches = self.fields["person"].queryset.filter(name_key=normalized(data["full_name"]))
            if matches.exists() and not data.get("confirm_distinct"):
                self.add_error("person", "Une fiche de même nom existe : sélectionnez-la ou confirmez qu’il s’agit d’une autre personne.")
        elif not data.get("DELETE"):
            self.add_error("full_name", "Renseignez un nom ou sélectionnez une personne existante.")
        return data


class NewConvertForm(RegistryPersonForm):

    class Meta:
        model = NewConvert
        fields = ["person", "full_name", "phone", "address", "follow_up_owner"]


class NewcomerForm(RegistryPersonForm):
    class Meta:
        model = Newcomer
        fields = ["person", "full_name", "invited_by"]


NewConvertFormSet = inlineformset_factory(
    ServiceReport,
    NewConvert,
    form=NewConvertForm,
    extra=1,
    can_delete=True,
)

NewcomerFormSet = inlineformset_factory(
    ServiceReport,
    Newcomer,
    form=NewcomerForm,
    extra=1,
    can_delete=True,
)
