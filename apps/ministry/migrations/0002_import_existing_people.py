import unicodedata
from django.db import migrations


def forwards(apps, schema_editor):
    alias = schema_editor.connection.alias
    Person = apps.get_model("ministry", "Person")
    Event = apps.get_model("ministry", "PersonEvent")
    Policy = apps.get_model("ministry", "FinancialPolicy")
    Extension = apps.get_model("churches", "ChurchExtension")
    for ext in Extension.objects.using(alias).all().iterator():
        Policy.objects.using(alias).get_or_create(extension_id=ext.pk, defaults={"regular_tithe": ext.tithe_percentage})
    for model_name, kind in [("Newcomer", "visit"), ("NewConvert", "conversion")]:
        Model = apps.get_model("reports", model_name)
        for old in Model.objects.using(alias).select_related("report").all().iterator():
            source = f"reports.{model_name}:{old.pk}"
            if Event.objects.using(alias).filter(source=source).exists():
                continue
            person = Person.objects.using(alias).create(extension_id=old.report.extension_id,
                full_name=old.full_name, phone=getattr(old, "phone", ""), address=getattr(old, "address", ""),
                name_key=" ".join(unicodedata.normalize("NFKC", old.full_name).casefold().split()),
                phone_key="".join(c for c in getattr(old, "phone", "") if c.isdigit()))
            Model.objects.using(alias).filter(pk=old.pk).update(person_id=person.pk)
            Event.objects.using(alias).create(person_id=person.pk, extension_id=old.report.extension_id,
                report_id=old.report_id, kind=kind, date=old.report.service_date, date_inferred=True,
                source=source, invited_by=getattr(old, "invited_by", ""), follow_up_owner=getattr(old, "follow_up_owner", ""))


class Migration(migrations.Migration):
    dependencies = [("ministry", "0001_initial"), ("reports", "0009_newcomer_person_newconvert_person_and_more")]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
