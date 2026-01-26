"""
-------------------------------------------------------------------------
System: KP-CFMS (Computerized Financial Management System)
Client: Local Government Department, Khyber Pakhtunkhwa
Team Lead: Jamil Shah
Developers: Ali Asghar, Akhtar Munir and Zarif Khan
Description: Django admin configuration for core models including
             Division, District, Tehsil (Geography) and Organization (Tenant).
-------------------------------------------------------------------------
"""
from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from apps.core.models import Division, District, Tehsil, Organization, BankAccount


@admin.register(Division)
class DivisionAdmin(admin.ModelAdmin):
    """Admin configuration for Division model."""
    
    list_display = ['name', 'code', 'district_count', 'tehsil_count', 'org_count', 'is_active']
    list_filter = ['is_active']
    search_fields = ['name', 'code']
    ordering = ['name']
    
    def district_count(self, obj: Division) -> int:
        """Count districts in this division."""
        return obj.districts.count()
    district_count.short_description = _('Districts')
    
    def tehsil_count(self, obj: Division) -> int:
        """Count tehsils in this division."""
        return Tehsil.objects.filter(district__division=obj).count()
    tehsil_count.short_description = _('Tehsils')
    
    def org_count(self, obj: Division) -> int:
        """Count organizations in this division."""
        return Organization.objects.filter(tehsil__district__division=obj).count()
    org_count.short_description = _('Organizations')


@admin.register(District)
class DistrictAdmin(admin.ModelAdmin):
    """Admin configuration for District model."""
    
    list_display = ['name', 'division', 'code', 'tehsil_count', 'org_count', 'is_active']
    list_filter = ['division', 'is_active']
    search_fields = ['name', 'code', 'division__name']
    ordering = ['division__name', 'name']
    
    def tehsil_count(self, obj: District) -> int:
        """Count tehsils in this district."""
        return obj.tehsils.count()
    tehsil_count.short_description = _('Tehsils')
    
    def org_count(self, obj: District) -> int:
        """Count organizations in this district."""
        return Organization.objects.filter(tehsil__district=obj).count()
    org_count.short_description = _('Organizations')


@admin.register(Tehsil)
class TehsilAdmin(admin.ModelAdmin):
    """Admin configuration for Tehsil model (Geography)."""
    
    list_display = ['name', 'district', 'division_name', 'code', 'org_count', 'is_active']
    list_filter = ['district__division', 'district', 'is_active']
    search_fields = ['name', 'code', 'district__name', 'district__division__name']
    ordering = ['district__division__name', 'district__name', 'name']
    
    def division_name(self, obj: Tehsil) -> str:
        """Get division name."""
        return obj.district.division.name
    division_name.short_description = _('Division')
    
    def org_count(self, obj: Tehsil) -> int:
        """Count organizations in this tehsil."""
        return obj.organizations.count()
    org_count.short_description = _('Organizations')


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    """Admin configuration for Organization model (Tenant)."""
    
    list_display = ['name', 'org_type', 'tehsil', 'ddo_code', 'bank_account_count', 'user_count', 'is_active']
    list_filter = ['org_type', 'tehsil__district__division', 'tehsil__district', 'is_active']
    search_fields = ['name', 'ddo_code', 'pla_account_no', 'tehsil__name']
    ordering = ['name']
    readonly_fields = ['public_id', 'created_at', 'updated_at']
    
    fieldsets = (
        (None, {
            'fields': ('name', 'org_type', 'tehsil', 'is_active')
        }),
        (_('Financial Details'), {
            'fields': ('ddo_code', 'pla_account_no')
        }),
        (_('System Information'), {
            'fields': ('public_id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def bank_account_count(self, obj: Organization) -> int:
        """Count bank accounts for this organization."""
        return obj.bank_accounts.count()
    bank_account_count.short_description = _('Bank Accounts')
    
    def user_count(self, obj: Organization) -> int:
        """Count users in this organization."""
        return obj.users.count()
    user_count.short_description = _('Users')


@admin.register(BankAccount)
class BankAccountAdmin(admin.ModelAdmin):
    """Admin configuration for BankAccount model."""
    
    list_display = ['account_number', 'bank_name', 'title', 'organization', 'gl_code', 'is_active']
    list_filter = ['bank_name', 'is_active', 'organization']
    search_fields = ['account_number', 'title', 'bank_name', 'organization__name']
    ordering = ['organization__name', 'bank_name', 'account_number']
    readonly_fields = ['public_id', 'created_at', 'updated_at', 'created_by', 'updated_by']
    
    fieldsets = (
        (_('Bank Details'), {
            'fields': ('organization', 'bank_name', 'branch_code', 'account_number', 'title')
        }),
        (_('GL Integration'), {
            'fields': ('gl_code',),
            'description': _('Link this bank account to a General Ledger account (typically an Asset account).')
        }),
        (_('Status'), {
            'fields': ('is_active',)
        }),
        (_('Audit Trail'), {
            'fields': ('public_id', 'created_at', 'updated_at', 'created_by', 'updated_by'),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        """Override to set audit fields."""
        if not change:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)

