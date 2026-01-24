"""
-------------------------------------------------------------------------
System: KP-CFMS (Computerized Financial Management System)
Client: Local Government Department, Khyber Pakhtunkhwa
Team Lead: Jamil Shah
Developers: Ali Asghar, Akhtar Munir and Zarif Khan
Description: Expenditure app configuration.
-------------------------------------------------------------------------
"""
from django.apps import AppConfig


class ExpenditureConfig(AppConfig):
    """Configuration for the expenditure application."""
    
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.expenditure'
    verbose_name = 'Expenditure Management'
