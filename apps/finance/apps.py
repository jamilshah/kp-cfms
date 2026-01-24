"""
-------------------------------------------------------------------------
System: KP-CFMS (Computerized Financial Management System)
Client: Local Government Department, Khyber Pakhtunkhwa
Team Lead: Jamil Shah
Developers: Ali Asghar, Akhtar Munir and Zarif Khan
Description: Finance app configuration.
-------------------------------------------------------------------------
"""
from django.apps import AppConfig


class FinanceConfig(AppConfig):
    """Configuration for the finance application."""
    
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.finance'
    verbose_name = 'Finance & Chart of Accounts'
