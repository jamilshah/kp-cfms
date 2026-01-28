"""
-------------------------------------------------------------------------
System: KP-CFMS (Computerized Financial Management System)
Client: Local Government Department, Khyber Pakhtunkhwa
Team Lead: Jamil Shah
Developers: Ali Asghar, Akhtar Munir and Zarif Khan
Description: App configuration for System Admin module.
-------------------------------------------------------------------------
"""
from django.apps import AppConfig


class SystemAdminConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.system_admin'
    verbose_name = 'System Administration'
