import os

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import validate_email
from django.db import transaction

from apps.accounts.models import UserProfile


class Command(BaseCommand):
    help = "Create the deployment administrator once, using DJANGO_SUPERUSER_* variables."

    @transaction.atomic
    def handle(self, *args, **options):
        username = os.environ.get("DJANGO_SUPERUSER_USERNAME", "").strip()
        email = os.environ.get("DJANGO_SUPERUSER_EMAIL", "").strip()
        password = os.environ.get("DJANGO_SUPERUSER_PASSWORD", "")
        if not any((username, email, password)):
            self.stdout.write("Administrator initialization skipped: no DJANGO_SUPERUSER_* variables configured.")
            return
        if not username:
            raise CommandError("DJANGO_SUPERUSER_USERNAME is required.")

        User = get_user_model()
        user = User.objects.filter(username=username).first()
        if user:
            if not (user.is_active and user.is_staff and user.is_superuser):
                raise CommandError("This username already belongs to a non-administrator or inactive account; choose another username.")
            UserProfile.objects.get_or_create(user=user, defaults={"role": UserProfile.Role.ADMIN})
            self.stdout.write("Administrator already exists; credentials and permissions unchanged.")
            return

        if not email or not password:
            raise CommandError("DJANGO_SUPERUSER_EMAIL and DJANGO_SUPERUSER_PASSWORD are required for creation.")
        candidate = User(username=username, email=email, is_staff=True, is_superuser=True)
        try:
            User._meta.get_field("username").clean(username, candidate)
            validate_email(email)
            validate_password(password, candidate)
        except ValidationError:
            raise CommandError("Invalid administrator details. Use a valid username, email and a strong password satisfying the configured validators.") from None
        user = User.objects.create_superuser(username=username, email=email, password=password)
        UserProfile.objects.create(user=user, role=UserProfile.Role.ADMIN)
        self.stdout.write(self.style.SUCCESS("Deployment administrator created."))
