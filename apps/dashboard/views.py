"""
-------------------------------------------------------------------------
System: KP-CFMS (Computerized Financial Management System)
Client: Local Government Department, Khyber Pakhtunkhwa
Team Lead: Jamil Shah
Developers: Ali Asghar, Akhtar Munir and Zarif Khan
Description: Dashboard views with caching for performance optimization
             and role-based workspaces.
-------------------------------------------------------------------------
"""
from decimal import Decimal
from typing import Dict, Any, Optional
from django.views.generic import TemplateView, RedirectView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.cache import cache
from django.utils import timezone
from django.shortcuts import redirect
from django.urls import reverse

from apps.budgeting.models import FiscalYear
from apps.core.models import Organization
from apps.dashboard.services import DashboardService


class ExecutiveDashboardView(LoginRequiredMixin, TemplateView):
    """
    Executive Dashboard view with KPIs and analytics.
    
    Features:
    - Role-based data filtering (TMO sees org data, LCB sees provincial)
    - 15-minute caching for performance
    - Chart.js visualizations
    - Auto-redirects LCB officers to provincial dashboard
    """
    
    template_name = 'dashboard/index.html'
    
    def dispatch(self, request, *args, **kwargs):
        """Auto-redirect LCB officers to provincial dashboard."""
        from django.shortcuts import redirect
        
        user = request.user
        
        # Redirect LCB officers to provincial dashboard
        if user.is_authenticated and (user.is_lcb_officer() or user.is_super_admin()):
            # Only redirect if they don't have an organization
            # (Super admins with org assignment can see TMA dashboard)
            if not user.organization:
                return redirect('dashboard:provincial')

        # Note: role-based workspace redirect is handled via
        # `DashboardRedirectView` at '/dashboard/workspace/'.
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        """Build dashboard context with cached data."""
        context = super().get_context_data(**kwargs)
        
        user = self.request.user
        
        # Determine organization context
        if user.organization:
            # TMO/Accountant: Show their organization only
            organization = user.organization
            context['is_provincial_view'] = False
            context['organization'] = organization
        else:
            # LCB/Admin: Show provincial summary
            organization = None
            context['is_provincial_view'] = True
            context['all_organizations'] = Organization.objects.filter(
                is_active=True,
                org_type__in=['TMA', 'TOWN']
            ).order_by('name')
        
        # Get current operating fiscal year
        if organization:
            fiscal_year = FiscalYear.get_current_operating_year(organization)
        else:
            # For provincial view, get any active fiscal year
            fiscal_year = FiscalYear.objects.filter(
                start_date__lte=timezone.now().date(),
                end_date__gte=timezone.now().date()
            ).first()
        
        if not fiscal_year:
            # No active fiscal year, show empty dashboard
            context['no_fiscal_year'] = True
            return context
        
        context['fiscal_year'] = fiscal_year
        
        # Build cache key
        org_id = organization.id if organization else 'provincial'
        cache_key = f'dashboard_stats_{org_id}_{fiscal_year.id}'
        
        # Try to get from cache
        cached_data = cache.get(cache_key)
        
        if cached_data:
            context.update(cached_data)
            context['from_cache'] = True
        else:
            # Calculate fresh data
            dashboard_data = self._calculate_dashboard_data(fiscal_year, organization)
            
            # Cache for 15 minutes (900 seconds)
            cache.set(cache_key, dashboard_data, 900)
            
            context.update(dashboard_data)
            context['from_cache'] = False
        
        return context
    
    def _calculate_dashboard_data(
        self,
        fiscal_year: FiscalYear,
        organization: Optional[Organization]
    ) -> Dict[str, Any]:
        """
        Calculate all dashboard metrics.
        
        Args:
            fiscal_year: The fiscal year to analyze.
            organization: The organization (None for provincial).
            
        Returns:
            Dictionary with all dashboard data.
        """
        service = DashboardService()
        
        # Budget Summary
        budget_summary = service.get_budget_summary(fiscal_year, organization)
        
        # Revenue Summary
        revenue_summary = service.get_revenue_summary(fiscal_year, organization)
        
        # Cash Position
        cash_position = service.get_cash_position(organization)
        
        # Pending Liabilities
        pending_liabilities = service.get_pending_liabilities(organization)
        
        # Top Expenditure Heads (for chart)
        top_expenditure = service.get_top_expenditure_heads(fiscal_year, organization, limit=5)
        
        # Budget Alerts (heads near exhaustion)
        budget_alerts = service.get_budget_alerts(fiscal_year, organization)
        
        return {
            'budget_summary': budget_summary,
            'revenue_summary': revenue_summary,
            'cash_position': cash_position,
            'pending_liabilities': pending_liabilities,
            'top_expenditure': top_expenditure,
            'budget_alerts': budget_alerts,
        }


class ProvincialDashboardView(LoginRequiredMixin, TemplateView):
    """
    Provincial (LCB) Dashboard for macro-level analytics.
    
    Features:
    - Strict access control (LCB_OFFICER, SUPER_ADMIN only)
    - Cross-TMA aggregation
    - Geographic filtering (Division/District)
    - 1-hour caching with manual refresh
    - Performance rankings and alerts
    """
    
    template_name = 'dashboard/provincial_index.html'
    
    def dispatch(self, request, *args, **kwargs):
        """Enforce strict role-based access control."""
        user = request.user
        
        # Check if user has LCB/Admin access
        if not (user.is_lcb_officer() or user.is_super_admin()):
            from django.contrib import messages
            from django.shortcuts import redirect
            messages.error(request, 'Access Denied: Provincial Dashboard requires LCB Officer or Super Admin role.')
            return redirect('dashboard:index')
        
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        """Build provincial dashboard context with cached data."""
        context = super().get_context_data(**kwargs)
        
        from apps.core.models import Division, District
        
        # Get filter parameters
        division_id = self.request.GET.get('division')
        district_id = self.request.GET.get('district')
        force_refresh = self.request.GET.get('refresh') == '1'
        
        division = None
        district = None
        
        if district_id:
            try:
                district = District.objects.get(id=district_id)
                division = district.division  # Auto-set division from district
            except District.DoesNotExist:
                pass
        elif division_id:
            try:
                division = Division.objects.get(id=division_id)
            except Division.DoesNotExist:
                pass
        
        # Add filter options to context
        context['divisions'] = Division.objects.all().order_by('name')
        context['districts'] = District.objects.all().order_by('name')
        context['selected_division'] = division
        context['selected_district'] = district
        
        # Get current fiscal year
        fiscal_year = FiscalYear.objects.filter(
            start_date__lte=timezone.now().date(),
            end_date__gte=timezone.now().date()
        ).first()
        
        if not fiscal_year:
            context['no_fiscal_year'] = True
            return context
        
        context['fiscal_year'] = fiscal_year
        
        # Build cache key based on filters
        filter_key = f"{division.id if division else 'all'}_{district.id if district else 'all'}"
        cache_key = f'provincial_stats_{fiscal_year.id}_{filter_key}'
        
        # Check cache (unless force refresh)
        if not force_refresh:
            cached_data = cache.get(cache_key)
            if cached_data:
                context.update(cached_data)
                context['from_cache'] = True
                return context
        
        # Calculate fresh data
        provincial_data = self._calculate_provincial_data(fiscal_year, division, district)
        
        # Cache for 1 hour (3600 seconds)
        cache.set(cache_key, provincial_data, 3600)
        
        context.update(provincial_data)
        context['from_cache'] = False
        
        return context
    
    def _calculate_provincial_data(
        self,
        fiscal_year: FiscalYear,
        division: Optional['Division'] = None,
        district: Optional['District'] = None
    ) -> Dict[str, Any]:
        """
        Calculate all provincial dashboard metrics.
        
        Args:
            fiscal_year: The fiscal year to analyze.
            division: Optional division filter.
            district: Optional district filter.
            
        Returns:
            Dictionary with all provincial dashboard data.
        """
        from apps.dashboard.services_provincial import ProvincialAnalyticsService
        
        service = ProvincialAnalyticsService()
        
        # Provincial totals
        provincial_totals = service.get_provincial_totals(fiscal_year, division, district)
        
        # TMA performance ranking
        performance_ranking = service.get_tma_performance_ranking(fiscal_year, division, district)
        
        # Expense composition
        expense_composition = service.get_expense_composition(fiscal_year, division, district)
        
        # Deficit TMAs
        deficit_tmas = service.get_deficit_tmas(fiscal_year, division, district)
        
        # Low utilization TMAs
        low_utilization_tmas = service.get_low_utilization_tmas(fiscal_year, Decimal('10.00'), division, district)
        
        return {
            'provincial_totals': provincial_totals,
            'top_performers': performance_ranking['top_performers'],
            'laggards': performance_ranking['laggards'],
            'expense_composition': expense_composition,
            'deficit_tmas': deficit_tmas,
            'low_utilization_tmas': low_utilization_tmas,
        }


# =====================================================================
# ROLE-BASED WORKSPACE VIEWS
# =====================================================================

class DashboardRedirectView(LoginRequiredMixin, RedirectView):
    """
    Central redirect view that routes users to their role-specific workspace.
    
    Based on user's primary role:
    - Finance Officer / Accountant -> Finance Workspace
    - Dealing Assistant -> Maker Workspace  
    - TMO -> PAO Workspace (Approval Authority)
    - Cashier -> Revenue Workspace
    - LCB Officer -> Provincial Dashboard
    - Others -> Executive Dashboard
    """
    
    permanent = False
    
    def get_redirect_url(self, *args, **kwargs):
        """Route user to appropriate workspace based on their role."""
        user = self.request.user
        
        # LCB Officers -> Provincial Dashboard
        if user.is_lcb_officer():
            return reverse('dashboard:provincial')
        
        # Finance Officers / Accountants -> Finance Workspace
        if user.is_finance_officer() or user.is_checker():
            return reverse('dashboard:workspace_finance')
        
        # TMO (Approval Authority) -> PAO Workspace
        if user.is_approver():
            return reverse('dashboard:workspace_pao')
        
        # Cashier -> Revenue Workspace
        if user.is_cashier():
            return reverse('dashboard:workspace_revenue')
        
        # Dealing Assistant (Makers) -> Executive Dashboard (default)
        # System Admin -> Executive Dashboard
        return reverse('dashboard:index')


class FinanceWorkspaceView(LoginRequiredMixin, TemplateView):
    """
    Finance Officer / Accountant Workspace.
    
    Features:
    - Budget utilization metrics
    - Action queue: Bills with status SUBMITTED (awaiting scrutiny)
    - Pending reconciliations
    - Quick links to budget management tools
    """
    
    template_name = 'dashboard/workspace_finance.html'
    
    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Get user's organization
        organization = user.organization
        if not organization:
            context['no_organization'] = True
            return context
        
        # Get current fiscal year
        fiscal_year = FiscalYear.get_current_operating_year(organization)
        if not fiscal_year:
            context['no_fiscal_year'] = True
            return context
        
        context['fiscal_year'] = fiscal_year
        context['organization'] = organization
        
        # Import here to avoid circular imports
        from apps.expenditure.models import Bill, BillStatus
        from apps.budgeting.models import BudgetAllocation
        from django.db.models import Sum, Q
        
        # Action Queue: Bills awaiting scrutiny
        pending_bills = Bill.objects.filter(
            organization=organization,
            fiscal_year=fiscal_year,
            status=BillStatus.SUBMITTED
        ).select_related('payee', 'budget_head').order_by('-bill_date')[:10]
        
        context['pending_bills'] = pending_bills
        context['pending_bills_count'] = pending_bills.count()
        
        # Budget Utilization Metrics
        budget_allocations = BudgetAllocation.objects.filter(
            organization=organization,
            fiscal_year=fiscal_year
        )
        
        total_budget = budget_allocations.aggregate(
            total=Sum('revised_allocation')
        )['total'] or Decimal('0.00')
        
        total_spent = budget_allocations.aggregate(
            total=Sum('spent_amount')
        )['total'] or Decimal('0.00')
        
        utilization_rate = (total_spent / total_budget * 100) if total_budget > 0 else Decimal('0.00')
        
        context['budget_metrics'] = {
            'total_budget': total_budget,
            'total_spent': total_spent,
            'available': total_budget - total_spent,
            'utilization_rate': utilization_rate,
        }
        
        # Pending Liabilities (Approved but not paid bills)
        pending_liabilities = Bill.objects.filter(
            organization=organization,
            fiscal_year=fiscal_year,
            status=BillStatus.APPROVED
        ).aggregate(total=Sum('net_amount'))['total'] or Decimal('0.00')
        
        context['pending_liabilities'] = pending_liabilities
        
        return context


class AuditWorkspaceView(LoginRequiredMixin, TemplateView):
    """
    Audit Officer Workspace (Resident Audit Team).
    
    Features:
    - Action queue: Bills marked for audit
    - Bulk pass/return with objections
    - Audit statistics and compliance metrics
    """
    
    template_name = 'dashboard/workspace_audit.html'
    
    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        organization = user.organization
        if not organization:
            context['no_organization'] = True
            return context
        
        fiscal_year = FiscalYear.get_current_operating_year(organization)
        if not fiscal_year:
            context['no_fiscal_year'] = True
            return context
        
        context['fiscal_year'] = fiscal_year
        context['organization'] = organization
        
        from apps.expenditure.models import Bill, BillStatus
        from django.db.models import Sum
        
        # Action Queue: Bills marked for audit (if status exists)
        # Note: MARKED_FOR_AUDIT status will be added in next task
        audit_bills = Bill.objects.filter(
            organization=organization,
            fiscal_year=fiscal_year,
            status__in=[BillStatus.SUBMITTED]  # Will add MARKED_FOR_AUDIT
        ).select_related('payee', 'budget_head', 'submitted_by').order_by('-bill_date')[:15]
        
        context['audit_bills'] = audit_bills
        context['audit_bills_count'] = audit_bills.count()
        
        # Audit Statistics
        total_audited = Bill.objects.filter(
            organization=organization,
            fiscal_year=fiscal_year,
            status__in=[BillStatus.APPROVED, BillStatus.PAID]
        ).count()
        
        total_rejected = Bill.objects.filter(
            organization=organization,
            fiscal_year=fiscal_year,
            status=BillStatus.REJECTED
        ).count()
        
        context['audit_stats'] = {
            'total_audited': total_audited,
            'total_rejected': total_rejected,
            'pending_audit': audit_bills.count(),
        }
        
        return context


class RevenueWorkspaceView(LoginRequiredMixin, TemplateView):
    """
    Revenue / Collecting Officer Workspace.
    
    Features:
    - Today's collection metrics
    - Month-to-date recovery vs target
    - Unreconciled challans/receipts
    - Outstanding demands
    """
    
    template_name = 'dashboard/workspace_revenue.html'
    
    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        organization = user.organization
        if not organization:
            context['no_organization'] = True
            return context
        
        fiscal_year = FiscalYear.get_current_operating_year(organization)
        if not fiscal_year:
            context['no_fiscal_year'] = True
            return context
        
        context['fiscal_year'] = fiscal_year
        context['organization'] = organization
        
        from apps.revenue.models import RevenueDemand, RevenueCollection, DemandStatus, CollectionStatus
        from django.db.models import Sum, Q
        from django.db.models import Sum, Q, F, Count
        from django.db.models.functions import Coalesce
        from datetime import date
        
        today = timezone.now().date()
        month_start = date(today.year, today.month, 1)
        
        # Today's Collections (Posted only - Accrual basis)
        today_collections = RevenueCollection.objects.filter(
            organization=organization,
            demand__fiscal_year=fiscal_year,
            receipt_date=today,
            status=CollectionStatus.POSTED
        ).aggregate(total=Sum('amount_received'))['total'] or Decimal('0.00')
        
        context['today_collections'] = today_collections
        
        # Month-to-Date Collections (Posted only - Accrual basis)
        mtd_collections = RevenueCollection.objects.filter(
            organization=organization,
            demand__fiscal_year=fiscal_year,
            receipt_date__gte=month_start,
            status=CollectionStatus.POSTED
        ).aggregate(total=Sum('amount_received'))['total'] or Decimal('0.00')
        
        context['mtd_collections'] = mtd_collections
        
        # Outstanding Demands
        outstanding_demands = RevenueDemand.objects.filter(
            organization=organization,
            fiscal_year=fiscal_year,
            status__in=[DemandStatus.POSTED, DemandStatus.PARTIAL]
        ).select_related('payer', 'budget_head').order_by('due_date')[:10]
        
        context['outstanding_demands'] = outstanding_demands
        context['outstanding_demands_count'] = outstanding_demands.count()
        
        # Total Outstanding Amount (All demands, accounting for partial payments)
        total_outstanding = RevenueDemand.objects.filter(
            organization=organization,
            fiscal_year=fiscal_year,
            status__in=[DemandStatus.POSTED, DemandStatus.PARTIAL]
        ).annotate(
            total_collected=Coalesce(
                Sum('collections__amount_received', 
                    filter=Q(collections__status=CollectionStatus.POSTED)),
                Decimal('0.00')
            )
        ).aggregate(
            total=Sum(F('amount') - F('total_collected'))
        )['total'] or Decimal('0.00')
        
        context['total_outstanding'] = total_outstanding
        
        # Unreconciled Collections (not posted to GL)
        unreconciled_data = RevenueCollection.objects.filter(
            organization=organization,
            demand__fiscal_year=fiscal_year,
            status=CollectionStatus.DRAFT
        ).aggregate(
            count=Count('id'),
            total=Sum('amount_received')
        )
        
        context['unreconciled_collections'] = unreconciled_data['count'] or 0
        context['unreconciled_amount'] = unreconciled_data['total'] or Decimal('0.00')
        
        # Expenditure Metrics (Cashier handles both collections and payments)
        from apps.expenditure.models import Payment
        
        # Today's Payments (Posted only)
        today_payments = Payment.objects.filter(
            organization=organization,
            bill__fiscal_year=fiscal_year,
            cheque_date=today,
            is_posted=True
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        context['today_payments'] = today_payments
        
        # Month-to-Date Payments (Posted only)
        mtd_payments = Payment.objects.filter(
            organization=organization,
            bill__fiscal_year=fiscal_year,
            cheque_date__gte=month_start,
            is_posted=True
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        context['mtd_payments'] = mtd_payments
        
        # Pending Payments (Draft status - not posted)
        pending_payments_data = Payment.objects.filter(
            organization=organization,
            bill__fiscal_year=fiscal_year,
            is_posted=False
        ).aggregate(
            count=Count('id'),
            total=Sum('amount')
        )
        
        context['pending_payments'] = pending_payments_data['count'] or 0
        context['pending_payments_amount'] = pending_payments_data['total'] or Decimal('0.00')
        
        return context


class PAOWorkspaceView(LoginRequiredMixin, TemplateView):
    """
    PAO / TMO Workspace (Sanctioning Authority).
    
    Features:
    - Action queue: Bills audited and ready for final approval
    - High-level monthly expenditure summary
    - Budget vs actual performance
    - Critical alerts and compliance issues
    """
    
    template_name = 'dashboard/workspace_pao.html'
    
    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        organization = user.organization
        if not organization:
            context['no_organization'] = True
            return context
        
        fiscal_year = FiscalYear.get_current_operating_year(organization)
        if not fiscal_year:
            context['no_fiscal_year'] = True
            return context
        
        context['fiscal_year'] = fiscal_year
        context['organization'] = organization
        
        from apps.expenditure.models import Bill, BillStatus
        from apps.budgeting.models import BudgetAllocation
        from django.db.models import Sum
        from datetime import date
        
        # Action Queue: Bills ready for final approval
        # (After audit, waiting for TMO approval)
        approval_queue = Bill.objects.filter(
            organization=organization,
            fiscal_year=fiscal_year,
            status=BillStatus.VERIFIED 
        ).select_related('payee', 'budget_head', 'submitted_by').order_by('-bill_date')[:10]
        
        context['approval_queue'] = approval_queue
        context['approval_queue_count'] = approval_queue.count()
        
        # Monthly Expenditure Summary
        today = timezone.now().date()
        month_start = date(today.year, today.month, 1)
        
        monthly_expenditure = Bill.objects.filter(
            organization=organization,
            fiscal_year=fiscal_year,
            status__in=[BillStatus.APPROVED, BillStatus.PAID],
            bill_date__gte=month_start
        ).aggregate(total=Sum('net_amount'))['total'] or Decimal('0.00')
        
        context['monthly_expenditure'] = monthly_expenditure
        
        # Budget Performance
        budget_allocations = BudgetAllocation.objects.filter(
            organization=organization,
            fiscal_year=fiscal_year
        )
        
        total_budget = budget_allocations.aggregate(
            total=Sum('revised_allocation')
        )['total'] or Decimal('0.00')
        
        total_spent = budget_allocations.aggregate(
            total=Sum('spent_amount')
        )['total'] or Decimal('0.00')
        
        context['budget_performance'] = {
            'total_budget': total_budget,
            'total_spent': total_spent,
            'available': total_budget - total_spent,
            'utilization_rate': (total_spent / total_budget * 100) if total_budget > 0 else Decimal('0.00'),
        }
        
        # Critical Alerts (Heads with >90% utilization)
        critical_heads = budget_allocations.filter(
            revised_allocation__gt=0
        ).annotate(
            utilization=Sum('spent_amount') * 100 / Sum('revised_allocation')
        ).filter(
            utilization__gte=90
        ).select_related('budget_head')[:5]
        
        context['critical_heads'] = critical_heads
        
        return context
