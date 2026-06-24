from datetime import date

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from apps.accounts.models import UserProfile
from apps.churches.models import AppSetting, ChurchExtension
from apps.reports.models import ServiceReport


class Command(BaseCommand):
    help = "Create demo extensions, users and a few service reports."

    def handle(self, *args, **options):
        User = get_user_model()
        AppSetting.objects.update_or_create(pk=1, defaults={"church_name": "Emerge in Christ", "social_percentage": 5})

        extensions_data = [
            {
                "slug": "nicosie-centre",
                "name": "Nicosie Centre",
                "color": "#166534",
                "city": "Nicosie",
                "country": "Chypre",
                "pastor_name": "Pasteur Emmanuel Kabila",
                "currency": "EUR",
                "currency_symbol": "EUR",
            },
            {
                "slug": "limassol-sud",
                "name": "Limassol Sud",
                "color": "#1D4ED8",
                "city": "Limassol",
                "country": "Chypre",
                "pastor_name": "Pasteur Pierre Kabasele",
                "currency": "EUR",
                "currency_symbol": "EUR",
            },
            {
                "slug": "larnaca-est",
                "name": "Larnaca Est",
                "color": "#B45309",
                "city": "Larnaca",
                "country": "Chypre",
                "pastor_name": "Pasteur Daniel Nzamba",
                "currency": "EUR",
                "currency_symbol": "EUR",
            },
        ]

        extensions = []
        for data in extensions_data:
            extension, _ = ChurchExtension.objects.update_or_create(slug=data["slug"], defaults=data)
            extensions.append(extension)

        admin_user, _ = User.objects.get_or_create(username="admin", defaults={"email": "admin@example.com"})
        admin_user.set_password("admin12345")
        admin_user.is_staff = True
        admin_user.is_superuser = True
        admin_user.save()
        UserProfile.objects.update_or_create(user=admin_user, defaults={"role": UserProfile.Role.ADMIN})

        for extension in extensions:
            username = extension.slug.replace("-", "_")
            user, _ = User.objects.get_or_create(username=username, defaults={"email": f"{username}@example.com"})
            user.set_password("extension12345")
            user.save()
            UserProfile.objects.update_or_create(
                user=user,
                defaults={"role": UserProfile.Role.EXTENSION, "extension": extension},
            )

        if not ServiceReport.objects.exists():
            ServiceReport.objects.create(
                extension=extensions[0],
                service_date=date.today(),
                preacher="Pasteur Emmanuel Kabila",
                theme="Servir avec fidelite",
                men_count=38,
                women_count=54,
                children_count=21,
                visitors_count=7,
                offering_regular=820,
                offering_preacher=140,
                offering_tithe=360,
                offering_thanksgiving=90,
                expenses=180,
                submitted_by=admin_user,
            )

        self.stdout.write(self.style.SUCCESS("Demo data ready. Admin: admin / admin12345"))
