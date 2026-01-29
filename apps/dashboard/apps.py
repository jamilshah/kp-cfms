"""
-------------------------------------------------------------------------
System: KP-CFMS (Computerized Financial Management System)
Client: Local Government Department, Khyber Pakhtunkhwa
Team Lead: Jamil Shah
Developers: Ali Asghar, Akhtar Munir and Zarif Khan
Description: Dashboard app configuration.
-------------------------------------------------------------------------
"""
from django.apps import AppConfig


class DashboardConfig(AppConfig):
    """Dashboard app configuration."""
    
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.dashboard'
    verbose_name = 'Executive Dashboard'
    
    def ready(self) -> None:
        """Import signals when app is ready."""
        import apps.dashboard.signals  # noqa
