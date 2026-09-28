from django.db.models.signals import post_save
from django.dispatch import receiver
from apps.reports.models import Newcomer, NewConvert
from .services import import_legacy_person


@receiver(post_save, sender=Newcomer)
def newcomer_saved(sender, instance, created, raw=False, **kwargs):
    if created and not raw:
        import_legacy_person(instance, "visit")


@receiver(post_save, sender=NewConvert)
def convert_saved(sender, instance, created, raw=False, **kwargs):
    if created and not raw:
        import_legacy_person(instance, "conversion")
