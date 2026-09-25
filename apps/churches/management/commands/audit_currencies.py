from django.core.management.base import BaseCommand
from apps.churches.models import Currency, ChurchExtension
from apps.churches.currency_service import get_record_currency, get_currency_for_extension, get_exchange_rate, resolve_currency, CurrencyConversionError
from apps.reports.models import ServiceReport, ExtraIncome, ExtraExpense


class Command(BaseCommand):
    help = "Vérifie les devises et taux sans modifier les données."

    def handle(self, *args, **options):
        target = Currency.get_default()
        self.stdout.write(f"Devise administrateur : {target.code if target else 'MANQUANTE'}")
        warnings = 0
        for currency in Currency.objects.all():
            try:
                rate = get_exchange_rate(currency, target)
                self.stdout.write(f"1 {currency.code} = {rate} {target.code} (taux USD : {currency.usd_rate})")
                if currency.code != "USD" and currency.usd_rate == 1:
                    warnings += 1
                    self.stdout.write(self.style.WARNING(f"À vérifier : taux vers USD égal à 1 pour {currency.code}."))
            except CurrencyConversionError as exc:
                warnings += 1
                self.stdout.write(self.style.WARNING(str(exc)))
        for extension in ChurchExtension.objects.select_related("currency"):
            source = get_currency_for_extension(extension)
            legacy = resolve_currency(extension.currency_code_legacy)
            self.stdout.write(f"Extension #{extension.pk} : {source.code if source else 'MANQUANTE'} ; ancien code : {extension.currency_code_legacy}")
            if source and legacy and source.code != legacy.code:
                warnings += 1
                self.stdout.write(self.style.WARNING("Devise liée différente de l’ancien code : vérifier la configuration, sans réécrire automatiquement l’historique."))
        for model in [ServiceReport, ExtraIncome, ExtraExpense]:
            for record in model.objects.select_related("currency", "extension__currency").iterator():
                source = get_record_currency(record)
                local = get_currency_for_extension(record.extension)
                if not source or (local and source != local):
                    warnings += 1
                    self.stdout.write(self.style.WARNING(f"{model.__name__} #{record.pk} : source {source.code if source else 'MANQUANTE'}, extension {local.code if local else 'MANQUANTE'} — vérifier la devise réellement saisie."))
        self.stdout.write(f"{warnings} point(s) à vérifier. Aucune donnée modifiée. Les taux ne sont pas des cotations en direct.")
