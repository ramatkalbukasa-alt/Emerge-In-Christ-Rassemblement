from django import forms
from django.forms import inlineformset_factory

from apps.churches.models import Currency
from .models import Expense, ExtraIncome, ExtraExpense, NewConvert, Newcomer, ServiceReport


class ServiceReportForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")
        
        # Filtrer les devises actives
        self.fields['currency'].queryset = Currency.objects.filter(is_active=True)
        self.fields['currency'].empty_label = "-- Sélectionner une devise --"

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


class ExtraIncomeForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")
        
        # Filtrer les devises actives
        self.fields['currency'].queryset = Currency.objects.filter(is_active=True)
        self.fields['currency'].empty_label = "-- Sélectionner une devise --"

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

class ExtraExpenseForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")
        
        # Filtrer les devises actives
        self.fields['currency'].queryset = Currency.objects.filter(is_active=True)
        self.fields['currency'].empty_label = "-- Sélectionner une devise --"

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
