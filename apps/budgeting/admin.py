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
from django.contrib import admin, messages
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.db.models import Sum

from apps.budgeting.models import (
    FiscalYear, BudgetAllocation, ScheduleOfEstablishment,
    QuarterlyRelease, SAERecord, BudgetStatus,
    DesignationMaster, BPSSalaryScale, Department,
    # Phase 3: Pension & Budget Execution
    PensionEstimate, RetiringEmployee, PensionEstimateStatus,
    SupplementaryGrant, SupplementaryGrantStatus,
    Reappropriation, ReappropriationStatus,
)
from apps.budgeting.models_employee import BudgetEmployee


class BudgetEmployeeInline(admin.TabularInline):
    """Inline admin for managing employees within ScheduleOfEstablishment."""
    model = BudgetEmployee
    extra = 0
    fields = ['name', 'father_name', 'designation', 'bps', 'running_basic', 'city_category', 'is_vacant']
    readonly_fields = []
    
    def get_queryset(self, request):
        return super().get_queryset(request).filter(is_vacant=False)


@admin.register(FiscalYear)
class FiscalYearAdmin(admin.ModelAdmin):
    """
    Admin configuration for GLOBAL FiscalYear model (LCB Admin only).
    """
    
    list_display = [
        'year_name', 'start_date', 'end_date', 
        'planning_status_badge', 'revision_status_badge'
    ]
    list_filter = ['is_planning_active', 'is_revision_active']
    search_fields = ['year_name']
    readonly_fields = [
        'created_at', 'updated_at', 'created_by', 'updated_by'
    ]
    ordering = ['-start_date']
    
    fieldsets = (
        (None, {
            'fields': ('year_name', 'start_date', 'end_date')
        }),
        (_('Planning Windows'), {
            'fields': ('is_planning_active', 'is_revision_active'),
            'description': _('Control when TMAs can create/edit budget proposals.')
        }),
        (_('Audit Trail'), {
            'fields': ('created_at', 'updated_at', 'created_by', 'updated_by'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['open_planning_window', 'close_planning_window', 'open_revision_window', 'close_revision_window']
    
    def planning_status_badge(self, obj: FiscalYear) -> str:
        """Display planning window status as a colored badge."""
        if obj.is_planning_active:
            return format_html('<span class="badge bg-success">Planning Open</span>')
        return format_html('<span class="badge bg-secondary">Planning Closed</span>')
    planning_status_badge.short_description = _('Planning Window')
    
    def revision_status_badge(self, obj: FiscalYear) -> str:
        """Display revision window status as a colored badge."""
        if obj.is_revision_active:
            return format_html('<span class="badge bg-warning">Revision Open</span>')
        return format_html('<span class="badge bg-secondary">Revision Closed</span>')
    revision_status_badge.short_description = _('Revision Window')
    
    @admin.action(description=_('Open planning window (May-June)'))
    def open_planning_window(self, request, queryset):
        """Open planning window for selected fiscal years."""
        count = queryset.update(is_planning_active=True)
        self.message_user(request, f'{count} fiscal year(s) planning window opened.')
    
    @admin.action(description=_('Close planning window'))
    def close_planning_window(self, request, queryset):
        """Close planning window for selected fiscal years."""
        count = queryset.update(is_planning_active=False)
        self.message_user(request, f'{count} fiscal year(s) planning window closed.')
    
    @admin.action(description=_('Open revision window (March)'))
    def open_revision_window(self, request, queryset):
        """Open revision window for selected fiscal years."""
        count = queryset.update(is_revision_active=True)
        self.message_user(request, f'{count} fiscal year(s) revision window opened.')
    
    @admin.action(description=_('Close revision window'))
    def close_revision_window(self, request, queryset):
        """Close revision window for selected fiscal years."""
        count = queryset.update(is_revision_active=False)
        self.message_user(request, f'{count} fiscal year(s) revision window closed.')
    
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
        'fiscal_year', 'budget_head__fund'
        # TODO: Add account_type filter after implementing custom filter for nam_head/sub_head
    ]
    search_fields = [
        # TODO: Add code/name search after implementing custom search for nam_head/sub_head
    ]
    readonly_fields = [
        'spent_amount', 'created_at', 'updated_at', 
        'created_by', 'updated_by'
    ]
    autocomplete_fields = ['budget_head']
    ordering = ['fiscal_year']
    # TODO: Add ordering by code after implementing custom ordering for nam_head/sub_head
    
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
        'house_rent_large_cities',
        'house_rent_other_cities',
        'adhoc_relief_percent',
        'estimated_gross_view'  # Calculated field
    )

    # 2. The "Excel-Style" Editing
    list_editable = (
        'basic_pay_min', 
        'annual_increment', 
        'conveyance_allowance', 
        'medical_allowance',
        'house_rent_large_cities',
        'house_rent_other_cities',
        'adhoc_relief_percent'
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


# =============================================================================
# Phase 3: Pension & Budget Execution Admin
# =============================================================================

class RetiringEmployeeInline(admin.TabularInline):
    """Inline admin for managing retiring employees within PensionEstimate."""
    model = RetiringEmployee
    extra = 1
    fields = ['name', 'designation', 'retirement_date', 'monthly_pension_amount', 'commutation_amount', 'remarks']


@admin.register(PensionEstimate)
class PensionEstimateAdmin(admin.ModelAdmin):
    """
    Admin configuration for PensionEstimate model.
    """
    
    list_display = [
        'fiscal_year', 'current_monthly_bill_display', 'expected_increase',
        'estimated_pension_display', 'estimated_commutation_display',
        'status_badge', 'retirees_count'
    ]
    list_filter = ['fiscal_year', 'status']
    readonly_fields = [
        'estimated_monthly_pension', 'estimated_commutation',
        'locked_at', 'locked_by',
        'created_at', 'updated_at', 'created_by', 'updated_by'
    ]
    ordering = ['-fiscal_year__start_date']
    inlines = [RetiringEmployeeInline]
    
    fieldsets = (
        (None, {
            'fields': ('fiscal_year', 'status')
        }),
        (_('Input Parameters'), {
            'fields': ('current_monthly_bill', 'expected_increase'),
            'description': _('Enter the current pension bill and expected increase percentage.')
        }),
        (_('Calculated Estimates'), {
            'fields': ('estimated_monthly_pension', 'estimated_commutation'),
            'classes': ('collapse',),
            'description': _('These are calculated when you run "Calculate & Lock".')
        }),
        (_('Lock Information'), {
            'fields': ('locked_at', 'locked_by'),
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
    
    actions = ['calculate_and_lock_action']
    
    def current_monthly_bill_display(self, obj: PensionEstimate) -> str:
        return f"Rs {obj.current_monthly_bill:,.2f}"
    current_monthly_bill_display.short_description = _('Monthly Bill')
    
    def estimated_pension_display(self, obj: PensionEstimate) -> str:
        return f"Rs {obj.estimated_monthly_pension:,.2f}"
    estimated_pension_display.short_description = _('Est. A04101')
    
    def estimated_commutation_display(self, obj: PensionEstimate) -> str:
        return f"Rs {obj.estimated_commutation:,.2f}"
    estimated_commutation_display.short_description = _('Est. A04102')
    
    def status_badge(self, obj: PensionEstimate) -> str:
        color = 'success' if obj.status == PensionEstimateStatus.LOCKED else 'secondary'
        return format_html(
            '<span class="badge bg-{}">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = _('Status')
    
    def retirees_count(self, obj: PensionEstimate) -> int:
        return obj.retiring_employees.count()
    retirees_count.short_description = _('Retirees')
    
    @admin.action(description=_('Calculate estimates & lock'))
    def calculate_and_lock_action(self, request, queryset):
        """Calculate pension estimates and lock selected entries."""
        for estimate in queryset.filter(status=PensionEstimateStatus.DRAFT):
            try:
                result = estimate.calculate_and_lock(user=request.user)
                self.message_user(
                    request,
                    f'{estimate}: A04101=Rs {result["monthly_pension"]:,.2f}, A04102=Rs {result["commutation"]:,.2f}',
                    messages.SUCCESS
                )
            except Exception as e:
                self.message_user(request, f'{estimate}: {str(e)}', messages.ERROR)
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(SupplementaryGrant)
class SupplementaryGrantAdmin(admin.ModelAdmin):
    """
    Admin configuration for SupplementaryGrant model.
    """
    
    list_display = [
        'reference_no', 'fiscal_year', 'budget_head',
        'amount_display', 'date', 'status_badge'
    ]
    list_filter = ['fiscal_year', 'status', 'date']
    search_fields = ['reference_no']
    # TODO: Add code/name search after implementing custom search for nam_head/sub_head
    autocomplete_fields = ['budget_head']
    readonly_fields = [
        'approved_by', 'approved_at',
        'created_at', 'updated_at', 'created_by', 'updated_by'
    ]
    ordering = ['-date']
    
    fieldsets = (
        (None, {
            'fields': ('fiscal_year', 'budget_head', 'status')
        }),
        (_('Grant Details'), {
            'fields': ('amount', 'reference_no', 'date', 'description')
        }),
        (_('Approval'), {
            'fields': ('approved_by', 'approved_at', 'rejection_reason'),
            'classes': ('collapse',)
        }),
        (_('Audit Trail'), {
            'fields': ('created_at', 'updated_at', 'created_by', 'updated_by'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['approve_grants', 'reject_grants']
    
    def amount_display(self, obj: SupplementaryGrant) -> str:
        return f"Rs {obj.amount:,.2f}"
    amount_display.short_description = _('Amount')
    
    def status_badge(self, obj: SupplementaryGrant) -> str:
        color_map = {
            SupplementaryGrantStatus.DRAFT: 'secondary',
            SupplementaryGrantStatus.APPROVED: 'success',
            SupplementaryGrantStatus.REJECTED: 'danger',
        }
        color = color_map.get(obj.status, 'secondary')
        return format_html(
            '<span class="badge bg-{}">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = _('Status')
    
    @admin.action(description=_('Approve selected grants'))
    def approve_grants(self, request, queryset):
        """Approve selected supplementary grants."""
        for grant in queryset.filter(status=SupplementaryGrantStatus.DRAFT):
            try:
                grant.approve(user=request.user)
                self.message_user(
                    request,
                    f'Approved: {grant.reference_no} - Rs {grant.amount:,.2f} added to {grant.budget_head}',
                    messages.SUCCESS
                )
            except Exception as e:
                self.message_user(request, f'{grant.reference_no}: {str(e)}', messages.ERROR)
    
    @admin.action(description=_('Reject selected grants'))
    def reject_grants(self, request, queryset):
        """Reject selected supplementary grants."""
        for grant in queryset.filter(status=SupplementaryGrantStatus.DRAFT):
            try:
                grant.reject(user=request.user, reason='Rejected via admin action')
                self.message_user(
                    request,
                    f'Rejected: {grant.reference_no}',
                    messages.WARNING
                )
            except Exception as e:
                self.message_user(request, f'{grant.reference_no}: {str(e)}', messages.ERROR)
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(Reappropriation)
class ReappropriationAdmin(admin.ModelAdmin):
    """
    Admin configuration for Reappropriation model.
    """
    
    list_display = [
        'reference_no', 'fiscal_year', 'from_head', 'to_head',
        'amount_display', 'date', 'status_badge'
    ]
    list_filter = ['fiscal_year', 'status', 'date']
    search_fields = [
        'reference_no', 
        # TODO: Add code/name search after implementing custom search for nam_head/sub_head
    ]
    autocomplete_fields = ['from_head', 'to_head']
    readonly_fields = [
        'approved_by', 'approved_at',
        'created_at', 'updated_at', 'created_by', 'updated_by'
    ]
    ordering = ['-date']
    
    fieldsets = (
        (None, {
            'fields': ('fiscal_year', 'status')
        }),
        (_('Transfer Details'), {
            'fields': ('from_head', 'to_head', 'amount', 'reference_no', 'date', 'description'),
            'description': _('Transfer budget from one head to another within the same Fund.')
        }),
        (_('Approval'), {
            'fields': ('approved_by', 'approved_at'),
            'classes': ('collapse',)
        }),
        (_('Audit Trail'), {
            'fields': ('created_at', 'updated_at', 'created_by', 'updated_by'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['approve_reappropriations']
    
    def amount_display(self, obj: Reappropriation) -> str:
        return f"Rs {obj.amount:,.2f}"
    amount_display.short_description = _('Amount')
    
    def status_badge(self, obj: Reappropriation) -> str:
        color = 'success' if obj.status == ReappropriationStatus.APPROVED else 'secondary'
        return format_html(
            '<span class="badge bg-{}">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = _('Status')
    
    @admin.action(description=_('Approve selected re-appropriations'))
    def approve_reappropriations(self, request, queryset):
        """Approve selected re-appropriations and transfer funds."""
        for reappropriation in queryset.filter(status=ReappropriationStatus.DRAFT):
            try:
                reappropriation.approve(user=request.user)
                self.message_user(
                    request,
                    f'Approved: {reappropriation.reference_no} - Rs {reappropriation.amount:,.2f} '
                    f'transferred from {reappropriation.from_head.code} to {reappropriation.to_head.code}',
                    messages.SUCCESS
                )
            except Exception as e:
                self.message_user(request, f'{reappropriation.reference_no}: {str(e)}', messages.ERROR)
    
        if not change:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    """
    Admin configuration for Department model.
    """
    
    list_display = ['name', 'code', 'get_related_functions', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'code']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['name']
    
    fieldsets = (
        (None, {
            'fields': ('name', 'code', 'related_functions', 'is_active')
        }),
        (_('Audit Info'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    filter_horizontal = ('related_functions',)
    
    def get_related_functions(self, obj):
        return ", ".join([f.code for f in obj.related_functions.all()])
    get_related_functions.short_description = 'Functions'
