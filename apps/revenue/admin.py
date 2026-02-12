"""
-------------------------------------------------------------------------
System: KP-CFMS (Computerized Financial Management System)
Client: Local Government Department, Khyber Pakhtunkhwa
Team Lead: Jamil Shah
Developers: Ali Asghar, Akhtar Munir and Zarif Khan
Description: Revenue Admin Configuration
-------------------------------------------------------------------------
"""
from django.contrib import admin
from .models import Payer, RevenueDemand, RevenueCollection


@admin.register(Payer)
class PayerAdmin(admin.ModelAdmin):
    """Admin configuration for Payer model."""
    
    list_display = ('name', 'cnic_ntn', 'contact_no', 'organization', 'is_active', 'created_at')
    list_filter = ('is_active', 'organization', 'created_at')
    search_fields = ('name', 'cnic_ntn', 'contact_no', 'address')
    ordering = ('-created_at',)
    
    fieldsets = (
        (None, {
            'fields': ('name', 'cnic_ntn', 'contact_no', 'address', 'email', 'is_active')
        }),
        ('System', {
            'fields': ('organization',),
            'classes': ('collapse',),
        }),
    )


@admin.register(RevenueDemand)
class RevenueDemandAdmin(admin.ModelAdmin):
    """Admin configuration for RevenueDemand model."""
    
    list_display = (
        'challan_no', 'payer', 'budget_head', 'amount', 
        'status', 'fiscal_year', 'issue_date', 'organization'
    )
    list_filter = ('status', 'fiscal_year', 'organization', 'issue_date')
    search_fields = ('challan_no', 'payer__name', 'budget_head__global_head__code')
    ordering = ('-issue_date',)
    readonly_fields = ('challan_no', 'posted_by', 'posted_at', 'cancelled_by', 'cancelled_at', 'accrual_voucher')
    
    fieldsets = (
        (None, {
            'fields': ('challan_no', 'fiscal_year', 'payer', 'budget_head', 'amount')
        }),
        ('Details', {
            'fields': ('issue_date', 'due_date', 'period_description', 'description', 'status'),
        }),
        ('Workflow', {
            'fields': ('accrual_voucher', 'posted_by', 'posted_at', 'cancelled_by', 'cancelled_at', 'cancellation_reason'),
            'classes': ('collapse',),
        }),
        ('System', {
            'fields': ('organization',),
            'classes': ('collapse',),
        }),
    )


@admin.register(RevenueCollection)
class RevenueCollectionAdmin(admin.ModelAdmin):
    """Admin configuration for RevenueCollection model."""
    
    list_display = (
        'receipt_no', 'demand', 'amount_received', 'receipt_date',
        'instrument_type', 'status', 'organization'
    )
    list_filter = ('status', 'instrument_type', 'receipt_date', 'organization')
    search_fields = ('receipt_no', 'demand__challan_no', 'demand__payer__name', 'instrument_no')
    ordering = ('-receipt_date',)
    readonly_fields = ('receipt_no', 'posted_by', 'posted_at', 'receipt_voucher')
    
    fieldsets = (
        (None, {
            'fields': ('receipt_no', 'demand', 'bank_account', 'amount_received', 'receipt_date')
        }),
        ('Payment Details', {
            'fields': ('instrument_type', 'instrument_no', 'remarks', 'status'),
        }),
        ('Workflow', {
            'fields': ('receipt_voucher', 'posted_by', 'posted_at'),
            'classes': ('collapse',),
        }),
        ('System', {
            'fields': ('organization',),
            'classes': ('collapse',),
        }),
    )
