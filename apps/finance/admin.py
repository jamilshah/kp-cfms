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
    ChequeBook, ChequeLeaf, BankStatement, BankStatementLine,
    MajorHead, MinorHead, GlobalHead, NAMHead, SubHead,
    DepartmentFunctionConfiguration,
    BudgetHeadFavorite, BudgetHeadUsageHistory
)


@admin.register(FunctionCode)
class FunctionCodeAdmin(admin.ModelAdmin):
    """Admin configuration for FunctionCode model."""
    
    list_display = ('code', 'name', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('code', 'name')
    ordering = ('code',)


@admin.register(MajorHead)
class MajorHeadAdmin(admin.ModelAdmin):
    """Admin configuration for MajorHead model (Master Data)."""
    
    list_display = ('code', 'name')
    search_fields = ('code', 'name')
    ordering = ('code',)


@admin.register(MinorHead)
class MinorHeadAdmin(admin.ModelAdmin):
    """Admin configuration for MinorHead model (Master Data)."""
    
    list_display = ('code', 'name', 'major')
    list_filter = ('major',)
    search_fields = ('code', 'name')
    ordering = ('code',)


@admin.register(GlobalHead)
class GlobalHeadAdmin(admin.ModelAdmin):
    """Admin configuration for GlobalHead model (Master Data)."""
    
    list_display = ('code', 'name', 'minor', 'account_type', 'scope', 'get_dept_display', 'system_code')
    list_filter = ('account_type', 'scope', 'system_code', 'minor__major', 'applicable_departments')
    search_fields = ('code', 'name')
    ordering = ('code',)
    readonly_fields = ('is_officer_related', 'major_code', 'major_name', 'get_applicable_departments_display')
    filter_horizontal = ('applicable_departments',)
    
    fieldsets = (
        (_('Identification'), {
            'fields': ('code', 'name', 'minor')
        }),
        (_('Classification'), {
            'fields': ('account_type', 'system_code')
        }),
        (_('Department Access Control'), {
            'fields': ('scope', 'applicable_departments'),
            'description': _('Control which departments can see this head. Universal heads appear for all departments.')
        }),
        (_('Hierarchy (Read-Only)'), {
            'fields': ('major_code', 'major_name', 'is_officer_related', 'get_applicable_departments_display'),
            'classes': ('collapse',)
        }),
    )
    
    def get_dept_display(self, obj):
        """Display applicable departments in list view."""
        if obj.scope == 'UNIVERSAL':
            return 'All'
        count = obj.applicable_departments.count()
        if count == 0:
            return '-'
        elif count <= 2:
            return ', '.join(obj.applicable_departments.values_list('code', flat=True))
        else:
            return f'{count} depts'
    get_dept_display.short_description = 'Departments'


@admin.register(NAMHead)
class NAMHeadAdmin(admin.ModelAdmin):
    """Admin configuration for NAMHead model (Level 4 - Official Reporting Head)."""
    
    list_display = ('code', 'name', 'minor', 'account_type', 'scope', 'has_sub_heads', 'allow_direct_posting', 'is_active')
    list_filter = ('account_type', 'scope', 'is_active', 'minor__major', 'applicable_departments')
    search_fields = ('code', 'name')
    ordering = ('code',)
    readonly_fields = ('has_sub_heads', 'major_code', 'major_name')
    filter_horizontal = ('applicable_departments', 'applicable_functions')
    
    fieldsets = (
        (_('Identification'), {
            'fields': ('code', 'name', 'minor')
        }),
        (_('Classification'), {
            'fields': ('account_type',)
        }),
        (_('Department-Function Access Control'), {
            'fields': ('scope', 'applicable_departments', 'applicable_functions'),
            'description': _('Control which departments and functions can use this head.')
        }),
        (_('Posting Control'), {
            'fields': ('allow_direct_posting', 'is_active'),
            'description': _('allow_direct_posting is auto-disabled when sub-heads are created.')
        }),
        (_('Hierarchy (Read-Only)'), {
            'fields': ('has_sub_heads', 'major_code', 'major_name'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['enable_posting', 'disable_posting', 'activate_heads', 'deactivate_heads']
    
    @admin.action(description='Enable direct posting for selected NAM heads')
    def enable_posting(self, request, queryset):
        """Enable posting only for NAM heads without sub-heads."""
        count = 0
        for obj in queryset:
            if not obj.has_sub_heads:
                obj.allow_direct_posting = True
                obj.save()
                count += 1
        self.message_user(request, f'Enabled posting for {count} NAM head(s) without sub-heads')
    
    @admin.action(description='Disable direct posting')
    def disable_posting(self, request, queryset):
        updated = queryset.update(allow_direct_posting=False)
        self.message_user(request, f'Disabled posting for {updated} NAM head(s)')
    
    @admin.action(description='Activate selected NAM heads')
    def activate_heads(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'Activated {updated} NAM head(s)')
    
    @admin.action(description='Deactivate selected NAM heads')
    def deactivate_heads(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'Deactivated {updated} NAM head(s)')


@admin.register(SubHead)
class SubHeadAdmin(admin.ModelAdmin):
    """Admin configuration for SubHead model (Level 5 - Internal Sub-Heads)."""
    
    list_display = ('get_code', 'name', 'nam_head', 'sub_code', 'is_active')
    list_filter = ('is_active', 'nam_head__minor__major', 'nam_head__account_type')
    search_fields = ('sub_code', 'name', 'nam_head__code', 'nam_head__name')
    ordering = ('nam_head__code', 'sub_code')
    readonly_fields = ('created_at', 'updated_at')
    autocomplete_fields = ['nam_head']
    
    fieldsets = (
        (_('Parent Head'), {
            'fields': ('nam_head',)
        }),
        (_('Sub-Head Details'), {
            'fields': ('sub_code', 'name', 'description')
        }),
        (_('Status'), {
            'fields': ('is_active',)
        }),
        (_('Audit'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_code(self, obj):
        return obj.code
    get_code.short_description = 'Full Code'
    
    actions = ['activate_subheads', 'deactivate_subheads']
    
    @admin.action(description='Activate selected sub-heads')
    def activate_subheads(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'Activated {updated} sub-head(s)')
    
    @admin.action(description='Deactivate selected sub-heads')
    def deactivate_subheads(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'Deactivated {updated} sub-head(s)')


@admin.register(DepartmentFunctionConfiguration)
class DepartmentFunctionConfigurationAdmin(admin.ModelAdmin):
    """Admin configuration for DepartmentFunctionConfiguration model."""
    
    list_display = ('department', 'function', 'get_head_count', 'get_completion_status', 'is_locked', 'updated_at')
    list_filter = ('is_locked', 'department', 'function')
    search_fields = ('department__name', 'function__code', 'function__name')
    ordering = ('department__name', 'function__code')
    filter_horizontal = ('allowed_nam_heads',)
    readonly_fields = ('get_head_count', 'get_completion_status', 'created_at', 'updated_at')
    actions = ['lock_configurations', 'unlock_configurations', 'export_configurations']
    
    fieldsets = (
        (_('Configuration'), {
            'fields': ('department', 'function', 'is_locked')
        }),
        (_('Allowed NAM Heads'), {
            'fields': ('allowed_nam_heads',),
            'description': _('Select which NAM heads are available for this department-function combination. '
                           'This is the ONLY access control mechanism.')
        }),
        (_('Additional Information'), {
            'fields': ('notes', 'get_head_count', 'get_completion_status'),
            'classes': ('collapse',)
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_head_count(self, obj):
        """Display count of allowed heads."""
        return obj.get_head_count()
    get_head_count.short_description = 'Head Count'
    
    def get_completion_status(self, obj):
        """Display completion status."""
        return obj.get_completion_status()
    get_completion_status.short_description = 'Status'
    
    @admin.action(description='Lock selected configurations')
    def lock_configurations(self, request, queryset):
        """Bulk lock configurations."""
        updated = queryset.update(is_locked=True)
        self.message_user(request, f'Locked {updated} configuration(s)')
    
    @admin.action(description='Unlock selected configurations')
    def unlock_configurations(self, request, queryset):
        """Bulk unlock configurations."""
        updated = queryset.update(is_locked=False)
        self.message_user(request, f'Unlocked {updated} configuration(s)')
    
    @admin.action(description='Export selected configurations to CSV')
    def export_configurations(self, request, queryset):
        """Export selected configurations to CSV."""
        import csv
        from django.http import HttpResponse
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="dept_func_configs.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Department Code', 'Department Name', 'Function Code', 'Function Name',
            'Allowed Global Heads', 'Head Count', 'Is Locked', 'Notes'
        ])
        
        for config in queryset.prefetch_related('allowed_global_heads'):
            head_codes = ', '.join(config.allowed_global_heads.values_list('code', flat=True))
            writer.writerow([
                config.department.code,
                config.department.name,
                config.function.code,
                config.function.name,
                head_codes,
                config.get_head_count(),
                'Yes' if config.is_locked else 'No',
                config.notes
            ])
        
        self.message_user(request, f'Exported {queryset.count()} configuration(s)')
        return response



@admin.register(BudgetHead)
class BudgetHeadAdmin(admin.ModelAdmin):
    """Admin configuration for BudgetHead model."""
    
    list_display = (
        'get_department', 'fund', 'get_function', 'get_code', 'get_name', 'get_level',
        'get_account_type', 'budget_control', 'posting_allowed', 'is_active'
    )
    list_filter = (
        'department', 'fund', 'function', 'budget_control', 'posting_allowed', 'is_active',
        'nam_head__account_type', 'sub_head__nam_head__account_type'
    )
    search_fields = (
        'nam_head__code', 'nam_head__name', 'sub_head__name', 'sub_head__sub_code',
        'department__name', 'department__code'
    )
    ordering = ('department__name', 'function__code', 'nam_head__code', 'sub_head__sub_code')
    actions = ['activate_heads', 'deactivate_heads', 'enable_posting', 'disable_posting']
    
    readonly_fields = ('created_at', 'updated_at', 'created_by', 'updated_by', 'get_hierarchy_path')
    autocomplete_fields = ['department', 'fund', 'function', 'nam_head', 'sub_head']
    
    fieldsets = (
        (_('Department & Classification'), {
            'fields': ('department', 'fund', 'function'),
            'description': _('Select department, fund, and function first.')
        }),
        (_('Account Head (Choose Either NAM or Sub-Head)'), {
            'fields': ('nam_head', 'sub_head'),
            'description': _('Link to EITHER a NAM Head (Level 4) OR a Sub-Head (Level 5), not both.')
        }),
        (_('Budget'), {
            'fields': ('current_budget',)
        }),
        (_('Control Flags'), {
            'fields': ('budget_control', 'project_required', 'posting_allowed', 'is_active')
        }),
        (_('Hierarchy Path'), {
            'fields': ('get_hierarchy_path',),
            'classes': ('collapse',)
        }),
        (_('Audit Trail'), {
            'fields': ('created_at', 'updated_at', 'created_by', 'updated_by'),
            'classes': ('collapse',)
        }),
    )
    
    def get_department(self, obj):
        return obj.department.code if obj.department else '-'
    get_department.short_description = 'Dept'
    get_department.admin_order_field = 'department__code'
    
    def get_function(self, obj):
        return obj.function.code if obj.function else '-'
    get_function.short_description = 'Func'
    get_function.admin_order_field = 'function__code'
    
    def get_code(self, obj):
        return obj.code  # Uses proxy property
    get_code.short_description = 'Code'
    
    def get_name(self, obj):
        return obj.name  # Uses proxy property
    get_name.short_description = 'Name'
    
    def get_level(self, obj):
        return f'L{obj.level}'
    get_level.short_description = 'Level'
    
    def get_account_type(self, obj):
        return obj.account_type
    get_account_type.short_description = 'Type'
    
    @admin.action(description='Activate selected budget heads')
    def activate_heads(self, request, queryset):
        """Bulk activate budget heads."""
        updated = queryset.update(is_active=True)
        self.message_user(request, f'Activated {updated} budget head(s)')
    
    @admin.action(description='Deactivate selected budget heads')
    def deactivate_heads(self, request, queryset):
        """Bulk deactivate budget heads."""
        updated = queryset.update(is_active=False)
        self.message_user(request, f'Deactivated {updated} budget head(s)')
    
    @admin.action(description='Enable posting for selected budget heads')
    def enable_posting(self, request, queryset):
        """Bulk enable posting."""
        updated = queryset.update(posting_allowed=True)
        self.message_user(request, f'Enabled posting for {updated} budget head(s)')
    
    @admin.action(description='Disable posting for selected budget heads')
    def disable_posting(self, request, queryset):
        """Bulk disable posting."""
        updated = queryset.update(posting_allowed=False)
        self.message_user(request, f'Disabled posting for {updated} budget head(s)')



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
    search_fields = ('description', 'voucher__voucher_no', 'budget_head__global_head__code')
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


@admin.register(BudgetHeadFavorite)
class BudgetHeadFavoriteAdmin(admin.ModelAdmin):
    """Admin configuration for BudgetHeadFavorite model."""
    
    list_display = ('user', 'budget_head', 'organization', 'created_at')
    list_filter = ('organization', 'created_at')
    search_fields = ('user__username', 'budget_head__global_head__code', 'budget_head__global_head__name')
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        (_('Favorite'), {
            'fields': ('user', 'budget_head', 'organization')
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(BudgetHeadUsageHistory)
class BudgetHeadUsageHistoryAdmin(admin.ModelAdmin):
    """Admin configuration for BudgetHeadUsageHistory model."""
    
    list_display = ('user', 'budget_head', 'organization', 'usage_count', 'last_used')
    list_filter = ('organization', 'last_used')
    search_fields = ('user__username', 'budget_head__global_head__code', 'budget_head__global_head__name')
    ordering = ('-last_used',)
    readonly_fields = ('created_at', 'updated_at', 'last_used')
    
    fieldsets = (
        (_('Usage'), {
            'fields': ('user', 'budget_head', 'organization', 'usage_count')
        }),
        (_('Timestamps'), {
            'fields': ('last_used', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


