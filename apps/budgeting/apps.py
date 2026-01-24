"""
-------------------------------------------------------------------------
System: KP-CFMS (Computerized Financial Management System)
Client: Local Government Department, Khyber Pakhtunkhwa
Team Lead: Jamil Shah
Developers: Ali Asghar, Akhtar Munir and Zarif Khan
Description: App configuration for the budgeting module.
             Handles budget planning, fiscal year management,
             and Schedule of Authorized Expenditure (SAE).
-------------------------------------------------------------------------
"""
from django.apps import AppConfig


class BudgetingConfig(AppConfig):
    """
    Configuration class for the budgeting application.
    
    This app manages:
    - Fiscal year calendar and locking
    - Budget entry forms (BDR-1, BDC-1, BDC-2)
    - Schedule of Establishment
    - Budget finalization and SAE generation
    - Quarterly fund releases
    """
    
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.budgeting'
    verbose_name = 'Budgeting Module'
    
    def ready(self) -> None:
        """Import signals when app is ready."""
        try:
            import apps.budgeting.signals  # noqa: F401
        except ImportError:
            pass
