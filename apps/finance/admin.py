"""
-------------------------------------------------------------------------
System: KP-CFMS (Computerized Financial Management System)
Client: Local Government Department, Khyber Pakhtunkhwa
Team Lead: Jamil Shah
Developers: Ali Asghar, Akhtar Munir and Zarif Khan
Description: Admin configuration for Finance models.
-------------------------------------------------------------------------
"""
from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import FunctionCode, BudgetHead


@admin.register(FunctionCode)
class FunctionCodeAdmin(admin.ModelAdmin):
    """Admin configuration for FunctionCode model."""
    
    list_display = ('code', 'name', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('code', 'name')
    ordering = ('code',)


@admin.register(BudgetHead)
class BudgetHeadAdmin(admin.ModelAdmin):
    """Admin configuration for BudgetHead model."""
    
    list_display = (
        'tma_sub_object', 'tma_description', 'pifra_object',
        'fund_id', 'fund_type', 'account_type', 'budget_control', 'is_active'
    )
    list_filter = (
        'fund_id', 'fund_type', 'account_type',
        'budget_control', 'project_required', 'is_active'
    )
    search_fields = (
        'pifra_object', 'pifra_description',
        'tma_sub_object', 'tma_description'
    )
    ordering = ('fund_id', 'pifra_object', 'tma_sub_object')
    
    readonly_fields = ('fund_type', 'created_at', 'updated_at', 'created_by', 'updated_by')
    
    fieldsets = (
        (_('Identification'), {
            'fields': ('pifra_object', 'pifra_description', 'tma_sub_object', 'tma_description')
        }),
        (_('Classification'), {
            'fields': ('fund_id', 'function', 'account_type', 'fund_type')
        }),
        (_('Control Flags'), {
            'fields': ('budget_control', 'project_required', 'posting_allowed', 'is_charged', 'is_active')
        }),
        (_('Audit Trail'), {
            'fields': ('created_at', 'updated_at', 'created_by', 'updated_by'),
            'classes': ('collapse',)
        }),
    )
