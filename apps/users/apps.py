"""
-------------------------------------------------------------------------
System: KP-CFMS (Computerized Financial Management System)
Client: Local Government Department, Khyber Pakhtunkhwa
Team Lead: Jamil Shah
Developers: Ali Asghar, Akhtar Munir and Zarif Khan
Description: Users app configuration.
-------------------------------------------------------------------------
"""
from django.apps import AppConfig


class UsersConfig(AppConfig):
    """Configuration for the users application."""
    
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.users'
    verbose_name = 'User Management'

    def ready(self):
        # Import signal handlers to ensure they're registered on startup
        try:
            from . import signals  # noqa: F401
        except Exception:
            # Avoid breaking startup if logging/signals fail temporarily
            import logging
            logging.getLogger(__name__).exception('Failed to import users.signals')
