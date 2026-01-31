"""
-------------------------------------------------------------------------
System: KP-CFMS (Computerized Financial Management System)
Client: Local Government Department, Khyber Pakhtunkhwa
Team Lead: Jamil Shah
Developers: Ali Asghar, Akhtar Munir and Zarif Khan
Description: Admin configuration for the expenditure module.
-------------------------------------------------------------------------
"""
from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from apps.expenditure.models import Payee, Bill, BillLine, Payment, BillStatus


@admin.register(Payee)
class PayeeAdmin(admin.ModelAdmin):
    """Admin interface for Payee model."""
    
    list_display = [
        'name', 'cnic_ntn', 'phone', 'email', 
        'bank_name', 'is_active', 'organization'
    ]
    list_filter = ['is_active', 'organization']
    search_fields = ['name', 'cnic_ntn', 'email', 'phone']
    ordering = ['name']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('organization', 'name', 'cnic_ntn', 'address')
        }),
        ('Contact Information', {
            'fields': ('phone', 'email')
        }),
        ('Bank Information', {
            'fields': ('bank_name', 'bank_account')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)



class BillLineInline(admin.TabularInline):
    """Inline for Bill Lines."""
    model = BillLine
    extra = 1
    autocomplete_fields = ['budget_head']


@admin.register(Bill)
class BillAdmin(admin.ModelAdmin):
    """Admin interface for Bill model."""
    
    list_display = [
        'id', 'bill_date', 'payee',
        'gross_amount', 'tax_amount', 'net_amount',
        'status_badge', 'fiscal_year', 'organization'
    ]
    list_filter = ['status', 'fiscal_year', 'organization']
    search_fields = ['payee__name', 'bill_number', 'description']
    ordering = ['-bill_date', '-created_at']
    date_hierarchy = 'bill_date'
    readonly_fields = [
        'status', 'submitted_at', 'submitted_by',
        'approved_at', 'approved_by', 'rejected_at', 'rejected_by',
        'rejection_reason', 'liability_voucher'
    ]
    
    fieldsets = (
        ('Bill Information', {
            'fields': (
                'organization', 'fiscal_year', 'payee',
                'bill_date', 'bill_number', 'description'
            )
        }),
        ('Amount Details', {
            'fields': ('gross_amount', 'tax_amount', 'net_amount')
        }),
        ('Workflow', {
            'fields': (
                'status',
                ('submitted_at', 'submitted_by'),
                ('approved_at', 'approved_by'),
                ('rejected_at', 'rejected_by'),
                'rejection_reason'
            ),
            'classes': ('collapse',)
        }),
        ('GL Link', {
            'fields': ('liability_voucher',),
            'classes': ('collapse',)
        }),
    )
    
    
    inlines = [BillLineInline]
    
    def status_badge(self, obj):
        colors = {
            BillStatus.DRAFT: 'secondary',
            BillStatus.SUBMITTED: 'warning',
            BillStatus.APPROVED: 'success',
            BillStatus.PAID: 'primary',
            BillStatus.REJECTED: 'danger',
        }
        color = colors.get(obj.status, 'secondary')
        return format_html(
            '<span class="badge bg-{}">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    status_badge.admin_order_field = 'status'
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    """Admin interface for Payment model."""
    
    list_display = [
        'id', 'cheque_number', 'cheque_date', 'bill_payee',
        'bank_account', 'amount', 'is_posted', 'organization'
    ]
    list_filter = ['is_posted', 'bank_account__bank_name', 'organization']
    search_fields = ['cheque_number', 'bill__payee__name']
    ordering = ['-cheque_date', '-created_at']
    date_hierarchy = 'cheque_date'
    readonly_fields = ['is_posted', 'posted_at', 'posted_by', 'payment_voucher']
    
    fieldsets = (
        ('Payment Information', {
            'fields': (
                'organization', 'bill', 'bank_account',
                'cheque_number', 'cheque_date', 'amount'
            )
        }),
        ('Posting Status', {
            'fields': ('is_posted', 'posted_at', 'posted_by', 'payment_voucher'),
            'classes': ('collapse',)
        }),
    )
    
    def bill_payee(self, obj):
        return obj.bill.payee.name
    bill_payee.short_description = 'Payee'
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)
