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
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy, reverse
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.core.exceptions import ValidationError
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
        active_fy = FiscalYear.get_current_operating_year() if org else None
        
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
            'payee', 'fiscal_year', 'department'
        ).order_by('-bill_date', '-created_at')
        
        # Apply department-level filtering if enabled
        if user.should_see_own_department_only():
            queryset = queryset.filter(department=user.department)
        
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
            context['fiscal_years'] = FiscalYear.objects.all().order_by('-start_date')
        
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
            active_fy = FiscalYear.get_current_operating_year()
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
            context['current_fiscal_year'] = FiscalYear.get_current_operating_year()
            
        # Get fiscal year for formset
        fy = FiscalYear.get_current_operating_year() if org else None
        
        # Get department and function from form data
        department_id = None
        function_id = None
        if self.request.POST:
            department_id = self.request.POST.get('department')
            function_id = self.request.POST.get('function')
            
        if self.request.POST:
            context['lines'] = BillLineFormSet(
                self.request.POST,
                organization=org,
                fiscal_year=fy,
                department_id=department_id,
                function_id=function_id
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
            total_amount = Decimal('0.00')
            for line_form in lines.forms:
                if line_form.cleaned_data and not line_form.cleaned_data.get('DELETE', False):
                    amount = line_form.cleaned_data.get('amount')
                    if amount:
                        total_amount += amount
            
            self.object.gross_amount = total_amount
            
            # --- Recalculate taxes based on actual gross from lines ---
            if total_amount > 0 and self.object.payee:
                from apps.expenditure.services_tax import TaxCalculator
                calculator = TaxCalculator()
                temp_bill = Bill(
                    payee=self.object.payee,
                    transaction_type=self.object.transaction_type,
                    gross_amount=total_amount
                )
                # Pass vendor invoice GST if provided
                invoice_gst = self.object.sales_tax_invoice_amount
                taxes = calculator.calculate_taxes(temp_bill, sales_tax_invoice_amount=invoice_gst)
                
                self.object.income_tax_amount = taxes['income_tax']
                self.object.sales_tax_amount = taxes['sales_tax']
                self.object.stamp_duty_amount = taxes['stamp_duty']
                self.object.tax_amount = taxes['total_tax']
                self.object.net_amount = taxes['net_amount']
            else:
                self.object.tax_amount = Decimal('0.00')
                self.object.net_amount = total_amount
            
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
        
        # Finance Officer can pre-audit submitted bills
        context['can_pre_audit'] = (
            bill.status == BillStatus.SUBMITTED and
            (user.has_any_role(['FINANCE_OFFICER']) or user.is_superuser)
        )
        
        # Tehsil Officer Finance can verify audited bills
        context['can_verify'] = (
            bill.status == BillStatus.AUDITED and
            (user.has_any_role(['TOF', 'TO_FINANCE', 'ACCOUNTANT', 'AC']) or user.is_superuser)
        )
        
        # TMO can approve only verified bills
        context['can_approve'] = (
            bill.status == BillStatus.VERIFIED and
            (user.is_approver() or user.is_superuser)
        )
        
        context['can_pay'] = bill.status == BillStatus.APPROVED
        
        # Get budget allocation info aggregated by budget head
        line_allocations = []
        if bill.fiscal_year:
            # Group lines by budget_head and sum amounts
            from collections import defaultdict
            budget_head_totals = defaultdict(Decimal)
            budget_head_objects = {}
            
            for line in bill.lines.all():
                budget_head_totals[line.budget_head.id] += line.amount
                budget_head_objects[line.budget_head.id] = line.budget_head
            
            # Create allocation entries for each unique budget head
            for budget_head_id, total_amount in budget_head_totals.items():
                budget_head = budget_head_objects[budget_head_id]
                try:
                    allocation = BudgetAllocation.objects.get(
                        organization=bill.organization,
                        fiscal_year=bill.fiscal_year,
                        budget_head=budget_head
                    )
                    line_allocations.append({
                        'budget_head': budget_head,
                        'total_amount': total_amount,
                        'allocation': allocation
                    })
                except BudgetAllocation.DoesNotExist:
                    line_allocations.append({
                        'budget_head': budget_head,
                        'total_amount': total_amount,
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


class BillPreAuditView(LoginRequiredMixin, View):
    """View to pre-audit a bill with comprehensive review (Finance Officer step)."""
    
    def get(self, request: HttpRequest, pk: int) -> HttpResponse:
        """Display pre-audit form."""
        from apps.expenditure.forms import BillPreAuditForm
        
        user = request.user
        org = getattr(user, 'organization', None)
        
        bill = get_object_or_404(Bill, pk=pk, organization=org)
        
        # Check permission
        if not (user.has_any_role(['FINANCE_OFFICER']) or user.is_superuser):
            messages.error(request, _('Permission denied. Only Finance Officers can pre-audit bills.'))
            return redirect('expenditure:bill_detail', pk=pk)
        
        # Check status
        if bill.status != BillStatus.SUBMITTED:
            messages.error(request, _('Bill must be in SUBMITTED status for pre-audit.'))
            return redirect('expenditure:bill_detail', pk=pk)
        
        form = BillPreAuditForm(bill=bill)
        
        return render(request, 'expenditure/bill_pre_audit.html', {
            'bill': bill,
            'form': form,
        })
    
    def post(self, request: HttpRequest, pk: int) -> HttpResponse:
        """Process pre-audit with comprehensive review."""
        from apps.expenditure.forms import BillPreAuditForm
        from django.utils import timezone
        
        user = request.user
        org = getattr(user, 'organization', None)
        
        bill = get_object_or_404(Bill, pk=pk, organization=org)
        
        # Check permission
        if not (user.has_any_role(['FINANCE_OFFICER']) or user.is_superuser):
            messages.error(request, _('Permission denied.'))
            return redirect('expenditure:bill_detail', pk=pk)
        
        form = BillPreAuditForm(request.POST, bill=bill)
        
        if form.is_valid():
            # Update transaction type if changed
            bill.transaction_type = form.cleaned_data['transaction_type']
            
            # Update tax amounts
            bill.income_tax_amount = form.cleaned_data['income_tax_amount']
            bill.sales_tax_amount = form.cleaned_data['sales_tax_amount']
            bill.stamp_duty_amount = form.cleaned_data['stamp_duty_amount']
            
            # Recalculate totals
            bill.tax_amount = (
                bill.income_tax_amount + 
                bill.sales_tax_amount + 
                bill.stamp_duty_amount
            )
            bill.net_amount = bill.gross_amount - bill.tax_amount
            
            # Save audit notes and adjustment reason if provided
            audit_notes = form.cleaned_data.get('audit_notes', '').strip()
            reason = form.cleaned_data.get('adjustment_reason', '').strip()
            
            if audit_notes or reason:
                # Add to bill description for audit trail
                audit_log = f"\n\n[FO Pre-Audit by {user.get_full_name()} on {timezone.now().strftime('%d-%b-%Y %H:%M')}]"
                if audit_notes:
                    audit_log += f"\nObservations: {audit_notes}"
                if reason:
                    audit_log += f"\nChanges Made: {reason}"
                bill.description += audit_log
            
            bill.save()
            
            # Move to AUDITED status
            try:
                bill.pre_audit(user)
                messages.success(request, _('Bill pre-audited successfully. Forwarded to TO for verification.'))
            except WorkflowTransitionException as e:
                messages.error(request, str(e))
            
            return redirect('expenditure:bill_detail', pk=pk)
        
        return render(request, 'expenditure/bill_pre_audit.html', {
            'bill': bill,
            'form': form,
        })



class BillVerifyView(LoginRequiredMixin, View):
    """View to verify a bill (Accountant step)."""
    
    def post(self, request: HttpRequest, pk: int) -> HttpResponse:
        user = request.user
        org = getattr(user, 'organization', None)
        
        bill = get_object_or_404(Bill, pk=pk, organization=org)
        
        # Check permission (Tehsil Officer Finance or Accountant)
        if not (user.has_any_role(['TOF', 'ACCOUNTANT']) or user.is_superuser):
            messages.error(request, _('Permission denied. Only Tehsil Officer Finance or Accountant can verify bills.'))
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
            except ValidationError as e:
                # Extract clean message from ValidationError
                if hasattr(e, 'message_dict'):
                    for field_errors in e.message_dict.values():
                        for err in field_errors:
                            messages.error(request, err)
                elif hasattr(e, 'messages'):
                    for msg in e.messages:
                        messages.error(request, msg)
                else:
                    messages.error(request, str(e))
            except Exception as e:
                messages.error(request, _('An unexpected error occurred. Please contact your System Administrator.'))
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
        
        queryset = Payment.objects.filter(
            organization=org
        ).select_related(
            'bill', 'bill__payee', 'bill__department', 'bank_account'
        ).order_by('-cheque_date', '-created_at')
        
        # Apply department-level filtering if enabled
        if user.should_see_own_department_only():
            queryset = queryset.filter(bill__department=user.department)
        
        return queryset


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
    AJAX view to load budget heads filtered by department and function.
    
    NEW BEHAVIOR (after CoA restructuring):
    - Filters by department FK directly on BudgetHead
    - When both department AND function provided: returns precise filtered set
    - Excludes salary heads (A01*) as they have separate salary bill workflow.
    """
    function_id = request.GET.get('function')
    department_id = request.GET.get('department')
    department = None
    
    # Base queryset - Expenditure heads only (Bills are for expenses, not revenue)
    # Exclude salary heads (A01*) as they have their own workflow
    budget_heads = BudgetHead.objects.filter(
        global_head__account_type=AccountType.EXPENDITURE,
        posting_allowed=True,
        is_active=True
    ).exclude(
        global_head__code__startswith='A01'
    ).select_related('global_head', 'function', 'department').order_by('global_head__code', 'function__code')
    
    # PRIMARY FILTER: Use both department + function for most precise results
    if department_id and function_id:
        try:
            department = Department.objects.get(id=department_id)
            # Use the new department FK directly for precise filtering
            budget_heads = budget_heads.filter(
                department_id=department_id,
                function_id=function_id
            )
        except (ValueError, TypeError, Department.DoesNotExist):
            pass
    # Filter by function only
    elif function_id:
        try:
            budget_heads = budget_heads.filter(function_id=function_id)
            # Get department for display - try from budget head's department first
            first_head = budget_heads.first()
            if first_head and first_head.department:
                department = first_head.department
            else:
                # Fallback: Try to find via M2M
                function = FunctionCode.objects.get(id=function_id)
                dept_with_function = Department.objects.filter(related_functions=function).first()
                if dept_with_function:
                    department = dept_with_function
        except (ValueError, TypeError, FunctionCode.DoesNotExist):
            pass
    # Filter by department only
    elif department_id:
        try:
            department = Department.objects.get(id=department_id)
            # Use the new department FK directly
            budget_heads = budget_heads.filter(department=department)
        except (ValueError, TypeError, Department.DoesNotExist):
            pass
            
    return render(request, 'expenditure/partials/budget_head_options.html', {
        'budget_heads': budget_heads,
        'department': department
    })

@login_required
def get_payee_default_budget_head(request):
    """
    AJAX endpoint to get the budget head for a payee's default expense type.
    
    Takes payee_id and function_id, returns the matching budget head ID.
    """
    payee_id = request.GET.get('payee')
    function_id = request.GET.get('function')
    
    if not payee_id or not function_id:
        return JsonResponse({'budget_head_id': None})
    
    try:
        from apps.expenditure.models import Payee
        from apps.finance.models import BudgetHead
        
        payee = Payee.objects.select_related('default_global_head').get(id=payee_id)
        
        # Check if payee has a default global head
        if not payee.default_global_head:
            return JsonResponse({'budget_head_id': None})
        
        # Find the budget head for this global head + function combination
        budget_head = BudgetHead.objects.filter(
            global_head=payee.default_global_head,
            function_id=function_id,
            is_active=True
        ).first()
        
        if budget_head:
            return JsonResponse({
                'budget_head_id': budget_head.id,
                'budget_head_code': budget_head.code,
                'budget_head_name': budget_head.name
            })
        else:
            return JsonResponse({'budget_head_id': None})
            
    except (ValueError, TypeError, Payee.DoesNotExist):
        return JsonResponse({'budget_head_id': None})

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


def load_payees(request):
    """
    AJAX view to load payees filtered by organization.
    Returns HTML <option> list.
    """
    user = request.user
    org = getattr(user, 'organization', None)
    
    payees = Payee.objects.none()
    if org:
        payees = Payee.objects.filter(organization=org).order_by('name')
        
    return render(request, 'expenditure/partials/payee_options.html', {'payees': payees})


@login_required
def calculate_taxes_ajax(request):
    """
    AJAX endpoint to calculate taxes in real-time.
    
    Accepts: payee_id, transaction_type, gross_amount
    Returns: JSON with calculated tax amounts
    """
    try:
        payee_id = request.GET.get('payee')
        transaction_type = request.GET.get('transaction_type')
        gross_amount = request.GET.get('gross_amount')
        sales_tax_invoice = request.GET.get('sales_tax_invoice_amount')
        
        if not all([payee_id, transaction_type, gross_amount]):
            return JsonResponse({
                'success': False,
                'error': 'Missing required parameters'
            })
        
        # Get payee
        payee = Payee.objects.get(id=payee_id)
        gross_amount = Decimal(gross_amount)
        sales_tax_invoice_amount = Decimal(sales_tax_invoice) if sales_tax_invoice else None
        
        # Create temporary bill for calculation
        temp_bill = Bill(
            payee=payee,
            transaction_type=transaction_type,
            gross_amount=gross_amount
        )
        
        # Calculate taxes
        from apps.expenditure.services_tax import TaxCalculator
        calculator = TaxCalculator()
        taxes = calculator.calculate_taxes(temp_bill, sales_tax_invoice_amount=sales_tax_invoice_amount)
        
        return JsonResponse({
            'success': True,
            'income_tax': str(taxes['income_tax']),
            'sales_tax': str(taxes['sales_tax']),
            'stamp_duty': str(taxes['stamp_duty']),
            'total_tax': str(taxes['total_tax']),
            'net_amount': str(taxes['net_amount'])
        })
        
    except Payee.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Payee not found'
        })
    except (ValueError, TypeError, Exception) as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })
