"""
-------------------------------------------------------------------------
System: KP-CFMS (Computerized Financial Management System)
Client: Local Government Department, Khyber Pakhtunkhwa
Team Lead: Jamil Shah
Developers: Ali Asghar, Akhtar Munir and Zarif Khan
Description: Revenue app configuration.
-------------------------------------------------------------------------
"""
from django.apps import AppConfig


class RevenueConfig(AppConfig):
    """Configuration for the Revenue module."""
    
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.revenue'
    verbose_name = 'Revenue Management'
