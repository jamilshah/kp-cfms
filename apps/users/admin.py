"""
-------------------------------------------------------------------------
System: KP-CFMS (Computerized Financial Management System)
Client: Local Government Department, Khyber Pakhtunkhwa
Team Lead: Jamil Shah
Developers: Ali Asghar, Akhtar Munir and Zarif Khan
Description: Admin configuration for CustomUser model.
-------------------------------------------------------------------------
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _

from .models import CustomUser


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    """Admin configuration for CustomUser model."""
    
    model = CustomUser
    
    list_display = (
        'cnic', 'email', 'first_name', 'last_name',
        'role', 'designation', 'is_active', 'is_staff'
    )
    list_filter = ('role', 'is_active', 'is_staff', 'department')
    search_fields = ('cnic', 'email', 'first_name', 'last_name', 'designation')
    ordering = ('first_name', 'last_name')
    
    fieldsets = (
        (None, {'fields': ('cnic', 'password')}),
        (_('Personal Info'), {
            'fields': ('first_name', 'last_name', 'email', 'phone')
        }),
        (_('Role & Department'), {
            'fields': ('role', 'designation', 'department')
        }),
        (_('Permissions'), {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        (_('Important Dates'), {
            'fields': ('last_login', 'date_joined'),
        }),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'cnic', 'email', 'first_name', 'last_name',
                'password1', 'password2', 'role', 'designation', 'department'
            ),
        }),
    )
