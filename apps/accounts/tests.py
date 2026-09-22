from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from .models import UserProfile


class DeploymentAdminTests(TestCase):
    def run_command(self, **changes):
        env = {
            "DJANGO_SUPERUSER_USERNAME": "deployment-owner",
            "DJANGO_SUPERUSER_EMAIL": "owner@example.org",
            "DJANGO_SUPERUSER_PASSWORD": "Initial!Random-9438-Strong",
        }
        env.update(changes)
        output = StringIO()
        with patch.dict("os.environ", env):
            call_command("ensure_admin", stdout=output)
        return output.getvalue()

    def test_creates_active_superuser_and_application_profile(self):
        output = self.run_command()
        user = get_user_model().objects.get(username="deployment-owner")
        self.assertTrue(user.is_active and user.is_staff and user.is_superuser)
        self.assertTrue(user.check_password("Initial!Random-9438-Strong"))
        self.assertEqual(user.profile.role, UserProfile.Role.ADMIN)
        self.assertNotIn("Initial!Random", output)

    def test_redeploy_preserves_changed_password_and_email(self):
        self.run_command()
        user = get_user_model().objects.get(username="deployment-owner")
        user.set_password("Changed!Secret-83761")
        user.email = "changed@example.org"
        user.save()
        self.run_command(DJANGO_SUPERUSER_PASSWORD="")
        user.refresh_from_db()
        self.assertTrue(user.check_password("Changed!Secret-83761"))
        self.assertEqual(user.email, "changed@example.org")
        self.assertEqual(UserProfile.objects.count(), 1)

    def test_never_promotes_existing_regular_account(self):
        user = get_user_model().objects.create_user(username="deployment-owner")
        with self.assertRaises(CommandError):
            self.run_command()
        user.refresh_from_db()
        self.assertFalse(user.is_superuser)
        self.assertFalse(UserProfile.objects.exists())

    def test_missing_password_does_not_create_account(self):
        with self.assertRaises(CommandError):
            self.run_command(DJANGO_SUPERUSER_PASSWORD="")
        self.assertFalse(get_user_model().objects.exists())

    def test_absent_configuration_is_a_noop(self):
        self.run_command(DJANGO_SUPERUSER_USERNAME="", DJANGO_SUPERUSER_EMAIL="", DJANGO_SUPERUSER_PASSWORD="")
        self.assertFalse(get_user_model().objects.exists())

    def test_invalid_email_does_not_create_account(self):
        with self.assertRaises(CommandError):
            self.run_command(DJANGO_SUPERUSER_EMAIL="invalid")
        self.assertFalse(get_user_model().objects.exists())
