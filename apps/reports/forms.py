from django import forms

from apps.churches.models import ChurchExtension

from .models import NewConvert, ServiceReport


class ExtensionChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, extension):
        return f"{extension.name} ({extension.slug}, {extension.currency})"


class ServiceReportForm(forms.ModelForm):
    extension = ExtensionChoiceField(queryset=ChurchExtension.objects.filter(is_active=True))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")

    class Meta:
        model = ServiceReport
        fields = [
            "extension",
            "service_type",
            "service_date",
            "preacher",
            "theme",
            "men_count",
            "women_count",
            "children_count",
            "visitors_count",
            "offering_regular",
            "offering_preacher",
            "offering_tithe",
            "offering_thanksgiving",
            "extra_income",
            "expenses",
            "notes",
        ]
        widgets = {
            "service_date": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }


class NewConvertForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")

    class Meta:
        model = NewConvert
        fields = ["full_name", "phone", "address", "follow_up_owner"]
