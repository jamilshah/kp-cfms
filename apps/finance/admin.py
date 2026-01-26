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

from .models import FunctionCode, BudgetHead, Fund, Voucher, JournalEntry


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


@admin.register(Fund)
class FundAdmin(admin.ModelAdmin):
    """Admin configuration for Fund model."""
    
    list_display = ('code', 'name', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('code', 'name', 'description')
    ordering = ('code',)
    readonly_fields = ('public_id', 'created_at', 'updated_at')
    
    fieldsets = (
        (None, {
            'fields': ('code', 'name', 'description', 'is_active')
        }),
        (_('System Information'), {
            'fields': ('public_id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


class JournalEntryInline(admin.TabularInline):
    """Inline admin for JournalEntry within Voucher."""
    
    model = JournalEntry
    extra = 2
    fields = ('budget_head', 'description', 'debit', 'credit')
    autocomplete_fields = ['budget_head']


@admin.register(Voucher)
class VoucherAdmin(admin.ModelAdmin):
    """Admin configuration for Voucher model."""
    
    list_display = (
        'voucher_no', 'date', 'voucher_type', 'fund', 'organization',
        'total_debit', 'total_credit', 'is_balanced_display', 'is_posted'
    )
    list_filter = ('voucher_type', 'fund', 'is_posted', 'fiscal_year', 'organization')
    search_fields = ('voucher_no', 'description', 'organization__name')
    ordering = ('-date', '-voucher_no')
    readonly_fields = (
        'public_id', 'is_posted', 'posted_at', 'posted_by',
        'created_at', 'updated_at', 'created_by', 'updated_by',
        'total_debit', 'total_credit', 'is_balanced_display'
    )
    inlines = [JournalEntryInline]
    date_hierarchy = 'date'
    
    fieldsets = (
        (_('Voucher Details'), {
            'fields': ('organization', 'fiscal_year', 'voucher_no', 'date', 'voucher_type', 'fund')
        }),
        (_('Description'), {
            'fields': ('description',)
        }),
        (_('Balance Check'), {
            'fields': ('total_debit', 'total_credit', 'is_balanced_display'),
            'description': _('Voucher must be balanced (Debit = Credit) before posting.')
        }),
        (_('Posting Status'), {
            'fields': ('is_posted', 'posted_at', 'posted_by')
        }),
        (_('Audit Trail'), {
            'fields': ('public_id', 'created_at', 'updated_at', 'created_by', 'updated_by'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['post_selected_vouchers', 'unpost_selected_vouchers']
    
    def total_debit(self, obj):
        """Display total debit amount."""
        return f"PKR {obj.get_total_debit():,.2f}"
    total_debit.short_description = _('Total Debit')
    
    def total_credit(self, obj):
        """Display total credit amount."""
        return f"PKR {obj.get_total_credit():,.2f}"
    total_credit.short_description = _('Total Credit')
    
    def is_balanced_display(self, obj):
        """Display whether voucher is balanced."""
        if obj.is_balanced():
            return '✓ Balanced'
        return '✗ Not Balanced'
    is_balanced_display.short_description = _('Balance Status')
    is_balanced_display.boolean = True
    
    def post_selected_vouchers(self, request, queryset):
        """Admin action to post selected vouchers."""
        posted_count = 0
        error_count = 0
        
        for voucher in queryset:
            try:
                if voucher.can_post():
                    voucher.post_voucher(request.user)
                    posted_count += 1
                else:
                    error_count += 1
            except Exception as e:
                error_count += 1
                self.message_user(request, f"Error posting {voucher.voucher_no}: {str(e)}", level='error')
        
        if posted_count:
            self.message_user(request, f"Successfully posted {posted_count} voucher(s).", level='success')
        if error_count:
            self.message_user(request, f"Failed to post {error_count} voucher(s).", level='warning')
    
    post_selected_vouchers.short_description = _('Post selected vouchers')
    
    def unpost_selected_vouchers(self, request, queryset):
        """Admin action to unpost selected vouchers."""
        unposted_count = 0
        
        for voucher in queryset.filter(is_posted=True):
            try:
                voucher.unpost_voucher()
                unposted_count += 1
            except Exception as e:
                self.message_user(request, f"Error unposting {voucher.voucher_no}: {str(e)}", level='error')
        
        if unposted_count:
            self.message_user(request, f"Successfully unposted {unposted_count} voucher(s).", level='success')
    
    unpost_selected_vouchers.short_description = _('Unpost selected vouchers')
    
    def save_model(self, request, obj, form, change):
        """Override to set audit fields."""
        if not change:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(JournalEntry)
class JournalEntryAdmin(admin.ModelAdmin):
    """Admin configuration for JournalEntry model."""
    
    list_display = ('voucher', 'budget_head', 'description', 'debit', 'credit', 'entry_type')
    list_filter = ('voucher__voucher_type', 'voucher__is_posted', 'voucher__fiscal_year')
    search_fields = ('description', 'voucher__voucher_no', 'budget_head__tma_sub_object')
    ordering = ('-voucher__date', 'voucher', 'id')
    readonly_fields = ('public_id', 'created_at', 'updated_at')
    
    def entry_type(self, obj):
        """Display entry type (Debit or Credit)."""
        if obj.debit > 0:
            return f'Dr {obj.debit:,.2f}'
        return f'Cr {obj.credit:,.2f}'
    entry_type.short_description = _('Entry Type')

