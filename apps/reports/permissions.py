from apps.accounts.models import UserProfile


def user_is_admin(user):
    profile = getattr(user, "profile", None)
    return bool(profile and profile.role == UserProfile.Role.ADMIN)


def user_extension(user):
    profile = getattr(user, "profile", None)
    return getattr(profile, "extension", None)


def reports_for_user(user):
    from .models import ServiceReport

    if user_is_admin(user):
        return ServiceReport.objects.select_related("extension", "submitted_by")
    extension = user_extension(user)
    if extension:
        return ServiceReport.objects.select_related("extension", "submitted_by").filter(extension=extension)
    return ServiceReport.objects.none()
