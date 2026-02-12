"""
-------------------------------------------------------------------------
System: KP-CFMS (Computerized Financial Management System)
Client: Local Government Department, Khyber Pakhtunkhwa
Team Lead: Jamil Shah
Developers: Ali Asghar, Akhtar Munir and Zarif Khan
Description: Property Management app configuration.
-------------------------------------------------------------------------
"""
from django.apps import AppConfig


class PropertyConfig(AppConfig):
    """Configuration for the Property Management application."""
    
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.property'
    verbose_name = 'Immoveable Property Management (GIS)'
    
    def ready(self):
        """Import signals when app is ready."""
        try:
            import apps.property.signals  # noqa: F401
        except ImportError:
            pass
