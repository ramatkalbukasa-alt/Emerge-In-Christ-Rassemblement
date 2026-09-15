from django import forms

from .models import ChurchExtension, Currency


class ChurchExtensionForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name != "color":
                field.widget.attrs.setdefault("class", "form-control")
        
        # Filtrer les devises actives
        self.fields['currency'].queryset = Currency.objects.filter(is_active=True)
        self.fields['currency'].empty_label = "-- Sélectionner une devise --"

    class Meta:
        model = ChurchExtension
        fields = [
            "name",
            "slug",
            "logo",
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
            "tithe_percentage",
            "social_percentage",
            "is_active",
        ]
        widgets = {
            "created_on": forms.DateInput(attrs={"type": "date"}),
            "color": forms.TextInput(attrs={"type": "color", "class": "h-10 w-20 cursor-pointer rounded border border-slate-300"}),
            "address": forms.Textarea(attrs={"rows": 3}),
            "currency": forms.Select(attrs={"class": "form-control"}),
            "logo": forms.FileInput(attrs={"accept": "image/*"}),
        }
        help_texts = {
            "currency": "Sélectionnez la devise par défaut pour cette extension. Les taux de change sont gérés dans les paramètres des devises.",
            "logo": "Format recommandé : PNG ou SVG, fond transparent.",
        }
