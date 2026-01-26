"""
-------------------------------------------------------------------------
System: KP-CFMS (Computerized Financial Management System)
Client: Local Government Department, Khyber Pakhtunkhwa
Team Lead: Jamil Shah
Developers: Ali Asghar, Akhtar Munir and Zarif Khan
Description: Django admin configuration for the budgeting module.
-------------------------------------------------------------------------
"""
from decimal import Decimal
from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.db.models import Sum

from apps.budgeting.models import (
    FiscalYear, BudgetAllocation, ScheduleOfEstablishment,
    QuarterlyRelease, SAERecord, BudgetStatus,
    DesignationMaster, BPSSalaryScale
)
from apps.budgeting.models_employee import BudgetEmployee


class BudgetEmployeeInline(admin.TabularInline):
    """Inline admin for managing employees within ScheduleOfEstablishment."""
    model = BudgetEmployee
    extra = 0
    fields = ['name', 'personnel_number', 'current_basic_pay', 'monthly_allowances', 'annual_increment_amount', 'is_vacant']
    readonly_fields = []
    
    def get_queryset(self, request):
        return super().get_queryset(request).filter(is_vacant=False)


@admin.register(FiscalYear)
class FiscalYearAdmin(admin.ModelAdmin):
    """
    Admin configuration for FiscalYear model.
    """
    
    list_display = [
        'year_name', 'start_date', 'end_date', 
        'status_badge', 'is_active', 'is_locked', 'sae_number'
    ]
    list_filter = ['status', 'is_active', 'is_locked']
    search_fields = ['year_name', 'sae_number']
    readonly_fields = [
        'sae_number', 'sae_generated_at', 'created_at', 
        'updated_at', 'created_by', 'updated_by'
    ]
    ordering = ['-start_date']
    
    fieldsets = (
        (None, {
            'fields': ('year_name', 'start_date', 'end_date')
        }),
        (_('Status'), {
            'fields': ('status', 'is_active', 'is_locked')
        }),
        (_('SAE Information'), {
            'fields': ('sae_number', 'sae_generated_at'),
            'classes': ('collapse',)
        }),
        (_('Audit Trail'), {
            'fields': ('created_at', 'updated_at', 'created_by', 'updated_by'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['activate_budget_entry', 'deactivate_budget_entry']
    
    def status_badge(self, obj: FiscalYear) -> str:
        """Display status as a colored badge."""
        color_map = {
            BudgetStatus.DRAFT: 'secondary',
            BudgetStatus.SUBMITTED: 'info',
            BudgetStatus.VERIFIED: 'warning',
            BudgetStatus.APPROVED: 'primary',
            BudgetStatus.LOCKED: 'success',
        }
        color = color_map.get(obj.status, 'secondary')
        return format_html(
            '<span class="badge bg-{}">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = _('Status')
    
    @admin.action(description=_('Activate budget entry window'))
    def activate_budget_entry(self, request, queryset):
        """Activate budget entry for selected fiscal years."""
        count = queryset.filter(is_locked=False).update(is_active=True)
        self.message_user(request, f'{count} fiscal year(s) activated.')
    
    @admin.action(description=_('Deactivate budget entry window'))
    def deactivate_budget_entry(self, request, queryset):
        """Deactivate budget entry for selected fiscal years."""
        count = queryset.update(is_active=False)
        self.message_user(request, f'{count} fiscal year(s) deactivated.')
    
    def save_model(self, request, obj, form, change):
        """Track created_by and updated_by."""
        if not change:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(BudgetAllocation)
class BudgetAllocationAdmin(admin.ModelAdmin):
    """
    Admin configuration for BudgetAllocation model.
    """
    
    list_display = [
        'budget_head', 'fiscal_year', 'original_allocation_display',
        'released_display', 'spent_display', 'available_display'
    ]
    list_filter = [
        'fiscal_year', 'budget_head__account_type', 
        'budget_head__fund_type'
    ]
    search_fields = [
        'budget_head__tma_sub_object', 'budget_head__tma_description'
    ]
    readonly_fields = [
        'spent_amount', 'created_at', 'updated_at', 
        'created_by', 'updated_by'
    ]
    autocomplete_fields = ['budget_head']
    ordering = ['fiscal_year', 'budget_head__pifra_object']
    
    fieldsets = (
        (None, {
            'fields': ('fiscal_year', 'budget_head')
        }),
        (_('Allocations'), {
            'fields': (
                'original_allocation', 'revised_allocation', 
                'released_amount', 'spent_amount'
            )
        }),
        (_('Comparison Data'), {
            'fields': ('previous_year_actual', 'current_year_budget'),
            'classes': ('collapse',)
        }),
        (_('Notes'), {
            'fields': ('remarks',),
            'classes': ('collapse',)
        }),
        (_('Audit Trail'), {
            'fields': ('created_at', 'updated_at', 'created_by', 'updated_by'),
            'classes': ('collapse',)
        }),
    )
    
    def original_allocation_display(self, obj: BudgetAllocation) -> str:
        """Format allocation amount."""
        return f"Rs {obj.original_allocation:,.2f}"
    original_allocation_display.short_description = _('Original')
    
    def released_display(self, obj: BudgetAllocation) -> str:
        """Format released amount."""
        return f"Rs {obj.released_amount:,.2f}"
    released_display.short_description = _('Released')
    
    def spent_display(self, obj: BudgetAllocation) -> str:
        """Format spent amount."""
        return f"Rs {obj.spent_amount:,.2f}"
    spent_display.short_description = _('Spent')
    
    def available_display(self, obj: BudgetAllocation) -> str:
        """Format available budget with color coding."""
        available = obj.get_available_budget()
        color = 'green' if available > Decimal('0') else 'red'
        return format_html(
            '<span style="color: {}">{:,.2f}</span>',
            color, available
        )
    available_display.short_description = _('Available')
    
    def save_model(self, request, obj, form, change):
        """Track created_by and updated_by."""
        if not change:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(ScheduleOfEstablishment)
class ScheduleOfEstablishmentAdmin(admin.ModelAdmin):
    """
    Admin configuration for ScheduleOfEstablishment model.
    """
    
    list_display = [
        'designation_name', 'department', 'bps_scale', 
        'sanctioned_posts', 'occupied_posts', 'vacant_display',
        'employee_count_display', 'estimated_budget_display',
        'post_type', 'approval_status'
    ]
    list_filter = ['fiscal_year', 'department', 'bps_scale', 'post_type', 'approval_status']
    search_fields = ['designation_name', 'department']
    autocomplete_fields = ['budget_head']
    ordering = ['fiscal_year', 'department', '-bps_scale']
    inlines = [BudgetEmployeeInline]
    
    fieldsets = (
        (None, {
            'fields': ('fiscal_year', 'department', 'designation_name', 'bps_scale', 'post_type')
        }),
        (_('Posts'), {
            'fields': ('sanctioned_posts', 'occupied_posts')
        }),
        (_('Budget Estimation'), {
            'fields': ('estimated_budget', 'annual_salary', 'budget_head'),
            'description': _('Use the Employees inline below to add actual staff data for precise budget calculation.')
        }),
        (_('Approval'), {
            'fields': ('approval_status', 'recommended_by', 'recommended_at', 'approved_by', 'approved_at', 'rejection_reason'),
            'classes': ('collapse',)
        }),
        (_('Audit Trail'), {
            'fields': ('created_at', 'updated_at', 'created_by', 'updated_by'),
            'classes': ('collapse',)
        }),
    )
    readonly_fields = ['created_at', 'updated_at', 'created_by', 'updated_by', 'recommended_at', 'approved_at']
    
    actions = ['recalculate_budget']
    
    def vacant_display(self, obj: ScheduleOfEstablishment) -> str:
        """Display vacant posts with color coding."""
        vacant = obj.vacant_posts
        color = 'orange' if vacant > 0 else 'green'
        return format_html('<span style="color: {}">{}</span>', color, vacant)
    vacant_display.short_description = _('Vacant')
    
    def employee_count_display(self, obj: ScheduleOfEstablishment) -> str:
        """Display count of linked employees."""
        count = obj.employees.filter(is_vacant=False).count()
        return f"{count} emp"
    employee_count_display.short_description = _('Employees')
    
    def estimated_budget_display(self, obj: ScheduleOfEstablishment) -> str:
        """Format estimated budget."""
        return f"Rs {obj.estimated_budget:,.0f}"
    estimated_budget_display.short_description = _('Est. Budget')
    
    @admin.action(description=_('Recalculate budget from employees'))
    def recalculate_budget(self, request, queryset):
        """Recalculate budget for selected establishment entries."""
        for entry in queryset:
            result = entry.calculate_total_budget_requirement()
            self.message_user(
                request, 
                f'{entry.designation_name}: Rs {result["total_cost"]:,.2f} '
                f'(Filled: {result["filled_count"]}, Vacant: {result["vacant_count"]})'
            )
    
    def save_model(self, request, obj, form, change):
        """Track created_by and updated_by."""
        if not change:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(QuarterlyRelease)
class QuarterlyReleaseAdmin(admin.ModelAdmin):
    """
    Admin configuration for QuarterlyRelease model.
    """
    
    list_display = [
        'fiscal_year', 'quarter', 'release_date', 
        'release_status', 'total_amount_display'
    ]
    list_filter = ['fiscal_year', 'quarter', 'is_released']
    readonly_fields = [
        'total_amount', 'created_at', 'updated_at', 
        'created_by', 'updated_by'
    ]
    ordering = ['fiscal_year', 'quarter']
    
    def release_status(self, obj: QuarterlyRelease) -> str:
        """Display release status as badge."""
        if obj.is_released:
            return format_html(
                '<span class="badge bg-success">Released</span>'
            )
        return format_html(
            '<span class="badge bg-warning">Pending</span>'
        )
    release_status.short_description = _('Status')
    
    def total_amount_display(self, obj: QuarterlyRelease) -> str:
        """Format total amount."""
        return f"Rs {obj.total_amount:,.2f}"
    total_amount_display.short_description = _('Total Released')


@admin.register(SAERecord)
class SAERecordAdmin(admin.ModelAdmin):
    """
    Admin configuration for SAERecord model.
    """
    
    list_display = [
        'sae_number', 'fiscal_year', 'total_receipts_display',
        'total_expenditure_display', 'surplus_deficit_display',
        'approved_by', 'is_authenticated'
    ]
    list_filter = ['is_authenticated', 'approval_date']
    search_fields = ['sae_number', 'fiscal_year__year_name']
    readonly_fields = [
        'sae_number', 'fiscal_year', 'total_receipts', 
        'total_expenditure', 'contingency_reserve', 
        'approved_by', 'approval_date', 'created_at', 'updated_at'
    ]
    ordering = ['-approval_date']
    
    def total_receipts_display(self, obj: SAERecord) -> str:
        """Format total receipts."""
        return f"Rs {obj.total_receipts:,.2f}"
    total_receipts_display.short_description = _('Receipts')
    
    def total_expenditure_display(self, obj: SAERecord) -> str:
        """Format total expenditure."""
        return f"Rs {obj.total_expenditure:,.2f}"
    total_expenditure_display.short_description = _('Expenditure')
    
    def surplus_deficit_display(self, obj: SAERecord) -> str:
        """Display surplus/deficit with color coding."""
        amount = obj.get_surplus_deficit()
        color = 'green' if amount >= Decimal('0') else 'red'
        label = 'Surplus' if amount >= Decimal('0') else 'Deficit'
        return format_html(
            '<span style="color: {}">{}: Rs {:,.2f}</span>',
            color, label, abs(amount)
        )
    surplus_deficit_display.short_description = _('Balance')
    
    def has_add_permission(self, request):
        """SAE records are created automatically, not manually."""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """SAE records cannot be deleted (immutable)."""
        return False


@admin.register(DesignationMaster)
class DesignationMasterAdmin(admin.ModelAdmin):
    """
    Admin configuration for DesignationMaster model.
    """
    
    list_display = ['name', 'bps_scale', 'post_type', 'is_active']
    list_filter = ['bps_scale', 'post_type', 'is_active']
    search_fields = ['name']
    ordering = ['name']


@admin.register(BPSSalaryScale)
class BPSSalaryScaleAdmin(admin.ModelAdmin):
    # 1. The Columns to Show
    list_display = (
        'bps_grade', 
        'basic_pay_min', 
        'annual_increment', 
        'conveyance_allowance', 
        'medical_allowance', 
        'house_rent_percent',
        'adhoc_relief_total_percent',
        'estimated_gross_view'  # Calculated field
    )

    # 2. The "Excel-Style" Editing
    list_editable = (
        'basic_pay_min', 
        'annual_increment', 
        'conveyance_allowance', 
        'medical_allowance',
        'house_rent_percent',
        'adhoc_relief_total_percent'
    )

    # 3. Sorting & Filtering
    ordering = ('bps_grade',)
    search_fields = ('bps_grade',)

    # 4. Custom Column for "Total Estimated"
    @admin.display(description='Est. Gross (Stage 0)')
    def estimated_gross_view(self, obj):
        return f"Rs {obj.estimated_gross_salary:,.0f}"

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['title'] = "Manage BPS Salary Chart (Update from Finance Notification)"
        return super().changelist_view(request, extra_context=extra_context)

