import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("churches", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ServiceReport",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "service_type",
                    models.CharField(
                        choices=[
                            ("sunday", "Culte dominical"),
                            ("week", "Culte de semaine"),
                            ("special", "Culte special"),
                        ],
                        default="sunday",
                        max_length=20,
                    ),
                ),
                ("service_date", models.DateField()),
                ("preacher", models.CharField(blank=True, max_length=160)),
                ("theme", models.CharField(blank=True, max_length=220)),
                ("men_count", models.PositiveIntegerField(default=0)),
                ("women_count", models.PositiveIntegerField(default=0)),
                ("children_count", models.PositiveIntegerField(default=0)),
                ("visitors_count", models.PositiveIntegerField(default=0)),
                ("offering_regular", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("offering_preacher", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("offering_tithe", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("offering_thanksgiving", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("extra_income", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("expenses", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("total_attendance", models.PositiveIntegerField(default=0, editable=False)),
                ("total_offerings", models.DecimalField(decimal_places=2, default=0, editable=False, max_digits=12)),
                ("tithe_deduction", models.DecimalField(decimal_places=2, default=0, editable=False, max_digits=12)),
                ("social_deduction", models.DecimalField(decimal_places=2, default=0, editable=False, max_digits=12)),
                ("net_balance", models.DecimalField(decimal_places=2, default=0, editable=False, max_digits=12)),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "extension",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="reports",
                        to="churches.churchextension",
                    ),
                ),
                (
                    "submitted_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="submitted_reports",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["-service_date", "-created_at"]},
        ),
        migrations.CreateModel(
            name="NewConvert",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("full_name", models.CharField(max_length=160)),
                ("phone", models.CharField(blank=True, max_length=60)),
                ("address", models.CharField(blank=True, max_length=220)),
                ("follow_up_owner", models.CharField(blank=True, max_length=160)),
                (
                    "report",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="new_converts",
                        to="reports.servicereport",
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="servicereport",
            constraint=models.UniqueConstraint(
                fields=("extension", "service_date", "service_type"),
                name="unique_extension_report_per_service",
            ),
        ),
    ]
