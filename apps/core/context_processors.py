from apps.core.services import NotificationService

def notifications(request):
    """
    Context processor to add unread notification count for the authenticated user.
    """
    if request.user.is_authenticated:
        return {
            'unread_count': NotificationService.get_unread_count(request.user)
        }
    return {'unread_count': 0}
