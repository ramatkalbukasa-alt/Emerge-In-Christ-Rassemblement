from .models import Notification


def notifications_context(request):
    """Injecte le compteur de notifications non lues dans tous les templates."""
    if not request.user.is_authenticated:
        return {}
    unread_count = Notification.objects.filter(
        recipient=request.user, is_read=False
    ).count()
    recent = Notification.objects.filter(recipient=request.user).order_by("-created_at")[:6]
    return {
        "notif_unread_count": unread_count,
        "notif_recent": recent,
    }
