"""
-------------------------------------------------------------------------
System: KP-CFMS (Computerized Financial Management System)
Client: Local Government Department, Khyber Pakhtunkhwa
Team Lead: Jamil Shah
Developers: Ali Asghar, Akhtar Munir and Zarif Khan
Description: Django views for the budgeting module.
             Implements budget entry, approval, and SAE views.
-------------------------------------------------------------------------
"""
from typing import Any, Dict
from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.db.models import Sum, Q
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views.generic import (
    ListView, CreateView, UpdateView, DeleteView, 
    DetailView, FormView, TemplateView
)

from apps.budgeting.models import (
    FiscalYear, BudgetAllocation, ScheduleOfEstablishment,
    QuarterlyRelease, SAERecord, BudgetStatus, ReleaseQuarter,
    DesignationMaster, Department,
    # Phase 3: Pension & Budget Execution
    PensionEstimate, RetiringEmployee, PensionEstimateStatus,
    SupplementaryGrant, SupplementaryGrantStatus,
    Reappropriation, ReappropriationStatus
)
from apps.budgeting.models_employee import BudgetEmployee
from apps.budgeting.forms import (
    FiscalYearForm, ReceiptEstimateForm, ExpenditureEstimateForm,
    ScheduleOfEstablishmentForm, BudgetApprovalForm, QuarterlyReleaseForm,
    BudgetSearchForm, BPSSalaryScaleForm,
    # Phase 3: Pension & Budget Execution
    PensionEstimateForm, RetiringEmployeeForm, SupplementaryGrantForm, ReappropriationForm
)
from apps.budgeting.services import (
    finalize_budget, process_quarterly_release,
    validate_reserve_requirement, validate_zero_deficit
)
from apps.users.permissions import (
    MakerRequiredMixin, ApproverRequiredMixin, FinanceOfficerRequiredMixin,
    AdminRequiredMixin
)
from apps.core.exceptions import (
    BudgetLockedException, ReserveViolationException, 
    FiscalYearInactiveException, BudgetExceededException
)


class BudgetingDashboardView(LoginRequiredMixin, TemplateView):
    """
    Main dashboard for the budgeting module.
    Shows fiscal year summary and quick actions.
    """
    
    template_name = 'budgeting/dashboard.html'
    
    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        
        # Get active fiscal year
        active_fy = FiscalYear.objects.filter(is_active=True).first()
        context['active_fiscal_year'] = active_fy
        
        # Get all fiscal years for dropdown
        context['fiscal_years'] = FiscalYear.objects.all()[:5]
        
        if active_fy:
            # Calculate totals
            context['total_receipts'] = active_fy.get_total_receipts()
            context['total_expenditure'] = active_fy.get_total_expenditure()
            context['contingency'] = active_fy.get_contingency_amount()
            
            # Validate budget
            receipts = context['total_receipts']
            expenditure = context['total_expenditure']
            contingency = context['contingency']
            
            is_valid, _ = validate_reserve_requirement(receipts, contingency)
            context['reserve_valid'] = is_valid
            
            is_valid, _ = validate_zero_deficit(receipts, expenditure)
            context['deficit_valid'] = is_valid
            
            # Pending quarterly releases
            context['pending_releases'] = QuarterlyRelease.objects.filter(
                fiscal_year=active_fy,
                is_released=False
            ).count()
        
        return context


class FiscalYearListView(LoginRequiredMixin, ListView):
    """
    List all fiscal years.
    """
    
    model = FiscalYear
    template_name = 'budgeting/fiscal_year_list.html'
    context_object_name = 'fiscal_years'
    ordering = ['-start_date']


class FiscalYearCreateView(LoginRequiredMixin, ApproverRequiredMixin, CreateView):
    """
    Create new fiscal year (TMO only).
    """
    
    model = FiscalYear
    form_class = FiscalYearForm
    template_name = 'budgeting/fiscal_year_form.html'
    success_url = reverse_lazy('budgeting:fiscal_year_list')
    
    def form_valid(self, form) -> HttpResponse:
        form.instance.created_by = self.request.user
        form.instance.updated_by = self.request.user
        messages.success(self.request, _('Fiscal year created successfully.'))
        return super().form_valid(form)


class FiscalYearUpdateView(LoginRequiredMixin, ApproverRequiredMixin, UpdateView):
    """
    Update fiscal year details (TMO only).
    """
    model = FiscalYear
    form_class = FiscalYearForm
    template_name = 'budgeting/fiscal_year_form.html'
    success_url = reverse_lazy('budgeting:fiscal_year_list')
    
    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        messages.success(self.request, _('Fiscal year updated successfully.'))
        return super().form_valid(form)


class FiscalYearDetailView(LoginRequiredMixin, DetailView):
    """
    View fiscal year details with budget summary.
    """
    
    model = FiscalYear
    template_name = 'budgeting/fiscal_year_detail.html'
    context_object_name = 'fiscal_year'
    
    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        fy = self.object
        
        # Get allocation summary by account type
        from apps.finance.models import AccountType
        
        context['receipt_allocations'] = BudgetAllocation.objects.filter(
            fiscal_year=fy,
            budget_head__account_type=AccountType.REVENUE
        ).select_related('budget_head')[:20]
        
        context['expenditure_allocations'] = BudgetAllocation.objects.filter(
            fiscal_year=fy,
            budget_head__account_type=AccountType.EXPENDITURE
        ).select_related('budget_head')[:20]
        
        context['establishment'] = ScheduleOfEstablishment.objects.filter(
            fiscal_year=fy
        )[:20]
        
        context['quarterly_releases'] = QuarterlyRelease.objects.filter(
            fiscal_year=fy
        )
        
        # Totals
        context['total_receipts'] = fy.get_total_receipts()
        context['total_expenditure'] = fy.get_total_expenditure()
        context['contingency'] = fy.get_contingency_amount()
        
        return context


class BudgetAllocationListView(LoginRequiredMixin, ListView):
    """
    List budget allocations with search and filter.
    """
    
    model = BudgetAllocation
    template_name = 'budgeting/allocation_list.html'
    context_object_name = 'allocations'
    paginate_by = 25
    
    def get_queryset(self):
        queryset = super().get_queryset().select_related(
            'fiscal_year', 'budget_head', 'budget_head__function'
        )
        
        # Filter by fiscal year
        fiscal_year_id = self.request.GET.get('fiscal_year')
        if fiscal_year_id:
            queryset = queryset.filter(fiscal_year_id=fiscal_year_id)
        else:
            # Default to active fiscal year
            active_fy = FiscalYear.objects.filter(is_active=True).first()
            if active_fy:
                queryset = queryset.filter(fiscal_year=active_fy)
        
        # Filter by account type
        account_type = self.request.GET.get('account_type')
        if account_type:
            queryset = queryset.filter(budget_head__account_type=account_type)
        
        # Search
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(budget_head__tma_sub_object__icontains=search) |
                Q(budget_head__tma_description__icontains=search)
            )
        
        return queryset.order_by('budget_head__pifra_object')
    
    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context['search_form'] = BudgetSearchForm(self.request.GET)
        context['fiscal_years'] = FiscalYear.objects.all()
        return context


class ReceiptEstimateCreateView(LoginRequiredMixin, MakerRequiredMixin, CreateView):
    """
    Create receipt estimate (Form BDR-1).
    """
    
    model = BudgetAllocation
    form_class = ReceiptEstimateForm
    template_name = 'budgeting/form_bdr1.html'
    success_url = reverse_lazy('budgeting:allocation_list')
    
    def get_form_kwargs(self) -> Dict[str, Any]:
        kwargs = super().get_form_kwargs()
        kwargs['fiscal_year'] = self.get_fiscal_year()
        return kwargs
    
    def get_fiscal_year(self) -> FiscalYear:
        fy_id = self.request.GET.get('fiscal_year')
        if fy_id:
            return get_object_or_404(FiscalYear, pk=fy_id)
        return FiscalYear.objects.filter(is_active=True).first()
    
    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context['fiscal_year'] = self.get_fiscal_year()
        context['form_title'] = _('Form BDR-1: Receipt Estimate')
        return context
    
    def form_valid(self, form) -> HttpResponse:
        fiscal_year = self.get_fiscal_year()
        
        if not fiscal_year:
            messages.error(self.request, _('No active fiscal year found.'))
            return self.form_invalid(form)
        
        if not fiscal_year.can_edit_budget():
            messages.error(self.request, _('Budget entry is not allowed for this fiscal year.'))
            return self.form_invalid(form)
        
        form.instance.fiscal_year = fiscal_year
        form.instance.created_by = self.request.user
        form.instance.updated_by = self.request.user
        
        messages.success(self.request, _('Receipt estimate saved successfully.'))
        return super().form_valid(form)


class ExpenditureEstimateCreateView(LoginRequiredMixin, MakerRequiredMixin, CreateView):
    """
    Create expenditure estimate (Form BDC-1).
    """
    
    model = BudgetAllocation
    form_class = ExpenditureEstimateForm
    template_name = 'budgeting/form_bdc1.html'
    success_url = reverse_lazy('budgeting:allocation_list')
    
    def get_form_kwargs(self) -> Dict[str, Any]:
        kwargs = super().get_form_kwargs()
        kwargs['fiscal_year'] = self.get_fiscal_year()
        return kwargs
    
    def get_fiscal_year(self) -> FiscalYear:
        fy_id = self.request.GET.get('fiscal_year')
        if fy_id:
            return get_object_or_404(FiscalYear, pk=fy_id)
        return FiscalYear.objects.filter(is_active=True).first()
    
    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context['fiscal_year'] = self.get_fiscal_year()
        context['form_title'] = _('Form BDC-1: Expenditure Estimate')
        return context
    
    def form_valid(self, form) -> HttpResponse:
        fiscal_year = self.get_fiscal_year()
        
        if not fiscal_year:
            messages.error(self.request, _('No active fiscal year found.'))
            return self.form_invalid(form)
        
        if not fiscal_year.can_edit_budget():
            messages.error(self.request, _('Budget entry is not allowed for this fiscal year.'))
            return self.form_invalid(form)
        
        form.instance.fiscal_year = fiscal_year
        form.instance.created_by = self.request.user
        form.instance.updated_by = self.request.user
        
        messages.success(self.request, _('Expenditure estimate saved successfully.'))
        return super().form_valid(form)


class ScheduleOfEstablishmentListView(LoginRequiredMixin, ListView):
    """
    List Schedule of Establishment entries.
    """
    
    model = ScheduleOfEstablishment
    template_name = 'budgeting/establishment_list.html'
    context_object_name = 'establishment_entries'
    paginate_by = 25
    
    def get_queryset(self):
        queryset = super().get_queryset().select_related(
            'fiscal_year', 'budget_head'
        )
        
        fiscal_year_id = self.request.GET.get('fiscal_year')
        if fiscal_year_id:
            queryset = queryset.filter(fiscal_year_id=fiscal_year_id)
        else:
            active_fy = FiscalYear.objects.filter(is_active=True).first()
            if active_fy:
                queryset = queryset.filter(fiscal_year=active_fy)
        
        return queryset.order_by('department', '-bps_scale')
    
    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context['fiscal_years'] = FiscalYear.objects.all()
        
        # Split into Section A (Sanctioned) and Section B (Proposed)
        queryset = self.get_queryset()
        from apps.budgeting.models import EstablishmentStatus
        
        context['sanctioned_list'] = queryset.filter(
            establishment_status=EstablishmentStatus.SANCTIONED
        )
        context['proposed_list'] = queryset.filter(
            establishment_status=EstablishmentStatus.PROPOSED
        )
        
        # Calculate totals
        context['total_sanctioned'] = context['sanctioned_list'].aggregate(
            total=Sum('sanctioned_posts')
        )['total'] or 0
        context['total_occupied'] = context['sanctioned_list'].aggregate(
            total=Sum('occupied_posts')
        )['total'] or 0
        
        return context


class ScheduleOfEstablishmentCreateView(LoginRequiredMixin, MakerRequiredMixin, CreateView):
    """
    Create Schedule of Establishment entry (Form BDC-2).
    """
    
    model = ScheduleOfEstablishment
    form_class = ScheduleOfEstablishmentForm
    template_name = 'budgeting/form_bdc2.html'
    success_url = reverse_lazy('budgeting:establishment_list')
    
    def get_form_kwargs(self) -> Dict[str, Any]:
        kwargs = super().get_form_kwargs()
        kwargs['fiscal_year'] = self.get_fiscal_year()
        return kwargs
    
    def get_fiscal_year(self) -> FiscalYear:
        fy_id = self.request.GET.get('fiscal_year')
        if fy_id:
            return get_object_or_404(FiscalYear, pk=fy_id)
        return FiscalYear.objects.filter(is_active=True).first()
    
    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context['fiscal_year'] = self.get_fiscal_year()
        context['form_title'] = _('Form BDC-2: Schedule of Establishment')
        return context
    
    def form_valid(self, form) -> HttpResponse:
        fiscal_year = self.get_fiscal_year()
        
        if not fiscal_year:
            messages.error(self.request, _('No active fiscal year found.'))
            return self.form_invalid(form)
        
        if not fiscal_year.can_edit_budget():
            messages.error(self.request, _('Budget entry is not allowed for this fiscal year.'))
            return self.form_invalid(form)
        
        form.instance.fiscal_year = fiscal_year
        form.instance.created_by = self.request.user
        form.instance.updated_by = self.request.user
        
        messages.success(self.request, _('Establishment entry saved successfully.'))
        return super().form_valid(form)


class NewPostProposalCreateView(LoginRequiredMixin, MakerRequiredMixin, CreateView):
    """
    Create New Post Proposal (SNE) (Form BDC-2 Part B).
    """
    
    model = ScheduleOfEstablishment
    from apps.budgeting.forms import NewPostProposalForm
    form_class = NewPostProposalForm
    template_name = 'budgeting/form_sne.html'  # Specific template for SNE
    success_url = reverse_lazy('budgeting:establishment_list')
    
    def get_form_kwargs(self) -> Dict[str, Any]:
        kwargs = super().get_form_kwargs()
        kwargs['fiscal_year'] = self.get_fiscal_year()
        return kwargs
    
    def get_fiscal_year(self) -> FiscalYear:
        fy_id = self.request.GET.get('fiscal_year')
        if fy_id:
            return get_object_or_404(FiscalYear, pk=fy_id)
        return FiscalYear.objects.filter(is_active=True).first()
    
    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context['fiscal_year'] = self.get_fiscal_year()
        context['form_title'] = _('Propose New Posts (SNE)')
        return context
    
    def form_valid(self, form) -> HttpResponse:
        fiscal_year = self.get_fiscal_year()
        
        if not fiscal_year:
            messages.error(self.request, _('No active fiscal year found.'))
            return self.form_invalid(form)
        
        if not fiscal_year.can_edit_budget():
            messages.error(self.request, _('Budget entry is not allowed for this fiscal year.'))
            return self.form_invalid(form)
        
        form.instance.fiscal_year = fiscal_year
        form.instance.created_by = self.request.user
        form.instance.updated_by = self.request.user
        
        # Financial impact is auto-calculated in model save()
        
        messages.success(self.request, _('New post proposal submitted successfully.'))
        return super().form_valid(form)


class BudgetApprovalView(LoginRequiredMixin, ApproverRequiredMixin, FormView):
    """
    TMO approval view for budget finalization.
    """
    
    form_class = BudgetApprovalForm
    template_name = 'budgeting/budget_approval.html'
    success_url = reverse_lazy('budgeting:sae_list')
    
    def get_fiscal_year(self) -> FiscalYear:
        fy_id = self.kwargs.get('pk')
        return get_object_or_404(FiscalYear, pk=fy_id)
    
    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        fy = self.get_fiscal_year()
        context['fiscal_year'] = fy
        
        # Calculate totals and validation
        context['total_receipts'] = fy.get_total_receipts()
        context['total_expenditure'] = fy.get_total_expenditure()
        context['contingency'] = fy.get_contingency_amount()
        context['surplus'] = context['total_receipts'] - context['total_expenditure']
        
        # Required reserve
        context['required_reserve'] = context['total_receipts'] * Decimal('0.02')
        
        # Validation status
        is_valid, error = validate_reserve_requirement(
            context['total_receipts'], context['contingency']
        )
        context['reserve_valid'] = is_valid
        context['reserve_error'] = error
        
        is_valid, error = validate_zero_deficit(
            context['total_receipts'], context['total_expenditure']
        )
        context['deficit_valid'] = is_valid
        context['deficit_error'] = error
        
        return context
    
    def form_valid(self, form) -> HttpResponse:
        fy = self.get_fiscal_year()
        
        try:
            result = finalize_budget(fy.id, self.request.user.id)
            messages.success(
                self.request,
                _(f'Budget finalized successfully. SAE Number: {result["sae_number"]}')
            )
            return super().form_valid(form)
        
        except ReserveViolationException as e:
            messages.error(self.request, e.message)
            return self.form_invalid(form)
        
        except BudgetExceededException as e:
            messages.error(self.request, e.message)
            return self.form_invalid(form)
        
        except BudgetLockedException as e:
            messages.error(self.request, e.message)
            return self.form_invalid(form)


class QuarterlyReleaseView(LoginRequiredMixin, FinanceOfficerRequiredMixin, FormView):
    """
    Process quarterly fund release (TO Finance).
    """
    
    form_class = QuarterlyReleaseForm
    template_name = 'budgeting/quarterly_release.html'
    success_url = reverse_lazy('budgeting:dashboard')
    
    def get_fiscal_year(self) -> FiscalYear:
        fy_id = self.kwargs.get('pk')
        return get_object_or_404(FiscalYear, pk=fy_id)
    
    def get_form_kwargs(self) -> Dict[str, Any]:
        kwargs = super().get_form_kwargs()
        fy = self.get_fiscal_year()
        
        # Get pending quarters
        pending = QuarterlyRelease.objects.filter(
            fiscal_year=fy,
            is_released=False
        ).values_list('quarter', flat=True)
        
        kwargs['pending_quarters'] = [
            (q, dict(ReleaseQuarter.choices).get(q, q))
            for q in pending
        ]
        
        return kwargs
    
    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context['fiscal_year'] = self.get_fiscal_year()
        context['releases'] = QuarterlyRelease.objects.filter(
            fiscal_year=context['fiscal_year']
        )
        return context
    
    def form_valid(self, form) -> HttpResponse:
        fy = self.get_fiscal_year()
        quarter = form.cleaned_data['quarter']
        
        try:
            result = process_quarterly_release(
                fy.id, quarter, self.request.user.id
            )
            messages.success(
                self.request,
                _(f'Quarterly release processed. Total: Rs {result["total_released"]}')
            )
            return super().form_valid(form)
        
        except (BudgetLockedException, FiscalYearInactiveException) as e:
            messages.error(self.request, e.message)
            return self.form_invalid(form)


class SAEListView(LoginRequiredMixin, ListView):
    """
    List all SAE (Schedule of Authorized Expenditure) records.
    """
    
    model = SAERecord
    template_name = 'budgeting/sae_list.html'
    context_object_name = 'sae_records'
    ordering = ['-approval_date']



class SAEDetailView(LoginRequiredMixin, DetailView):
    """
    View SAE record details.
    """
    
    model = SAERecord
    template_name = 'budgeting/sae_detail.html'
    context_object_name = 'sae'
    
    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        
        # Get allocation breakdown
        fy = self.object.fiscal_year
        
        from apps.finance.models import AccountType
        
        context['receipt_allocations'] = BudgetAllocation.objects.filter(
            fiscal_year=fy,
            budget_head__account_type=AccountType.REVENUE
        ).select_related('budget_head').order_by('budget_head__pifra_object')
        
        context['expenditure_allocations'] = BudgetAllocation.objects.filter(
            fiscal_year=fy,
            budget_head__account_type=AccountType.EXPENDITURE
        ).select_related('budget_head').order_by('budget_head__pifra_object')
        
        context['establishment'] = ScheduleOfEstablishment.objects.filter(
            fiscal_year=fy
        ).order_by('department', '-bps_scale')
        
        return context


from django.views import View
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
import json


class SmartCalculatorView(LoginRequiredMixin, View):
    """
    Smart Calculator API endpoint for budget estimation.
    
    Calculates annual budget based on:
    - Filled posts cost (from last month bill × 12)
    - Vacant posts cost (from BPS salary scale)
    - 10% inflation buffer
    """
    
    def get(self, request: HttpRequest, pk: int) -> HttpResponse:
        """Return current estimation data for an establishment entry."""
        entry = get_object_or_404(ScheduleOfEstablishment, pk=pk)
        
        from apps.budgeting.models import BPSSalaryScale
        
        # Get current values
        vacant = entry.vacant_posts
        filled = entry.occupied_posts
        
        # Get salary scale
        scale = BPSSalaryScale.objects.filter(bps_grade=entry.bps_scale).first()
        bps_annual = (scale.estimated_gross_salary * 12) if scale else Decimal('0')
        
        return JsonResponse({
            'id': entry.id,
            'designation': entry.designation_name,
            'department': entry.department,
            'bps_scale': entry.bps_scale,
            'sanctioned_posts': entry.sanctioned_posts,
            'occupied_posts': filled,
            'vacant_posts': vacant,
            'annual_salary_per_post': float(bps_annual),
            'last_month_bill': float(entry.last_month_bill),
            'current_estimated_budget': float(entry.estimated_budget),
        })
    
    def post(self, request: HttpRequest, pk: int) -> HttpResponse:
        """
        Calculate budget estimate using employee-wise data.
        
        Triggers the calculate_total_budget_requirement() method and returns
        the breakdown of filled vs vacant costs.
        """
        entry = get_object_or_404(ScheduleOfEstablishment, pk=pk)
        
        try:
            data = json.loads(request.body) if request.body else {}
        except json.JSONDecodeError as e:
            return JsonResponse({'error': f'Invalid JSON: {e}'}, status=400)
        
        # Legacy support: If filled_posts and last_month_bill are provided,
        # use the old calculation method for backward compatibility
        if 'filled_posts' in data or 'last_month_bill' in data:
            return self._legacy_calculate(request, entry, data)
        
        # New method: Use employee-wise calculation
        try:
            result = entry.calculate_total_budget_requirement()
            
            return JsonResponse({
                'success': True,
                'saved': True,
                'method': 'employee_wise',
                'filled_count': result['filled_count'],
                'vacant_count': result['vacant_count'],
                'filled_cost': float(result['filled_cost']),
                'vacant_cost': float(result['vacant_cost']),
                'total_cost': float(result['total_cost']),
                'estimated_budget': float(result['total_cost']),
                'message': f'Budget calculated: Rs {result["total_cost"]:,.2f} '
                          f'(Filled: {result["filled_count"]}, Vacant: {result["vacant_count"]})'
            })
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    def _legacy_calculate(self, request: HttpRequest, entry, data: dict) -> HttpResponse:
        """Legacy calculation method using lump-sum bill data."""
        try:
            filled_posts = int(data.get('filled_posts', 0))
            last_month_bill = Decimal(str(data.get('last_month_bill', 0)))
        except (ValueError, TypeError) as e:
            return JsonResponse({'error': f'Invalid input: {e}'}, status=400)
        
        from apps.budgeting.models import BPSSalaryScale
        
        # Validate filled posts
        if filled_posts < 0 or filled_posts > entry.sanctioned_posts:
            return JsonResponse({
                'error': f'Filled posts must be between 0 and {entry.sanctioned_posts}'
            }, status=400)
        
        # Calculate vacant posts
        vacant_posts = entry.sanctioned_posts - filled_posts
        
        # Get salary scale rate
        scale = BPSSalaryScale.objects.filter(bps_grade=entry.bps_scale).first()
        bps_annual = (scale.estimated_gross_salary * 12) if scale else Decimal('0')
        
        # Calculate annual cost for filled staff (from bill)
        if filled_posts > 0 and last_month_bill > 0:
            filled_annual_cost = last_month_bill * 12
        else:
            # Use BPS rate if no bill provided
            filled_annual_cost = bps_annual * filled_posts
        
        # Calculate annual cost for vacant staff (using BPS salary scale)
        vacant_annual_cost = bps_annual * vacant_posts
        
        # Total before inflation
        total_cost = filled_annual_cost + vacant_annual_cost
        
        # Add 10% inflation buffer
        inflation_buffer = total_cost * Decimal('0.10')
        estimated_budget = total_cost + inflation_buffer
        
        # Only save if explicitly requested
        should_save = data.get('save', False)
        saved = False
        
        if should_save:
            entry.occupied_posts = filled_posts
            entry.last_month_bill = last_month_bill
            entry.estimated_budget = estimated_budget
            entry.save(update_fields=['occupied_posts', 'last_month_bill', 'estimated_budget', 'updated_at'])
            saved = True
        
        return JsonResponse({
            'success': True,
            'saved': saved,
            'method': 'legacy_lump_sum',
            'filled_posts': filled_posts,
            'vacant_posts': vacant_posts,
            'filled_annual_cost': float(filled_annual_cost),
            'vacant_annual_cost': float(vacant_annual_cost),
            'inflation_buffer': float(inflation_buffer),
            'estimated_budget': float(estimated_budget),
            'message': f'Budget estimate {"saved" if saved else "calculated"}: Rs {estimated_budget:,.2f}'
        })


class EstablishmentDetailView(LoginRequiredMixin, DetailView):
    """
    View Schedule of Establishment entry details.
    """
    
    model = ScheduleOfEstablishment
    template_name = 'budgeting/establishment_detail.html'
    context_object_name = 'entry'
    
    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        
        from apps.budgeting.workflows import get_user_allowed_actions, get_status_display_class
        
        # Get allowed actions for current user
        context['allowed_actions'] = get_user_allowed_actions(
            self.request.user,
            self.object
        )
        context['status_class'] = get_status_display_class(self.object.approval_status)
        
        return context


class EstablishmentApprovalView(LoginRequiredMixin, View):
    """
    Handle approval workflow actions for Schedule of Establishment entries.
    
    Supports: Verify, Recommend, Approve, Reject actions based on user role
    and post type (PUGF/LOCAL).
    """
    
    def post(self, request: HttpRequest, pk: int) -> HttpResponse:
        """Process approval action."""
        from apps.budgeting.models import ApprovalStatus
        from apps.budgeting.workflows import perform_transition, get_user_allowed_actions
        from apps.core.exceptions import WorkflowTransitionException
        
        entry = get_object_or_404(ScheduleOfEstablishment, pk=pk)
        
        # Get action from POST data
        action = request.POST.get('action', '')
        rejection_reason = request.POST.get('rejection_reason', '')
        
        # Map action to target status
        action_map = {
            'verify': ApprovalStatus.VERIFIED,
            'recommend': ApprovalStatus.RECOMMENDED,
            'approve': ApprovalStatus.APPROVED,
            'reject': ApprovalStatus.REJECTED,
        }
        
        target_status = action_map.get(action.lower())
        
        if not target_status:
            messages.error(request, _('Invalid action specified.'))
            return redirect('budgeting:establishment_list')
        
        # Check if user is allowed to perform this action
        allowed_actions = get_user_allowed_actions(request.user, entry)
        if target_status not in allowed_actions:
            messages.error(request, _('You are not authorized to perform this action.'))
            return redirect('budgeting:establishment_list')
        
        # Validate rejection reason
        if target_status == ApprovalStatus.REJECTED and not rejection_reason.strip():
            messages.error(request, _('Rejection reason is required.'))
            return redirect('budgeting:establishment_detail', pk=pk)
        
        try:
            with transaction.atomic():
                perform_transition(
                    establishment_entry=entry,
                    target_status=target_status,
                    user=request.user,
                    rejection_reason=rejection_reason
                )
            
            action_names = {
                ApprovalStatus.VERIFIED: 'verified',
                ApprovalStatus.RECOMMENDED: 'recommended for LCB approval',
                ApprovalStatus.APPROVED: 'approved',
                ApprovalStatus.REJECTED: 'rejected',
            }
            messages.success(
                request,
                _(f'Entry "{entry.designation_name}" has been {action_names.get(target_status, "updated")}.')
            )
        
        except WorkflowTransitionException as e:
            messages.error(request, str(e))
        
        except Exception as e:
            messages.error(request, _(f'Error processing action: {str(e)}'))
        
        return redirect('budgeting:establishment_list')



class EstablishmentBulkApprovalView(LoginRequiredMixin, TemplateView):
    """
    View for bulk approval of establishment entries.
    Shows all pending entries that the current user can approve.
    """
    
    template_name = 'budgeting/establishment_bulk_approval.html'
    
    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        
        from apps.budgeting.models import ApprovalStatus, PostType
        from apps.budgeting.workflows import get_user_allowed_actions
        
        user = self.request.user
        
        # Get entries that user can act on
        all_entries = ScheduleOfEstablishment.objects.filter(
            approval_status__in=[
                ApprovalStatus.DRAFT,
                ApprovalStatus.VERIFIED,
                ApprovalStatus.RECOMMENDED
            ]
        ).select_related('fiscal_year', 'budget_head')
        
        # Filter to only those user can act on
        actionable_entries = []
        for entry in all_entries:
            actions = get_user_allowed_actions(user, entry)
            if actions:
                actionable_entries.append({
                    'entry': entry,
                    'allowed_actions': actions
                })
        
        context['actionable_entries'] = actionable_entries
        
        # Stats
        context['pending_local'] = ScheduleOfEstablishment.objects.filter(
            post_type=PostType.LOCAL,
            approval_status__in=[ApprovalStatus.DRAFT, ApprovalStatus.VERIFIED]
        ).count()
        
        context['pending_pugf'] = ScheduleOfEstablishment.objects.filter(
            post_type=PostType.PUGF,
            approval_status__in=[ApprovalStatus.DRAFT, ApprovalStatus.VERIFIED, ApprovalStatus.RECOMMENDED]
        ).count()
        
        return context


# --- Setup / Master Data Management Views (Admin Only) ---

class SetupDashboardView(LoginRequiredMixin, AdminRequiredMixin, TemplateView):
    """Dashboard for managing master data."""
    template_name = 'budgeting/setup_dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['department_count'] = Department.objects.count()
        context['designation_count'] = DesignationMaster.objects.count()
        
        from apps.finance.models import BudgetHead, Fund, ChequeBook
        context['coa_count'] = BudgetHead.objects.count()
        context['fund_count'] = Fund.objects.count()
        context['chequebook_count'] = ChequeBook.objects.count()
        
        from apps.core.models import BankAccount
        context['bank_account_count'] = BankAccount.objects.count()
        return context


class DepartmentListView(LoginRequiredMixin, AdminRequiredMixin, ListView):
    """List all departments."""
    model = Department
    template_name = 'budgeting/setup_department_list.html'
    context_object_name = 'departments'


class DepartmentCreateView(LoginRequiredMixin, AdminRequiredMixin, CreateView):
    """Create new department."""
    model = Department
    fields = ['name', 'is_active']
    template_name = 'budgeting/setup_form.html'
    success_url = reverse_lazy('budgeting:setup_departments')
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['name'].widget.attrs.update({'class': 'form-control'})
        form.fields['is_active'].widget.attrs.update({'class': 'form-check-input'})
        return form
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = _('Add New Department')
        context['back_url'] = reverse_lazy('budgeting:setup_departments')
        return context


class DepartmentUpdateView(LoginRequiredMixin, AdminRequiredMixin, UpdateView):
    """Update department."""
    model = Department
    fields = ['name', 'is_active']
    template_name = 'budgeting/setup_form.html'
    success_url = reverse_lazy('budgeting:setup_departments')
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['name'].widget.attrs.update({'class': 'form-control'})
        form.fields['is_active'].widget.attrs.update({'class': 'form-check-input'})
        return form
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = _('Edit Department')
        context['back_url'] = reverse_lazy('budgeting:setup_departments')
        return context


class DepartmentDeleteView(LoginRequiredMixin, AdminRequiredMixin, DeleteView):
    """Delete department."""
    model = Department
    template_name = 'budgeting/setup_confirm_delete.html'
    success_url = reverse_lazy('budgeting:setup_departments')
    context_object_name = 'item'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = _('Delete Department')
        context['back_url'] = reverse_lazy('budgeting:setup_departments')
        return context


class DesignationListView(LoginRequiredMixin, AdminRequiredMixin, ListView):
    """List all designations."""
    model = DesignationMaster
    template_name = 'budgeting/setup_designation_list.html'
    context_object_name = 'designations'


class DesignationCreateView(LoginRequiredMixin, AdminRequiredMixin, CreateView):
    """Create new designation."""
    model = DesignationMaster
    fields = ['name', 'bps_scale', 'post_type', 'is_active']
    template_name = 'budgeting/setup_form.html'
    success_url = reverse_lazy('budgeting:setup_designations')
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['name'].widget.attrs.update({'class': 'form-control'})
        form.fields['bps_scale'].widget.attrs.update({'class': 'form-control'})
        form.fields['post_type'].widget.attrs.update({'class': 'form-select'})
        form.fields['is_active'].widget.attrs.update({'class': 'form-check-input'})
        return form
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = _('Add New Designation')
        context['back_url'] = reverse_lazy('budgeting:setup_designations')
        return context


class DesignationUpdateView(LoginRequiredMixin, AdminRequiredMixin, UpdateView):
    """Update designation."""
    model = DesignationMaster
    fields = ['name', 'bps_scale', 'post_type', 'is_active']
    template_name = 'budgeting/setup_form.html'
    success_url = reverse_lazy('budgeting:setup_designations')
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['name'].widget.attrs.update({'class': 'form-control'})
        form.fields['bps_scale'].widget.attrs.update({'class': 'form-control'})
        form.fields['post_type'].widget.attrs.update({'class': 'form-select'})
        form.fields['is_active'].widget.attrs.update({'class': 'form-check-input'})
        return form
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = _('Edit Designation')
        context['back_url'] = reverse_lazy('budgeting:setup_designations')
        return context


class DesignationDeleteView(LoginRequiredMixin, AdminRequiredMixin, DeleteView):
    """Delete designation."""
    model = DesignationMaster
    template_name = 'budgeting/setup_confirm_delete.html'
    success_url = reverse_lazy('budgeting:setup_designations')
    context_object_name = 'item'
    
class EmployeeListView(LoginRequiredMixin, ListView):
    """List employees linked to a schedule entry."""
    model = BudgetEmployee
    template_name = 'budgeting/employee_list.html'
    context_object_name = 'employees'
    
    def get_schedule(self):
        return get_object_or_404(ScheduleOfEstablishment, pk=self.kwargs['schedule_pk'])
    
    def get_queryset(self):
        return BudgetEmployee.objects.filter(
            schedule_id=self.kwargs['schedule_pk'],
            is_vacant=False
        ).order_by('name')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        schedule = self.get_schedule()
        context['schedule'] = schedule
        
        # Calculate stats
        result = schedule.calculate_total_budget_requirement()
        context['stats'] = result
        return context


class EmployeeCreateView(LoginRequiredMixin, CreateView):
    """Add new employee to schedule."""
    model = BudgetEmployee
    fields = ['name', 'cnic', 'personnel_number', 'current_basic_pay', 'monthly_allowances', 'annual_increment_amount']
    template_name = 'budgeting/setup_form.html'
    
    def get_schedule(self):
        return get_object_or_404(ScheduleOfEstablishment, pk=self.kwargs['schedule_pk'])
    
    def get_success_url(self):
        return reverse_lazy('budgeting:employee_list', kwargs={'schedule_pk': self.kwargs['schedule_pk']})
    
    def form_valid(self, form):
        schedule = self.get_schedule()
        form.instance.schedule = schedule
        form.instance.is_vacant = False
        response = super().form_valid(form)
        
        # Recalculate budget
        schedule.calculate_total_budget_requirement()
        messages.success(self.request, _('Employee added successfully.'))
        return response
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        for field in form.fields:
            form.fields[field].widget.attrs.update({'class': 'form-control'})
        return form
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        schedule = self.get_schedule()
        context['title'] = _(f'Add Employee - {schedule.designation_name}')
        context['back_url'] = self.get_success_url()
        return context


class EmployeeUpdateView(LoginRequiredMixin, UpdateView):
    """Edit employee details."""
    model = BudgetEmployee
    fields = ['name', 'cnic', 'personnel_number', 'current_basic_pay', 'monthly_allowances', 'annual_increment_amount']
    template_name = 'budgeting/setup_form.html'
    
    def get_success_url(self):
        return reverse_lazy('budgeting:employee_list', kwargs={'schedule_pk': self.object.schedule.pk})
    
    def form_valid(self, form):
        response = super().form_valid(form)
        # Recalculate budget
        self.object.schedule.calculate_total_budget_requirement()
        messages.success(self.request, _('Employee updated successfully.'))
        return response
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        for field in form.fields:
            form.fields[field].widget.attrs.update({'class': 'form-control'})
        return form
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = _(f'Edit Employee - {self.object.name}')
        context['back_url'] = self.get_success_url()
        return context


class EmployeeDeleteView(LoginRequiredMixin, DeleteView):
    """Delete employee."""
    model = BudgetEmployee
    template_name = 'budgeting/setup_confirm_delete.html'
    context_object_name = 'item'
    
    def get_success_url(self):
        return reverse_lazy('budgeting:employee_list', kwargs={'schedule_pk': self.object.schedule.pk})
        
    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        schedule = self.object.schedule
        response = super().delete(request, *args, **kwargs)
        
        # Recalculate budget
        schedule.calculate_total_budget_requirement()
        messages.success(request, _('Employee removed successfully.'))
        return response
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = _('Remove Employee')
        context['back_url'] = self.get_success_url()
        return context


class SalaryStructureView(LoginRequiredMixin, AdminRequiredMixin, TemplateView):
    """
    Grid view for editing BPS Salary Structures.
    """
    template_name = 'budgeting/setup_salary_structure.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from django.forms import modelformset_factory
        from apps.budgeting.models import BPSSalaryScale
        
        SalaryFormSet = modelformset_factory(
            BPSSalaryScale, 
            form=BPSSalaryScaleForm,
            extra=0,
            can_delete=False
        )
        
        if self.request.method == 'POST':
            formset = SalaryFormSet(self.request.POST, queryset=BPSSalaryScale.objects.all().order_by('bps_grade'))
        else:
            formset = SalaryFormSet(queryset=BPSSalaryScale.objects.all().order_by('bps_grade'))
            
        context['formset'] = formset
        return context
        
    def post(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        formset = context['formset']
        
        if formset.is_valid():
            formset.save()
            messages.success(request, 'Salary structure updated successfully.')
            return redirect('budgeting:setup_salary_structure')
        else:
            messages.error(request, 'Please verify the data. All fields must be valid numbers.')
            return self.render_to_response(context)


# =============================================================================
# Phase 3: Pension Estimate Workflows
# =============================================================================

class PensionEstimateListView(LoginRequiredMixin, ListView):
    model = PensionEstimate
    template_name = 'budgeting/pension_estimate_list.html'
    context_object_name = 'pension_estimates'
    ordering = ['-fiscal_year__start_date']


class PensionEstimateCreateView(LoginRequiredMixin, MakerRequiredMixin, CreateView):
    model = PensionEstimate
    form_class = PensionEstimateForm
    template_name = 'budgeting/pension_estimate_form.html'
    success_url = reverse_lazy('budgeting:pension_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from django.forms import inlineformset_factory
        RetiringEmployeeFormSet = inlineformset_factory(
            PensionEstimate, RetiringEmployee, 
            form=RetiringEmployeeForm, extra=1, can_delete=True
        )
        if self.request.POST:
            context['retirees_formset'] = RetiringEmployeeFormSet(self.request.POST)
        else:
            context['retirees_formset'] = RetiringEmployeeFormSet()
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        retirees_formset = context['retirees_formset']
        if retirees_formset.is_valid():
            self.object = form.save(commit=False)
            self.object.created_by = self.request.user
            self.object.updated_by = self.request.user
            self.object.save()
            retirees_formset.instance = self.object
            retirees_formset.save()
            messages.success(self.request, 'Pension estimate created successfully.')
            return super().form_valid(form)
        else:
            return self.render_to_response(self.get_context_data(form=form))


class PensionEstimateDetailView(LoginRequiredMixin, DetailView):
    model = PensionEstimate
    template_name = 'budgeting/pension_estimate_detail.html'
    context_object_name = 'estimate'


class PensionEstimateCalculateView(LoginRequiredMixin, MakerRequiredMixin, View):
    def post(self, request, pk):
        estimate = get_object_or_404(PensionEstimate, pk=pk)
        try:
            result = estimate.calculate_and_lock(user=request.user)
            messages.success(
                request, 
                f"Pension Budget Locked: A04101 (Monthly) = {result['monthly_pension']:,.2f}, "
                f"A04102 (Commutation) = {result['commutation']:,.2f}"
            )
        except Exception as e:
            messages.error(request, str(e))
        return redirect('budgeting:pension_detail', pk=pk)


# =============================================================================
# Supplementary Grant Workflows
# =============================================================================

class SupplementaryGrantListView(LoginRequiredMixin, ListView):
    model = SupplementaryGrant
    template_name = 'budgeting/supplementary_grant_list.html'
    context_object_name = 'grants'
    ordering = ['-date']


class SupplementaryGrantCreateView(LoginRequiredMixin, MakerRequiredMixin, CreateView):
    model = SupplementaryGrant
    form_class = SupplementaryGrantForm
    template_name = 'budgeting/supplementary_grant_form.html'
    success_url = reverse_lazy('budgeting:supplementary_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        form.instance.updated_by = self.request.user
        messages.success(self.request, 'Supplementary grant request created.')
        return super().form_valid(form)


class SupplementaryGrantDetailView(LoginRequiredMixin, DetailView):
    model = SupplementaryGrant
    template_name = 'budgeting/supplementary_grant_detail.html'
    context_object_name = 'grant'


class SupplementaryGrantApproveView(LoginRequiredMixin, ApproverRequiredMixin, View):
    def post(self, request, pk):
        grant = get_object_or_404(SupplementaryGrant, pk=pk)
        try:
            grant.approve(user=request.user)
            messages.success(request, f"Supplementary grant {grant.reference_no} approved.")
        except Exception as e:
            messages.error(request, str(e))
        return redirect('budgeting:supplementary_detail', pk=pk)


# =============================================================================
# Reappropriation Workflows
# =============================================================================

class ReappropriationListView(LoginRequiredMixin, ListView):
    model = Reappropriation
    template_name = 'budgeting/reappropriation_list.html'
    context_object_name = 'reappropriations'
    ordering = ['-date']


class ReappropriationCreateView(LoginRequiredMixin, MakerRequiredMixin, CreateView):
    model = Reappropriation
    form_class = ReappropriationForm
    template_name = 'budgeting/reappropriation_form.html'
    success_url = reverse_lazy('budgeting:reappropriation_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        form.instance.updated_by = self.request.user
        messages.success(self.request, 'Re-appropriation request created.')
        return super().form_valid(form)


class ReappropriationDetailView(LoginRequiredMixin, DetailView):
    model = Reappropriation
    template_name = 'budgeting/reappropriation_detail.html'
    context_object_name = 'reappropriation'


class ReappropriationApproveView(LoginRequiredMixin, ApproverRequiredMixin, View):
    def post(self, request, pk):
        reapp = get_object_or_404(Reappropriation, pk=pk)
        try:
            reapp.approve(user=request.user)
            messages.success(request, f"Re-appropriation {reapp.reference_no} approved.")
        except Exception as e:
            messages.error(request, str(e))
        return redirect('budgeting:reappropriation_detail', pk=pk)


# ============================================================
# PHASE 4: BUDGET BOOK REPORTING
# ============================================================

from django.views import View
from django.template.response import TemplateResponse
from django.utils import timezone
from apps.budgeting.services_report import BudgetBookService


class PrintBudgetBookView(LoginRequiredMixin, View):
    """
    Generate and render Budget Book PDF report.
    
    Displays a printer-friendly HTML page that can be printed to PDF
    or uses PDF generation libraries if available.
    
    URL: /budgeting/reports/budget-book/<int:fy_id>/
    
    Permissions: Any authenticated user can view budget book.
    """
    
    def get(self, request: HttpRequest, fy_id: int) -> HttpResponse:
        """
        Render Budget Book report.
        
        Args:
            request: HTTP request object.
            fy_id: Fiscal Year ID.
        
        Returns:
            HTTP response with rendered template or PDF.
        """
        # Get structured context from reporting service
        context = BudgetBookService.get_budget_book_context(fy_id)
        
        # Add current date for footer
        context['today'] = timezone.now()
        
        # Check if PDF generation is requested via query parameter
        generate_pdf = request.GET.get('pdf', 'false').lower() == 'true'
        engine = request.GET.get('engine', 'weasyprint').lower()
        
        if generate_pdf:
            # Attempt to generate PDF using selected engine
            template = 'budgeting/reports/budget_book_pdf.html'
            html_string = TemplateResponse(
                request, template, context
            ).render().content.decode('utf-8')

            if engine == 'weasyprint':
                try:
                    from weasyprint import HTML
                    # Generate PDF (base_url helps resolve relative assets)
                    pdf_file = HTML(string=html_string, base_url=request.build_absolute_uri('/')).write_pdf()
                    response = HttpResponse(pdf_file, content_type='application/pdf')
                    filename = f"Budget_Book_{context['fiscal_year'].year_name.replace(' ', '_')}.pdf"
                    response['Content-Disposition'] = f'attachment; filename="{filename}"'
                    return response
                except Exception as e:  # Catch broader runtime errors (e.g., missing libgobject)
                    messages.warning(
                        request,
                        'WeasyPrint failed to generate PDF on this system. '
                        'Falling back to xhtml2pdf. '
                        f'Details: {e}'
                    )
                    engine = 'xhtml2pdf'

            if engine == 'xhtml2pdf':
                try:
                    from xhtml2pdf import pisa
                    from io import BytesIO
                    result = BytesIO()
                    pdf = pisa.pisaDocument(BytesIO(html_string.encode('utf-8')), result)
                    if not pdf.err:
                        response = HttpResponse(result.getvalue(), content_type='application/pdf')
                        filename = f"Budget_Book_{context['fiscal_year'].year_name.replace(' ', '_')}.pdf"
                        response['Content-Disposition'] = f'attachment; filename="{filename}"'
                        return response
                    else:
                        messages.warning(
                            request,
                            'xhtml2pdf failed to generate PDF. Displaying HTML version for printing.'
                        )
                except Exception:
                    messages.warning(
                        request,
                        'PDF library not available. Displaying HTML version. '
                        'Use the Print button or add ?engine=xhtml2pdf after installing xhtml2pdf.'
                    )
        
        # Fallback: Render HTML template for browser printing
        return TemplateResponse(
            request,
            'budgeting/reports/budget_book_pdf.html',
            context
        )

