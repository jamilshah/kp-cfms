from django.contrib.auth.signals import user_login_failed
from django.dispatch import receiver
import logging

logger = logging.getLogger(__name__)


@receiver(user_login_failed)
def log_failed_login(sender, credentials, request, **kwargs):
    """Log failed login attempts for debugging temporary issues.

    This is temporary and should be removed or reduced in verbosity
    before deploying to production.
    """
    try:
        username = credentials.get('username')
    except Exception:
        username = None

    ip = None
    if request is not None:
        ip = request.META.get('REMOTE_ADDR') or request.META.get('HTTP_X_FORWARDED_FOR')

    logger.warning(
        "Failed login attempt - username=%s ip=%s path=%s",
        username,
        ip,
        getattr(request, 'path', None)
    )
