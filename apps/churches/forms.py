from django import forms

from .models import ChurchExtension


class ChurchExtensionForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault(
                "class",
                "w-full rounded-md border-gray-300 text-sm focus:border-ecclesia-green focus:ring-ecclesia-green",
            )

    class Meta:
        model = ChurchExtension
        fields = [
            "name",
            "slug",
            "color",
            "city",
            "country",
            "address",
            "created_on",
            "pastor_name",
            "pastor_email",
            "pastor_phone",
            "coordinator",
            "secretary",
            "treasurer",
            "currency",
            "currency_symbol",
            "is_active",
        ]
        widgets = {
            "created_on": forms.DateInput(attrs={"type": "date"}),
            "color": forms.TextInput(attrs={"type": "color"}),
            "address": forms.Textarea(attrs={"rows": 3}),
        }
