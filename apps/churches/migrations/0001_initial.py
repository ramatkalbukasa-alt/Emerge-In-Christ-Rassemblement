from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="AppSetting",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("social_percentage", models.DecimalField(decimal_places=2, default=5, max_digits=5)),
                ("church_name", models.CharField(default="Emerge in Christ", max_length=160)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name="ChurchExtension",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=160)),
                ("slug", models.SlugField(max_length=180, unique=True)),
                ("color", models.CharField(default="#166534", max_length=7)),
                ("city", models.CharField(blank=True, max_length=120)),
                ("country", models.CharField(blank=True, max_length=120)),
                ("address", models.TextField(blank=True)),
                ("created_on", models.DateField(blank=True, null=True)),
                ("pastor_name", models.CharField(blank=True, max_length=160)),
                ("pastor_email", models.EmailField(blank=True, max_length=254)),
                ("pastor_phone", models.CharField(blank=True, max_length=50)),
                ("coordinator", models.CharField(blank=True, max_length=160)),
                ("secretary", models.CharField(blank=True, max_length=160)),
                ("treasurer", models.CharField(blank=True, max_length=160)),
                ("currency", models.CharField(default="EUR", max_length=8)),
                ("currency_symbol", models.CharField(default="EUR", max_length=8)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["name"]},
        ),
    ]
