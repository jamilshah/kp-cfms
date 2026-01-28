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

from .models import (
    FunctionCode, BudgetHead, Fund, Voucher, JournalEntry, 
    ChequeBook, ChequeLeaf, BankStatement, BankStatementLine
)


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


class ChequeLeafInline(admin.TabularInline):
    """Inline admin for ChequeLeaf within ChequeBook."""
    
    model = ChequeLeaf
    extra = 0
    readonly_fields = ('leaf_number', 'status', 'void_reason', 'used_at')
    can_delete = False
    
    def has_add_permission(self, request, obj=None):
        return False


@admin.register(ChequeBook)
class ChequeBookAdmin(admin.ModelAdmin):
    """Admin configuration for ChequeBook model."""
    
    list_display = (
        'book_no', 'bank_account', 'prefix', 'start_serial', 'end_serial',
        'issue_date', 'total_leaves', 'available_count', 'is_active'
    )
    list_filter = ('is_active', 'bank_account__organization', 'issue_date')
    search_fields = ('book_no', 'bank_account__title', 'bank_account__account_number')
    ordering = ('-issue_date', 'book_no')
    date_hierarchy = 'issue_date'
    inlines = [ChequeLeafInline]
    
    readonly_fields = ('created_at', 'updated_at', 'created_by', 'updated_by')
    
    fieldsets = (
        (None, {
            'fields': ('bank_account', 'book_no', 'prefix')
        }),
        (_('Serial Range'), {
            'fields': ('start_serial', 'end_serial', 'issue_date')
        }),
        (_('Status'), {
            'fields': ('is_active',)
        }),
        (_('Audit Trail'), {
            'fields': ('created_at', 'updated_at', 'created_by', 'updated_by'),
            'classes': ('collapse',)
        }),
    )
    
    def total_leaves(self, obj):
        return obj.total_leaves
    total_leaves.short_description = _('Total')
    
    def available_count(self, obj):
        return obj.available_count
    available_count.short_description = _('Available')


@admin.register(ChequeLeaf)
class ChequeLeafAdmin(admin.ModelAdmin):
    """Admin configuration for ChequeLeaf model."""
    
    list_display = ('leaf_number', 'book', 'status', 'used_at')
    list_filter = ('status', 'book__bank_account')
    search_fields = ('leaf_number', 'book__book_no')
    ordering = ('book', 'id')
    readonly_fields = ('book', 'leaf_number', 'used_at', 'created_at', 'updated_at')
    
    fieldsets = (
        (None, {
            'fields': ('book', 'leaf_number', 'status')
        }),
        (_('Void Information'), {
            'fields': ('void_reason', 'used_at'),
            'classes': ('collapse',)
        }),
    )


# ============================================================================
# Bank Statement & Reconciliation Admin
# ============================================================================

class BankStatementLineInline(admin.TabularInline):
    """Inline admin for BankStatementLine within BankStatement."""
    
    model = BankStatementLine
    extra = 0
    readonly_fields = ('is_reconciled', 'matched_entry')
    fields = ('date', 'description', 'debit', 'credit', 'ref_no', 'balance', 'is_reconciled', 'matched_entry')


@admin.register(BankStatement)
class BankStatementAdmin(admin.ModelAdmin):
    """Admin configuration for BankStatement model."""
    
    list_display = (
        'bank_account', 'month_name', 'year', 'opening_balance', 'closing_balance',
        'total_lines', 'reconciled_count', 'status', 'is_locked'
    )
    list_filter = ('status', 'is_locked', 'bank_account__organization', 'year', 'month')
    search_fields = ('bank_account__title', 'bank_account__account_number', 'notes')
    ordering = ('-year__start_date', '-month')
    date_hierarchy = 'created_at'
    inlines = [BankStatementLineInline]
    
    readonly_fields = ('created_at', 'updated_at', 'created_by', 'updated_by')
    
    fieldsets = (
        (None, {
            'fields': ('bank_account', 'month', 'year')
        }),
        (_('Balances'), {
            'fields': ('opening_balance', 'closing_balance')
        }),
        (_('Status'), {
            'fields': ('status', 'is_locked')
        }),
        (_('Files & Notes'), {
            'fields': ('file', 'notes'),
            'classes': ('collapse',)
        }),
        (_('Audit Trail'), {
            'fields': ('created_at', 'updated_at', 'created_by', 'updated_by'),
            'classes': ('collapse',)
        }),
    )
    
    def month_name(self, obj):
        month_names = [
            'January', 'February', 'March', 'April', 'May', 'June',
            'July', 'August', 'September', 'October', 'November', 'December'
        ]
        return month_names[obj.month - 1]
    month_name.short_description = _('Month')
    
    def total_lines(self, obj):
        return obj.lines.count()
    total_lines.short_description = _('Lines')


@admin.register(BankStatementLine)
class BankStatementLineAdmin(admin.ModelAdmin):
    """Admin configuration for BankStatementLine model."""
    
    list_display = ('statement', 'date', 'description_short', 'debit', 'credit', 'ref_no', 'is_reconciled')
    list_filter = ('is_reconciled', 'statement__bank_account', 'statement__year')
    search_fields = ('description', 'ref_no', 'statement__bank_account__title')
    ordering = ('-statement__year__start_date', '-statement__month', 'date', 'id')
    readonly_fields = ('is_reconciled', 'matched_entry', 'created_at', 'updated_at')
    
    fieldsets = (
        (None, {
            'fields': ('statement', 'date', 'description')
        }),
        (_('Amounts'), {
            'fields': ('debit', 'credit', 'balance', 'ref_no')
        }),
        (_('Reconciliation'), {
            'fields': ('is_reconciled', 'matched_entry'),
            'classes': ('collapse',)
        }),
    )
    
    def description_short(self, obj):
        """Truncate description for display."""
        if len(obj.description) > 40:
            return f'{obj.description[:40]}...'
        return obj.description
    description_short.short_description = _('Description')


