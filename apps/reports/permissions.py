from apps.accounts.models import UserProfile

from .models import ServiceReport


def user_is_admin(user):
    if not user.is_authenticated or not user.is_active:
        return False
    try:
        return user.profile.role == UserProfile.Role.ADMIN
    except UserProfile.DoesNotExist:
        return False


def user_extension(user):
    if not user.is_authenticated or not user.is_active:
        return None
    try:
        return user.profile.extension
    except UserProfile.DoesNotExist:
        return None


def reports_for_user(user):
    if user_is_admin(user):
        return ServiceReport.objects.select_related("extension", "submitted_by")
    extension = user_extension(user)
    if extension:
        return ServiceReport.objects.select_related("extension", "submitted_by").filter(extension=extension)
    return ServiceReport.objects.none()


def report_event_group(user):
    if not user.is_authenticated:
        return None
    profile = UserProfile.objects.select_related("extension").filter(
        user_id=user.pk, user__is_active=True
    ).first()
    if profile is None:
        return None
    if profile.role == UserProfile.Role.ADMIN:
        return "reports.admin"
    if profile.extension_id and profile.extension.is_active:
        return f"reports.extension.{profile.extension_id}"
    return None
