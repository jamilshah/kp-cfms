"""
-------------------------------------------------------------------------
System: KP-CFMS (Computerized Financial Management System)
Client: Local Government Department, Khyber Pakhtunkhwa
Team Lead: Jamil Shah
Developers: Ali Asghar, Akhtar Munir and Zarif Khan
Description: Views for the expenditure module including Bill and
             Payment management with workflow support.
-------------------------------------------------------------------------
"""
from typing import Any, Dict, Optional
from decimal import Decimal
from django.views.generic import (
    ListView, CreateView, DetailView, UpdateView, TemplateView, View
)
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy, reverse
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.db import transaction
from django.utils.translation import gettext_lazy as _

from apps.users.permissions import MakerRequiredMixin, CheckerRequiredMixin, ApproverRequiredMixin
from apps.expenditure.models import Payee, Bill, Payment, BillStatus
from apps.expenditure.forms import (
    PayeeForm, BillForm, BillSubmitForm, BillApprovalForm, PaymentForm,
    BillLineFormSet
)
from apps.budgeting.models import FiscalYear, BudgetAllocation, Department
from apps.finance.models import BudgetHead, AccountType, FunctionCode
from apps.core.exceptions import BudgetExceededException, WorkflowTransitionException


class ExpenditureDashboardView(LoginRequiredMixin, TemplateView):
    """
    Dashboard view for the expenditure module.
    
    Shows summary statistics for bills and payments.
    """
    template_name = 'expenditure/dashboard.html'
    
    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        user = self.request.user
        org = getattr(user, 'organization', None)
        
        # Get current operating fiscal year (based on today's date)
        active_fy = FiscalYear.get_current_operating_year(org) if org else None
        
        if org and active_fy:
            bills_qs = Bill.objects.filter(
                organization=org,
                fiscal_year=active_fy
            )
            
            context.update({
                'active_fiscal_year': active_fy,
                'total_bills': bills_qs.count(),
                'draft_bills': bills_qs.filter(status=BillStatus.DRAFT).count(),
                'submitted_bills': bills_qs.filter(status=BillStatus.SUBMITTED).count(),
                'verified_bills': bills_qs.filter(status=BillStatus.VERIFIED).count(),
                'approved_bills': bills_qs.filter(status=BillStatus.APPROVED).count(),
                'paid_bills': bills_qs.filter(status=BillStatus.PAID).count(),
                'pending_approval': bills_qs.filter(status__in=[BillStatus.SUBMITTED, BillStatus.VERIFIED]),
                'recent_bills': bills_qs.order_by('-created_at')[:5],
            })
        
        return context


class PayeeListView(LoginRequiredMixin, ListView):
    """List view for payees/vendors."""
    
    model = Payee
    template_name = 'expenditure/payee_list.html'
    context_object_name = 'payees'
    paginate_by = 20
    
    def get_queryset(self):
        user = self.request.user
        org = getattr(user, 'organization', None)
        if org:
            return Payee.objects.filter(organization=org).order_by('name')
        return Payee.objects.none()


class PayeeCreateView(LoginRequiredMixin, MakerRequiredMixin, CreateView):
    """Create view for payees/vendors.
    
    Requires Dealing Assistant (Maker) role.
    """
    
    model = Payee
    form_class = PayeeForm
    template_name = 'expenditure/payee_form.html'
    success_url = reverse_lazy('expenditure:payee_list')
    
    def form_valid(self, form):
        user = self.request.user
        form.instance.organization = getattr(user, 'organization', None)
        form.instance.created_by = user
        messages.success(self.request, _('Payee created successfully.'))
        return super().form_valid(form)


class PayeeUpdateView(LoginRequiredMixin, UpdateView):
    """Update view for payees/vendors."""
    
    model = Payee
    form_class = PayeeForm
    template_name = 'expenditure/payee_form.html'
    success_url = reverse_lazy('expenditure:payee_list')
    
    def get_queryset(self):
        user = self.request.user
        org = getattr(user, 'organization', None)
        if org:
            return Payee.objects.filter(organization=org)
        return Payee.objects.none()
    
    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        messages.success(self.request, _('Payee updated successfully.'))
        return super().form_valid(form)


class BillListView(LoginRequiredMixin, ListView):
    """
    List view for bills with status filtering.
    
    Shows bills for the user's organization with status badges
    and action buttons based on workflow state.
    """
    
    model = Bill
    template_name = 'expenditure/bill_list.html'
    context_object_name = 'bills'
    paginate_by = 20
    
    def get_queryset(self):
        user = self.request.user
        org = getattr(user, 'organization', None)
        
        if not org:
            return Bill.objects.none()
        
        queryset = Bill.objects.filter(
            organization=org
        ).select_related(
            'payee', 'fiscal_year'
        ).order_by('-bill_date', '-created_at')
        
        # Filter by status if provided
        status = self.request.GET.get('status')
        if status and status in dict(BillStatus.choices):
            queryset = queryset.filter(status=status)
        
        # Filter by fiscal year if provided
        fy_id = self.request.GET.get('fiscal_year')
        if fy_id:
            queryset = queryset.filter(fiscal_year_id=fy_id)
        
        return queryset
    
    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        user = self.request.user
        org = getattr(user, 'organization', None)
        
        context['status_choices'] = BillStatus.choices
        context['current_status'] = self.request.GET.get('status', '')
        
        if org:
            context['fiscal_years'] = FiscalYear.objects.filter(
                organization=org
            ).order_by('-start_date')
        
        return context


class BillCreateView(LoginRequiredMixin, MakerRequiredMixin, CreateView):
    """
    Create view for new bills.
    
    Requires Dealing Assistant (Maker) role.
    Automatically assigns organization and calculates net_amount.
    Requires an active (current operating) fiscal year.
    """
    
    model = Bill
    form_class = BillForm
    template_name = 'expenditure/bill_form.html'
    
    def dispatch(self, request, *args, **kwargs):
        """Check for current operating fiscal year before allowing access."""
        user = request.user
        org = getattr(user, 'organization', None)
        
        if org:
            # Check if there's a current operating fiscal year
            active_fy = FiscalYear.get_current_operating_year(org)
            if not active_fy:
                messages.error(
                    request, 
                    _('No active fiscal year found for the current period. '
                      'Please contact your administrator to set up a fiscal year.')
                )
                return redirect('expenditure:dashboard')
            

        
        return super().dispatch(request, *args, **kwargs)
    
    def get_form_kwargs(self) -> Dict[str, Any]:
        kwargs = super().get_form_kwargs()
        user = self.request.user
        kwargs['organization'] = getattr(user, 'organization', None)
        kwargs['user'] = user
        return kwargs
    
    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        user = self.request.user
        org = getattr(user, 'organization', None)
        if org:
            context['current_fiscal_year'] = FiscalYear.get_current_operating_year(org)
            
        # Get fiscal year for formset
        fy = FiscalYear.get_current_operating_year(org) if org else None
            
        if self.request.POST:
            context['lines'] = BillLineFormSet(
                self.request.POST,
                organization=org,
                fiscal_year=fy
            )
        else:
            context['lines'] = BillLineFormSet(
                organization=org,
                fiscal_year=fy
            )
        return context
    
    @transaction.atomic
    def form_valid(self, form):
        context = self.get_context_data()
        lines = context['lines']
        
        user = self.request.user
        org = getattr(user, 'organization', None)
        
        if lines.is_valid():
            form.instance.organization = org
            form.instance.created_by = user
            
            # Set fiscal year
            if form._current_fiscal_year:
                form.instance.fiscal_year = form._current_fiscal_year
            
            # Save Bill (Parent)
            self.object = form.save(commit=False)
            
            # --- Auto-calculate Gross Amount from Lines ---
            # Use line amounts to set gross_amount, ignoring the field input if necessary, 
            # OR validate they match. For strictness/UX, let's override gross_amount with sum of lines.
            
            # Access cleaned_data of lines (list of dicts)
            total_amount = Decimal('0.00')
            for line_form in lines.forms:
                if line_form.cleaned_data and not line_form.cleaned_data.get('DELETE', False):
                    amount = line_form.cleaned_data.get('amount')
                    if amount:
                        total_amount += amount
            
            self.object.gross_amount = total_amount
            
            # Recalculate Net Amount
            tax = form.cleaned_data.get('tax_amount', Decimal('0.00'))
            self.object.tax_amount = tax
            self.object.net_amount = total_amount - tax
            
            self.object.save()
            
            # Save Lines
            lines.instance = self.object
            lines.save()
            
            messages.success(self.request, _('Bill created successfully.'))
            return redirect(self.get_success_url())
        else:
            # If lines are invalid, render form with errors
            return self.render_to_response(self.get_context_data(form=form))
    
    def get_success_url(self) -> str:
        return reverse('expenditure:bill_detail', kwargs={'pk': self.object.pk})


class BillDetailView(LoginRequiredMixin, DetailView):
    """
    Detail view for bills.
    
    Shows bill details, workflow actions (submit/approve/reject),
    and payment status.
    """
    
    model = Bill
    template_name = 'expenditure/bill_detail.html'
    context_object_name = 'bill'
    
    def get_queryset(self):
        user = self.request.user
        org = getattr(user, 'organization', None)
        if org:
            return Bill.objects.filter(
                organization=org
            ).select_related(
                'payee', 'fiscal_year',
                'liability_voucher', 'submitted_by', 'approved_by'
            ).prefetch_related(
                'lines', 'lines__budget_head'
            )
        return Bill.objects.none()
    
    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        bill = self.object
        user = self.request.user
        
        # Check user permissions for workflow actions
        context['can_submit'] = bill.status == BillStatus.DRAFT
        
        # Accountant can verify submitted bills
        context['can_verify'] = (
            bill.status == BillStatus.SUBMITTED and
            (user.is_checker() or user.is_superuser)
        )
        
        # TMO can approve only verified bills
        context['can_approve'] = (
            bill.status == BillStatus.VERIFIED and
            (user.is_approver() or user.is_superuser)
        )
        
        context['can_pay'] = bill.status == BillStatus.APPROVED
        
        # Get budget allocation info for each line
        line_allocations = []
        if bill.fiscal_year:
            for line in bill.lines.all():
                try:
                    allocation = BudgetAllocation.objects.get(
                        organization=bill.organization,
                        fiscal_year=bill.fiscal_year,
                        budget_head=line.budget_head
                    )
                    line_allocations.append({
                        'line': line,
                        'allocation': allocation
                    })
                except BudgetAllocation.DoesNotExist:
                    line_allocations.append({
                        'line': line,
                        'allocation': None
                    })
        context['line_allocations'] = line_allocations
        
        # Get payments
        context['payments'] = bill.payments.all()
        
        return context


class BillSubmitView(LoginRequiredMixin, View):
    """View to submit a bill for approval."""
    
    def post(self, request: HttpRequest, pk: int) -> HttpResponse:
        user = request.user
        org = getattr(user, 'organization', None)
        
        bill = get_object_or_404(Bill, pk=pk, organization=org)
        
        try:
            bill.submit(user)
            messages.success(request, _('Bill submitted for approval.'))
        except WorkflowTransitionException as e:
            messages.error(request, str(e))
        
        return redirect('expenditure:bill_detail', pk=pk)


class BillVerifyView(LoginRequiredMixin, View):
    """View to verify a bill (Accountant step)."""
    
    def post(self, request: HttpRequest, pk: int) -> HttpResponse:
        user = request.user
        org = getattr(user, 'organization', None)
        
        bill = get_object_or_404(Bill, pk=pk, organization=org)
        
        if not (user.is_checker() or user.is_superuser):
            messages.error(request, _('Permission denied. Only Accountants can verify bills.'))
            return redirect('expenditure:bill_detail', pk=pk)
            
        try:
            bill.verify(user)
            messages.success(request, _('Bill verified successfully. Forwarded to TMO for approval.'))
        except WorkflowTransitionException as e:
            messages.error(request, str(e))
        
        return redirect('expenditure:bill_detail', pk=pk)


class BillApproveView(LoginRequiredMixin, View):
    """View to approve or reject a bill."""
    
    def post(self, request: HttpRequest, pk: int) -> HttpResponse:
        user = request.user
        org = getattr(user, 'organization', None)
        
        bill = get_object_or_404(Bill, pk=pk, organization=org)
        
        # Check permission (TMO)
        if not (user.is_approver() or user.is_superuser):
             messages.error(request, _('Permission denied. Only TMO can approve bills.'))
             return redirect('expenditure:bill_detail', pk=pk)
        
        form = BillApprovalForm(request.POST)
        
        if form.is_valid():
            action = form.cleaned_data['action']
            
            try:
                if action == 'approve':
                    bill.approve(user)
                    messages.success(
                        request, 
                        _('Bill approved successfully. Liability recorded in GL.')
                    )
                else:
                    reason = form.cleaned_data['rejection_reason']
                    bill.reject(user, reason)
                    messages.warning(request, _('Bill rejected.'))
            except (WorkflowTransitionException, BudgetExceededException) as e:
                messages.error(request, str(e))
            except Exception as e:
                messages.error(request, _('An error occurred: ') + str(e))
        else:
            for error in form.errors.values():
                messages.error(request, error)
        
        return redirect('expenditure:bill_detail', pk=pk)


class PaymentCreateView(LoginRequiredMixin, CreateView):
    """
    Create view for payments.
    
    Issues a cheque payment against an approved bill.
    """
    
    model = Payment
    form_class = PaymentForm
    template_name = 'expenditure/payment_form.html'
    
    def get_form_kwargs(self) -> Dict[str, Any]:
        kwargs = super().get_form_kwargs()
        user = self.request.user
        org = getattr(user, 'organization', None)
        kwargs['organization'] = org
        
        # If bill_id is provided in URL, pre-select the bill
        bill_id = self.kwargs.get('bill_pk')
        if bill_id:
            try:
                bill = Bill.objects.get(
                    pk=bill_id,
                    organization=org,
                    status=BillStatus.APPROVED
                )
                kwargs['initial'] = {'bill': bill, 'amount': bill.net_amount}
            except Bill.DoesNotExist:
                pass
        
        return kwargs
    
    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        
        # If bill_id is provided, include bill details
        bill_id = self.kwargs.get('bill_pk')
        if bill_id:
            user = self.request.user
            org = getattr(user, 'organization', None)
            try:
                context['bill'] = Bill.objects.get(
                    pk=bill_id,
                    organization=org
                )
            except Bill.DoesNotExist:
                pass
        
        return context
    
    @transaction.atomic
    def form_valid(self, form):
        user = self.request.user
        org = getattr(user, 'organization', None)
        
        form.instance.organization = org
        form.instance.created_by = user
        
        # Set amount from bill
        bill = form.cleaned_data['bill']
        form.instance.amount = bill.net_amount
        
        # Save the payment
        self.object = form.save()
        
        # Post the payment immediately
        try:
            self.object.post(user)
            messages.success(
                self.request, 
                _('Payment posted successfully. Bill marked as PAID.')
            )
        except Exception as e:
            messages.error(self.request, _('Payment created but posting failed: ') + str(e))
        
        return redirect(self.get_success_url())
    
    def get_success_url(self) -> str:
        return reverse('expenditure:bill_detail', kwargs={'pk': self.object.bill.pk})


class PaymentListView(LoginRequiredMixin, ListView):
    """List view for payments."""
    
    model = Payment
    template_name = 'expenditure/payment_list.html'
    context_object_name = 'payments'
    paginate_by = 20
    
    def get_queryset(self):
        user = self.request.user
        org = getattr(user, 'organization', None)
        
        if not org:
            return Payment.objects.none()
        
        return Payment.objects.filter(
            organization=org
        ).select_related(
            'bill', 'bill__payee', 'bank_account'
        ).order_by('-cheque_date', '-created_at')


class BillAmountAPIView(LoginRequiredMixin, View):
    """API view to get bill amount for payment form."""
    
    def get(self, request: HttpRequest, pk: int) -> JsonResponse:
        user = request.user
        org = getattr(user, 'organization', None)
        
        try:
            bill = Bill.objects.get(pk=pk, organization=org)
            return JsonResponse({
                'success': True,
                'net_amount': str(bill.net_amount),
                'payee_name': bill.payee.name,
                'description': bill.description[:100]
            })
        except Bill.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Bill not found'
            }, status=404)


def load_functions(request):
    """
    AJAX view to load functions filtered by department.
    Returns HTML with function options including default and usage notes.
    """
    department_id = request.GET.get('department')
    functions = FunctionCode.objects.none()
    default_id = None
    
    if department_id:
        try:
            dept = Department.objects.get(id=department_id)
            functions = dept.related_functions.all().order_by('code')
            default_id = dept.default_function_id if dept.default_function else None
        except (ValueError, TypeError, Department.DoesNotExist):
            pass
            
    return render(request, 'expenditure/partials/function_options.html', {
        'functions': functions,
        'default_id': default_id
    })


def load_budget_heads(request):
    """
    AJAX view to load budget heads filtered by function.
    
    All budget heads are now UNIVERSAL scope.
    Filtering is done by the selected function.
    Excludes salary heads (A01*) as they have separate salary bill workflow.
    """
    function_id = request.GET.get('function')
    department_id = request.GET.get('department')  # Keep for backward compatibility
    department = None
    
    # Base queryset - Expenditure heads only (Bills are for expenses, not revenue)
    # Exclude salary heads (A01*) as they have their own workflow
    budget_heads = BudgetHead.objects.filter(
        global_head__account_type=AccountType.EXPENDITURE,
        posting_allowed=True,
        is_active=True
    ).exclude(
        global_head__code__startswith='A01'
    ).select_related('global_head', 'function').order_by('global_head__code', 'function__code')
    
    # Filter by function (primary method)
    if function_id:
        try:
            budget_heads = budget_heads.filter(function_id=function_id)
            # Get department for display purposes
            function = FunctionCode.objects.get(id=function_id)
            # Try to find which department this function belongs to
            dept_with_function = Department.objects.filter(related_functions=function).first()
            if dept_with_function:
                department = dept_with_function
        except (ValueError, TypeError, FunctionCode.DoesNotExist):
            pass
    # Fallback to department filtering (for backward compatibility)
    elif department_id:
        try:
            department = Department.objects.get(id=department_id)
            
            # Only show budget heads for functions assigned to this department
            budget_heads = budget_heads.filter(
                function__in=department.related_functions.all()
            )
            
        except (ValueError, TypeError, Department.DoesNotExist):
            pass
            
    return render(request, 'expenditure/partials/budget_head_options.html', {
        'budget_heads': budget_heads,
        'department': department
    })

class BankAccountNextChequeAPIView(LoginRequiredMixin, View):
    """API view to get next available cheque number for a bank account."""
    
    def get(self, request: HttpRequest, pk: int) -> JsonResponse:
        user = request.user
        org = getattr(user, 'organization', None)
        
        from apps.core.models import BankAccount
        from apps.finance.models import ChequeLeaf, LeafStatus
        
        try:
            # Ensure account belongs to user's org
            account = BankAccount.objects.get(pk=pk, organization=org)
            
            # Find first available leaf across all active books
            # Ordered by book issue date/serial to ensure we use oldest books first
            next_leaf = ChequeLeaf.objects.filter(
                book__bank_account=account,
                book__is_active=True,
                status=LeafStatus.AVAILABLE
            ).order_by('book__issue_date', 'book__start_serial', 'id').first()
            
            if next_leaf:
                return JsonResponse({
                    'success': True,
                    'next_cheque_number': next_leaf.leaf_number
                })
            else:
                return JsonResponse({
                    'success': False, 
                    'error': 'No available cheques found in active books.'
                })
                
        except BankAccount.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Bank account not found.'
            }, status=404)
