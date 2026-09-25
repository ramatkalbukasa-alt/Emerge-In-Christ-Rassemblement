from django import forms
from django.forms import inlineformset_factory

from apps.churches.models import Currency
from decimal import Decimal
from .models import ReportIncomeLine
from .models import Expense, ExtraIncome, ExtraExpense, NewConvert, Newcomer, ServiceReport


class RecordCurrencyForm(forms.ModelForm):
    def clean(self):
        data = super().clean()
        if not data.get("currency") and data.get("extension"):
            from apps.churches.currency_service import get_currency_for_extension
            data["currency"] = get_currency_for_extension(data["extension"])
            if not data["currency"]:
                self.add_error("currency", "Sélectionnez la devise des montants saisis.")
        return data


class ServiceReportForm(RecordCurrencyForm):
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


class NewConvertForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")

    class Meta:
        model = NewConvert
        fields = ["full_name", "phone", "address", "follow_up_owner"]


class NewcomerForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")

    class Meta:
        model = Newcomer
        fields = ["full_name", "invited_by"]


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
