"""
-------------------------------------------------------------------------
System: KP-CFMS (Computerized Financial Management System)
Client: Local Government Department, Khyber Pakhtunkhwa
Team Lead: Jamil Shah
Developers: Ali Asghar, Akhtar Munir and Zarif Khan
Description: Admin configuration for CustomUser and Role models.
-------------------------------------------------------------------------
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _

from .models import CustomUser, Role


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    """Admin configuration for Role model."""
    
    list_display = ('name', 'code', 'is_system_role', 'user_count', 'created_at')
    list_filter = ('is_system_role',)
    search_fields = ('name', 'code', 'description')
    readonly_fields = ('group', 'created_at', 'updated_at')
    ordering = ('name',)
    
    fieldsets = (
        (None, {'fields': ('name', 'code', 'description')}),
        (_('Settings'), {'fields': ('is_system_role', 'group')}),
        (_('Timestamps'), {'fields': ('created_at', 'updated_at')}),
    )
    
    def user_count(self, obj):
        """Return number of users with this role."""
        return obj.users.count()
    user_count.short_description = _('Users')


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    """Admin configuration for CustomUser model."""
    
    model = CustomUser
    
    list_display = (
        'cnic', 'email', 'first_name', 'last_name',
        'get_roles_display', 'designation', 'is_active', 'is_staff', 'public_id'
    )
    list_display_links = ('cnic', 'email')
    list_filter = ('roles', 'is_active', 'is_staff', 'department')
    search_fields = ('cnic', 'email', 'first_name', 'last_name', 'designation', 'public_id')
    ordering = ('first_name', 'last_name')
    filter_horizontal = ('roles', 'groups', 'user_permissions')
    
    readonly_fields = ('public_id',)
    
    fieldsets = (
        (None, {'fields': ('public_id', 'cnic', 'password')}),
        (_('Personal Info'), {
            'fields': ('first_name', 'last_name', 'email', 'phone')
        }),
        (_('Roles & Organization'), {
            'fields': ('roles', 'organization', 'designation', 'department')
        }),
        (_('Legacy Role (Deprecated)'), {
            'fields': ('role',),
            'classes': ('collapse',),
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
                'password1', 'password2', 'roles', 'organization', 'designation', 'department'
            ),
        }),
    )
    
    def get_roles_display(self, obj):
        """Return comma-separated list of role names."""
        return obj.get_role_display()
    get_roles_display.short_description = _('Roles')
    
    class Media:
        js = ('js/admin_cnic_mask.js',)
