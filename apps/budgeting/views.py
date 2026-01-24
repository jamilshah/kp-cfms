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
    QuarterlyRelease, SAERecord, BudgetStatus, ReleaseQuarter
)
from apps.budgeting.forms import (
    FiscalYearForm, ReceiptEstimateForm, ExpenditureEstimateForm,
    ScheduleOfEstablishmentForm, BudgetApprovalForm, QuarterlyReleaseForm,
    BudgetSearchForm
)
from apps.budgeting.services import (
    finalize_budget, process_quarterly_release,
    validate_reserve_requirement, validate_zero_deficit
)
from apps.users.permissions import (
    MakerRequiredMixin, ApproverRequiredMixin, FinanceOfficerRequiredMixin
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
        
        # Calculate totals
        queryset = self.get_queryset()
        context['total_sanctioned'] = queryset.aggregate(
            total=Sum('sanctioned_posts')
        )['total'] or 0
        context['total_occupied'] = queryset.aggregate(
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
