"""
-------------------------------------------------------------------------
System: KP-CFMS (Computerized Financial Management System)
Client: Local Government Department, Khyber Pakhtunkhwa
Team Lead: Jamil Shah
Developers: Ali Asghar, Akhtar Munir and Zarif Khan
Description: Dashboard views with caching for performance optimization.
-------------------------------------------------------------------------
"""
from decimal import Decimal
from typing import Dict, Any, Optional
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.cache import cache
from django.utils import timezone

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
