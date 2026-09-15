from django.contrib.auth import get_user_model

from .models import Notification


User = get_user_model()


def notify_all_admins(title, body, notification_type=Notification.Type.SYSTEM, link=""):
    """Envoie une notification à tous les administrateurs."""
    admins = User.objects.filter(profile__role="admin")
    for admin in admins:
        Notification.objects.create(
            recipient=admin,
            notification_type=notification_type,
            title=title,
            body=body,
            link=link,
        )


def notify_user(user, title, body, notification_type=Notification.Type.SYSTEM, link=""):
    """Envoie une notification à un utilisateur spécifique."""
    Notification.objects.create(
        recipient=user,
        notification_type=notification_type,
        title=title,
        body=body,
        link=link,
    )
