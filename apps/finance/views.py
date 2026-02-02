"""
Views for the Finance module.
"""
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy, reverse
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.shortcuts import get_object_or_404, redirect
from django.http import HttpResponseRedirect
from django.db import models
from typing import Dict, Any

from apps.users.permissions import AdminRequiredMixin, MakerRequiredMixin
from apps.finance.models import (
    BudgetHead, Fund, ChequeBook, ChequeLeaf, LeafStatus,
    Voucher, JournalEntry
)
from apps.finance.forms import BudgetHeadForm, ChequeBookForm, ChequeLeafCancelForm, VoucherForm
from apps.core.models import BankAccount
from apps.budgeting.models import FiscalYear


class FundListView(LoginRequiredMixin, AdminRequiredMixin, ListView):
    """List all funds."""
    model = Fund
    template_name = 'finance/setup_fund_list.html'
    context_object_name = 'funds'
    ordering = ['code']


class FundCreateView(LoginRequiredMixin, AdminRequiredMixin, CreateView):
    """Create new fund."""
    model = Fund
    fields = ['code', 'name', 'description', 'is_active']
    template_name = 'budgeting/setup_form.html'
    success_url = reverse_lazy('budgeting:setup_funds')
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['code'].widget.attrs.update({'class': 'form-control'})
        form.fields['name'].widget.attrs.update({'class': 'form-control'})
        form.fields['description'].widget.attrs.update({'class': 'form-control', 'rows': 3})
        form.fields['is_active'].widget.attrs.update({'class': 'form-check-input'})
        return form
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = _('Add New Fund')
        context['back_url'] = reverse_lazy('budgeting:setup_funds')
        return context


class FundUpdateView(LoginRequiredMixin, AdminRequiredMixin, UpdateView):
    """Update fund."""
    model = Fund
    fields = ['code', 'name', 'description', 'is_active']
    template_name = 'budgeting/setup_form.html'
    success_url = reverse_lazy('budgeting:setup_funds')
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['code'].widget.attrs.update({'class': 'form-control', 'readonly': 'readonly'})
        form.fields['name'].widget.attrs.update({'class': 'form-control'})
        form.fields['description'].widget.attrs.update({'class': 'form-control', 'rows': 3})
        form.fields['is_active'].widget.attrs.update({'class': 'form-check-input'})
        return form
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = _('Edit Fund')
        context['back_url'] = reverse_lazy('budgeting:setup_funds')
        return context


class FundDeleteView(LoginRequiredMixin, AdminRequiredMixin, DeleteView):
    """Delete fund."""
    model = Fund
    template_name = 'budgeting/setup_confirm_delete.html'
    success_url = reverse_lazy('budgeting:setup_funds')
    context_object_name = 'item'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = _('Delete Fund')
        context['back_url'] = reverse_lazy('budgeting:setup_funds')
        return context

class BudgetHeadListView(LoginRequiredMixin, AdminRequiredMixin, ListView):
    """List all Budget Heads (Chart of Accounts) with tree structure and filtering.
    
    OPTIMIZATION STRATEGY:
    - select_related: fund, function, global_head + global_head__minor (for account_type access)
    - Efficient major/minor heads query using database-level distinct
    - Pagination to avoid loading all 2838 items in memory at once
    - Cached lookups for filter options
    """
    model = BudgetHead
    template_name = 'finance/budget_head_list.html'
    context_object_name = 'budget_heads'
    ordering = ['function__code', 'global_head__code']
    paginate_by = 50  # Paginate to improve performance

    def get_queryset(self):
        # CRITICAL: Include select_related for all ForeignKey relationships
        # to avoid N+1 queries in the template
        qs = super().get_queryset().select_related(
            'fund',
            'function',
            'global_head',
            'global_head__minor',  # Needed for major_code access
        )
        
        # Apply filters
        query = self.request.GET.get('q')
        if query:
            qs = qs.filter(
                models.Q(global_head__name__icontains=query) |
                models.Q(global_head__code__icontains=query)
            )
        
        # Account type filter
        account_type = self.request.GET.get('account_type')
        if account_type:
            qs = qs.filter(global_head__account_type=account_type)
        
        # Fund filter
        fund_id = self.request.GET.get('fund')
        if fund_id:
            qs = qs.filter(fund_id=fund_id)
        
        # Function filter
        function_id = self.request.GET.get('function')
        if function_id:
            qs = qs.filter(function_id=function_id)

        # Department filter
        department_id = self.request.GET.get('department')
        if department_id:
            from apps.budgeting.models import Department
            try:
                dept = Department.objects.get(id=department_id)
                qs = qs.filter(function__in=dept.related_functions.all())
            except Department.DoesNotExist:
                pass # Or handle error
        
        # Active status filter
        is_active = self.request.GET.get('is_active')
        if is_active:
            qs = qs.filter(is_active=is_active == 'true')
        
        # Fund type filter
        fund_type = self.request.GET.get('fund_type')
        if fund_type:
            qs = qs.filter(fund_type=fund_type)
        
        # Major head filter (first 3 characters)
        major_head = self.request.GET.get('major_head')
        if major_head:
            qs = qs.filter(global_head__code__startswith=major_head)
        
        # Minor head filter (first 4 characters)
        minor_head = self.request.GET.get('minor_head')
        if minor_head:
            qs = qs.filter(global_head__code__startswith=minor_head)
        
        return qs

    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        from apps.finance.models import Fund, FunctionCode, AccountType, FundType
        from apps.budgeting.models import Department
        from django.db.models import F
        
        context = super().get_context_data(**kwargs)
        context['page_title'] = _('Chart of Accounts Management')
        
        # Cache filter options using select_for_update would be better in production
        context['departments'] = Department.objects.filter(is_active=True).order_by('name')
        context['funds'] = Fund.objects.filter(is_active=True).order_by('code')
        
        # Filter functions based on selected department if applicable
        functions_qs = FunctionCode.objects.filter(is_active=True)
        department_id = self.request.GET.get('department')
        if department_id:
            try:
                dept = Department.objects.get(id=department_id)
                functions_qs = functions_qs.filter(id__in=dept.related_functions.all())
            except Department.DoesNotExist:
                pass
            
        context['functions'] = functions_qs.order_by('code')
        context['account_types'] = AccountType.choices
        context['fund_types'] = FundType.choices
        
        # OPTIMIZED: Get unique major and minor heads using database-level distinct
        # No longer iterating through all heads in Python
        all_heads = BudgetHead.objects.values_list(
            'global_head__code', flat=True
        ).distinct().order_by('global_head__code')
        
        major_heads = set()
        minor_heads = set()
        
        for code in all_heads:
            if len(code) >= 3:
                major = code[:3]  # First 3 chars (e.g., A01, B02, G05)
                major_heads.add(major)
            if len(code) >= 4:
                minor = code[:4]  # First 4 chars (e.g., A011, B013, G021)
                minor_heads.add(minor)
        
        context['major_heads'] = sorted(major_heads)
        context['minor_heads'] = sorted(minor_heads)
        
        # Build Grouped Structure (Function -> BudgetHeads)
        # NOTE: With pagination, only builds tree for current page items
        heads = list(context['budget_heads'])
        tree_list = []
        
        current_function_code = None
        
        for head in heads:
            func_code = head.function.code if head.function else 'None'
            
            # Start a new group if function changes
            if func_code != current_function_code:
                current_function_code = func_code
                tree_list.append({
                    'obj': head.function,
                    'level': 0,
                    'is_leaf': False,
                    'is_group_header': True,
                    'parent_code': None,
                    'has_children': True,
                    'group_name': f"{head.function.code} - {head.function.name}"
                })
            
            # Add the BudgetHead
            tree_list.append({
                'obj': head,
                'level': 1,
                'is_leaf': True,
                'is_group_header': False,
                'parent_code': func_code,
                'has_children': False
            })
            
        context['tree_nodes'] = tree_list
        return context


class BudgetHeadCreateView(LoginRequiredMixin, AdminRequiredMixin, CreateView):
    """Create new Budget Head."""
    model = BudgetHead
    form_class = BudgetHeadForm
    template_name = 'finance/budget_head_form.html'
    success_url = reverse_lazy('budgeting:setup_coa_list')

    def form_valid(self, form):
        messages.success(self.request, _('Budget Head created successfully.'))
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = _('Add New Budget Head')
        context['back_url'] = self.success_url
        return context


class BudgetHeadUpdateView(LoginRequiredMixin, AdminRequiredMixin, UpdateView):
    """Update Budget Head."""
    model = BudgetHead
    form_class = BudgetHeadForm
    template_name = 'finance/budget_head_form.html'
    success_url = reverse_lazy('budgeting:setup_coa_list')

    def form_valid(self, form):
        messages.success(self.request, _('Budget Head updated successfully.'))
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = _('Edit Budget Head')
        context['back_url'] = self.success_url
        return context


class BudgetHeadDeleteView(LoginRequiredMixin, AdminRequiredMixin, DeleteView):
    """Delete Budget Head."""
    model = BudgetHead
    template_name = 'finance/budget_head_confirm_delete.html'
    success_url = reverse_lazy('budgeting:setup_coa_list')

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, _('Budget Head deleted successfully.'))
        return super().delete(request, *args, **kwargs)


# ============================================================================
# Cheque Book Management Views
# ============================================================================

class ChequeBookListView(LoginRequiredMixin, AdminRequiredMixin, ListView):
    """
    List all cheque books grouped by Bank Account.
    
    Shows: Bank, Book No, Range, Total Leaves, Available Leaves.
    """
    model = ChequeBook
    template_name = 'finance/chequebook_list.html'
    context_object_name = 'chequebooks'
    
    def get_queryset(self):
        """Filter by user's organization."""
        user = self.request.user
        org = getattr(user, 'organization', None)
        
        qs = ChequeBook.objects.select_related('bank_account').order_by(
            'bank_account__title', '-issue_date'
        )
        
        if org:
            qs = qs.filter(bank_account__organization=org)
        
        return qs
    
    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context['page_title'] = _('Cheque Book Management')
        
        # Group by bank account
        grouped = {}
        for book in context['chequebooks']:
            bank = book.bank_account
            if bank.pk not in grouped:
                grouped[bank.pk] = {
                    'bank': bank,
                    'books': []
                }
            grouped[bank.pk]['books'].append(book)
        
        context['grouped_books'] = grouped
        return context


class ChequeBookCreateView(LoginRequiredMixin, AdminRequiredMixin, CreateView):
    """
    Create a new Cheque Book.
    
    Automatically generates ChequeLeaf records on save.
    """
    model = ChequeBook
    form_class = ChequeBookForm
    template_name = 'finance/chequebook_form.html'
    success_url = reverse_lazy('budgeting:setup_chequebooks')
    
    def get_form_kwargs(self):
        """Pass organization to form."""
        kwargs = super().get_form_kwargs()
        user = self.request.user
        kwargs['organization'] = getattr(user, 'organization', None)
        return kwargs
    
    def form_valid(self, form):
        """Save and show success message."""
        response = super().form_valid(form)
        leaf_count = self.object.total_leaves
        messages.success(
            self.request,
            _(f'Cheque Book "{self.object.book_no}" created with {leaf_count} leaves.')
        )
        return response
    
    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context['page_title'] = _('Register New Cheque Book')
        context['back_url'] = self.success_url
        return context


class ChequeBookDetailView(LoginRequiredMixin, AdminRequiredMixin, DetailView):
    """
    View details of a Cheque Book including all leaves.
    
    Allows cancelling individual leaves.
    """
    model = ChequeBook
    template_name = 'finance/chequebook_detail.html'
    context_object_name = 'chequebook'
    
    def get_queryset(self):
        """Filter by user's organization."""
        user = self.request.user
        org = getattr(user, 'organization', None)
        
        qs = ChequeBook.objects.select_related('bank_account')
        
        if org:
            qs = qs.filter(bank_account__organization=org)
        
        return qs
    
    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context['page_title'] = f"Cheque Book: {self.object.book_no}"
        context['leaves'] = self.object.leaves.all().order_by('id')
        context['cancel_form'] = ChequeLeafCancelForm()
        context['leaf_statuses'] = LeafStatus
        return context


class ChequeLeafCancelView(LoginRequiredMixin, AdminRequiredMixin, View):
    """
    Cancel a cheque leaf (mark as void).
    """
    
    def post(self, request, pk, leaf_pk):
        """Process leaf cancellation."""
        book = get_object_or_404(ChequeBook, pk=pk)
        leaf = get_object_or_404(ChequeLeaf, pk=leaf_pk, book=book)
        
        form = ChequeLeafCancelForm(request.POST)
        if form.is_valid():
            try:
                reason = form.cleaned_data['reason']
                leaf.mark_cancelled(reason)
                messages.success(
                    request,
                    _(f'Cheque leaf {leaf.leaf_number} has been cancelled.')
                )
            except Exception as e:
                messages.error(request, str(e))
        else:
            messages.error(request, _('Please provide a reason for cancellation.'))
        
        return HttpResponseRedirect(reverse('budgeting:setup_chequebook_detail', kwargs={'pk': pk}))


class ChequeLeafDamageView(LoginRequiredMixin, AdminRequiredMixin, View):
    """
    Mark a cheque leaf as damaged.
    """
    
    def post(self, request, pk, leaf_pk):
        """Process leaf damage marking."""
        book = get_object_or_404(ChequeBook, pk=pk)
        leaf = get_object_or_404(ChequeLeaf, pk=leaf_pk, book=book)
        
        form = ChequeLeafCancelForm(request.POST)
        if form.is_valid():
            try:
                reason = form.cleaned_data['reason']
                leaf.mark_damaged(reason)
                messages.success(
                    request,
                    _(f'Cheque leaf {leaf.leaf_number} has been marked as damaged.')
                )
            except Exception as e:
                messages.error(request, str(e))
        else:
            messages.error(request, _('Please provide a reason.'))
        
        return HttpResponseRedirect(reverse('budgeting:setup_chequebook_detail', kwargs={'pk': pk}))


# ============================================================================
# Bank Reconciliation Views
# ============================================================================

from apps.finance.models import BankStatement, BankStatementLine, JournalEntry, StatementStatus
from apps.finance.forms import (
    BankStatementForm, BankStatementLineForm, ManualMatchForm, StatementUploadForm
)
from apps.finance.services_reconciliation import (
    ReconciliationEngine, parse_bank_statement_csv
)
from django.http import JsonResponse
from django.db import transaction


class BankStatementListView(LoginRequiredMixin, ListView):
    """
    List all bank statements for reconciliation.
    """
    model = BankStatement
    template_name = 'finance/statement_list.html'
    context_object_name = 'statements'
    paginate_by = 20
    
    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        org = getattr(user, 'organization', None)
        
        if org:
            qs = qs.filter(bank_account__organization=org)
        
        return qs.select_related('bank_account', 'year').order_by('-year__start_date', '-month')
    
    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context['page_title'] = _('Bank Statements')
        return context


class BankStatementCreateView(LoginRequiredMixin, CreateView):
    """
    Create a new bank statement and optionally upload CSV.
    """
    model = BankStatement
    form_class = BankStatementForm
    template_name = 'finance/statement_form.html'
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['organization'] = getattr(self.request.user, 'organization', None)
        return kwargs
    
    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context['page_title'] = _('Create Bank Statement')
        context['upload_form'] = StatementUploadForm()
        return context
    
    def form_valid(self, form):
        """Save statement and process CSV if uploaded."""
        statement = form.save(commit=False)
        statement.created_by = self.request.user
        statement.save()
        
        # Check if CSV file was uploaded with the statement
        if statement.file:
            try:
                content = statement.file.read().decode('utf-8')
                lines_created, errors = parse_bank_statement_csv(content, statement)
                
                if lines_created > 0:
                    messages.success(
                        self.request,
                        _(f'Statement created with {lines_created} lines imported from CSV.')
                    )
                
                if errors:
                    for error in errors[:5]:  # Show first 5 errors
                        messages.warning(self.request, error)
                    if len(errors) > 5:
                        messages.warning(
                            self.request,
                            _(f'... and {len(errors) - 5} more errors.')
                        )
            except Exception as e:
                messages.warning(
                    self.request,
                    _(f'Statement created but CSV import failed: {str(e)}')
                )
        else:
            messages.success(self.request, _('Bank statement created successfully.'))
        
        return HttpResponseRedirect(
            reverse('finance:statement_detail', kwargs={'pk': statement.pk})
        )
    
    def get_success_url(self):
        return reverse('finance:statement_list')


class BankStatementDetailView(LoginRequiredMixin, DetailView):
    """
    View statement details and reconciliation status.
    """
    model = BankStatement
    template_name = 'finance/statement_detail.html'
    context_object_name = 'statement'
    
    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        org = getattr(user, 'organization', None)
        
        if org:
            qs = qs.filter(bank_account__organization=org)
        
        return qs.select_related('bank_account', 'year')
    
    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context['page_title'] = f"Statement: {self.object}"
        context['lines'] = self.object.lines.all().order_by('date', 'id')
        context['line_form'] = BankStatementLineForm()
        context['upload_form'] = StatementUploadForm()
        
        # Get reconciliation summary
        engine = ReconciliationEngine(self.object)
        context['brs_summary'] = engine.get_brs_summary()
        
        return context


class BankStatementUploadCSVView(LoginRequiredMixin, View):
    """
    Upload and parse CSV file for an existing statement.
    """
    
    def post(self, request, pk):
        statement = get_object_or_404(BankStatement, pk=pk)
        
        # Check organization access
        org = getattr(request.user, 'organization', None)
        if org and statement.bank_account.organization != org:
            messages.error(request, _('Access denied.'))
            return HttpResponseRedirect(reverse('finance:statement_list'))
        
        if statement.is_locked:
            messages.error(request, _('Cannot modify a locked statement.'))
            return HttpResponseRedirect(
                reverse('finance:statement_detail', kwargs={'pk': pk})
            )
        
        form = StatementUploadForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                csv_file = form.cleaned_data['csv_file']
                content = csv_file.read().decode('utf-8')
                lines_created, errors = parse_bank_statement_csv(content, statement)
                
                if lines_created > 0:
                    messages.success(
                        request,
                        _(f'{lines_created} lines imported from CSV.')
                    )
                
                if errors:
                    for error in errors[:5]:
                        messages.warning(request, error)
                    if len(errors) > 5:
                        messages.warning(
                            request,
                            _(f'... and {len(errors) - 5} more errors.')
                        )
            except Exception as e:
                messages.error(request, _(f'CSV import failed: {str(e)}'))
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, error)
        
        return HttpResponseRedirect(
            reverse('finance:statement_detail', kwargs={'pk': pk})
        )


class BankStatementAddLineView(LoginRequiredMixin, View):
    """
    Add a single line to a statement.
    """
    
    def post(self, request, pk):
        statement = get_object_or_404(BankStatement, pk=pk)
        
        if statement.is_locked:
            messages.error(request, _('Cannot modify a locked statement.'))
            return HttpResponseRedirect(
                reverse('finance:statement_detail', kwargs={'pk': pk})
            )
        
        form = BankStatementLineForm(request.POST)
        if form.is_valid():
            line = form.save(commit=False)
            line.statement = statement
            line.save()
            messages.success(request, _('Statement line added.'))
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
        
        return HttpResponseRedirect(
            reverse('finance:statement_detail', kwargs={'pk': pk})
        )


class ReconciliationWorkbenchView(LoginRequiredMixin, DetailView):
    """
    Two-column reconciliation workbench.
    
    Left: Unreconciled GL entries (Cash Book)
    Right: Unreconciled Bank Statement lines
    """
    model = BankStatement
    template_name = 'finance/reconciliation_workbench.html'
    context_object_name = 'statement'
    
    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        org = getattr(user, 'organization', None)
        
        if org:
            qs = qs.filter(bank_account__organization=org)
        
        return qs.select_related('bank_account', 'year')
    
    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context['page_title'] = f"Reconciliation: {self.object}"
        
        engine = ReconciliationEngine(self.object)
        
        # Get unreconciled items for both sides
        context['gl_entries'] = engine.get_unreconciled_gl_entries()
        context['statement_lines'] = engine.get_unreconciled_statement_lines()
        context['brs_summary'] = engine.get_brs_summary()
        context['match_form'] = ManualMatchForm()
        
        return context


class AutoReconcileView(LoginRequiredMixin, View):
    """
    Trigger automatic reconciliation.
    """
    
    def post(self, request, pk):
        statement = get_object_or_404(BankStatement, pk=pk)
        
        if statement.is_locked:
            messages.error(request, _('Cannot reconcile a locked statement.'))
            return HttpResponseRedirect(
                reverse('finance:reconciliation_workbench', kwargs={'pk': pk})
            )
        
        try:
            engine = ReconciliationEngine(statement)
            result = engine.auto_reconcile()
            
            messages.success(
                request,
                _(f'Auto-reconciliation complete: {result.matched_count} items matched. '
                  f'{result.unmatched_statement_lines} statement lines and '
                  f'{result.unmatched_gl_entries} GL entries remain unmatched.')
            )
        except Exception as e:
            messages.error(request, _(f'Auto-reconciliation failed: {str(e)}'))
        
        return HttpResponseRedirect(
            reverse('finance:reconciliation_workbench', kwargs={'pk': pk})
        )


class ManualMatchView(LoginRequiredMixin, View):
    """
    Manually match selected items.
    """
    
    @transaction.atomic
    def post(self, request, pk):
        statement = get_object_or_404(BankStatement, pk=pk)
        
        if statement.is_locked:
            return JsonResponse({
                'success': False,
                'error': 'Statement is locked.'
            })
        
        form = ManualMatchForm(request.POST)
        if not form.is_valid():
            return JsonResponse({
                'success': False,
                'error': 'Invalid form data.'
            })
        
        try:
            engine = ReconciliationEngine(statement)
            matched = engine.manual_match(
                form.cleaned_data['statement_line_ids'],
                form.cleaned_data['journal_entry_ids']
            )
            
            return JsonResponse({
                'success': True,
                'matched_count': matched,
                'message': f'{matched} items matched successfully.'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })


class UnmatchLineView(LoginRequiredMixin, View):
    """
    Unmatch a statement line.
    """
    
    def post(self, request, pk, line_pk):
        statement = get_object_or_404(BankStatement, pk=pk)
        line = get_object_or_404(BankStatementLine, pk=line_pk, statement=statement)
        
        if statement.is_locked:
            messages.error(request, _('Cannot unmatch items in a locked statement.'))
        else:
            try:
                line.unmatch()
                messages.success(request, _('Item unmatched successfully.'))
            except Exception as e:
                messages.error(request, str(e))
        
        return HttpResponseRedirect(
            reverse('finance:reconciliation_workbench', kwargs={'pk': pk})
        )


class LockStatementView(LoginRequiredMixin, View):
    """
    Lock a statement after reconciliation is complete.
    """
    
    def post(self, request, pk):
        statement = get_object_or_404(BankStatement, pk=pk)
        
        try:
            statement.lock()
            messages.success(request, _('Statement locked successfully.'))
        except Exception as e:
            messages.error(request, str(e))
        
        return HttpResponseRedirect(
            reverse('finance:statement_detail', kwargs={'pk': pk})
        )


class BRSSummaryView(LoginRequiredMixin, DetailView):
    """
    Bank Reconciliation Statement summary view.
    """
    model = BankStatement
    template_name = 'finance/brs_summary.html'
    context_object_name = 'statement'
    
    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        org = getattr(user, 'organization', None)
        
        if org:
            qs = qs.filter(bank_account__organization=org)
        
        return qs.select_related('bank_account', 'year')
    
    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context['page_title'] = f"BRS: {self.object}"
        
        engine = ReconciliationEngine(self.object)
        context['brs'] = engine.get_brs_summary()
        
        return context


# =========================================================================
# Manual Journal Vouchers (Phase 10: General Journal)
# =========================================================================

class VoucherListView(LoginRequiredMixin, ListView):
    """
    List all vouchers (auto-generated and manual).
    
    Filter by:
    - Voucher Type (JV, PV, RV)
    - Date Range
    - Posted Status
    """
    model = Voucher
    template_name = 'finance/voucher_list.html'
    context_object_name = 'vouchers'
    paginate_by = 25
    
    def get_queryset(self):
        user = self.request.user
        org = getattr(user, 'organization', None)
        
        qs = Voucher.objects.filter(organization=org).select_related(
            'fiscal_year', 'fund', 'posted_by'
        ).prefetch_related('entries')
        
        # Filter by voucher type
        voucher_type = self.request.GET.get('type')
        if voucher_type:
            qs = qs.filter(voucher_type=voucher_type)
        
        # Filter by date range
        date_from = self.request.GET.get('date_from')
        date_to = self.request.GET.get('date_to')
        if date_from:
            qs = qs.filter(date__gte=date_from)
        if date_to:
            qs = qs.filter(date__lte=date_to)
        
        # Filter by posted status
        status = self.request.GET.get('status')
        if status == 'posted':
            qs = qs.filter(is_posted=True)
        elif status == 'draft':
            qs = qs.filter(is_posted=False)
        
        return qs.order_by('-date', '-voucher_no')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'General Journal'
        context['filter_type'] = self.request.GET.get('type', '')
        context['filter_date_from'] = self.request.GET.get('date_from', '')
        context['filter_date_to'] = self.request.GET.get('date_to', '')
        context['filter_status'] = self.request.GET.get('status', '')
        return context


class VoucherCreateView(LoginRequiredMixin, MakerRequiredMixin, CreateView):
    """
    Create a manual Journal Voucher with multiple lines.
    
    Requires Dealing Assistant (Maker) role.
    Uses formset for journal entries with dynamic add/remove.
    Validates that Sum(Debit) == Sum(Credit).
    """
    model = Voucher
    template_name = 'finance/voucher_form.html'
    form_class = VoucherForm
    
    def get_success_url(self):
        return reverse('finance:voucher_detail', kwargs={'pk': self.object.pk})
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['organization'] = getattr(self.request.user, 'organization', None)
        return kwargs
    
    def get_context_data(self, **kwargs):
        from django.forms import inlineformset_factory
        from apps.finance.forms import JournalEntryForm
        
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Create Journal Voucher'
        
        JournalEntryFormSet = inlineformset_factory(
            Voucher,
            JournalEntry,
            form=JournalEntryForm,
            extra=2,
            can_delete=True,
            min_num=2,
            validate_min=True
        )
        
        if self.request.POST:
            context['formset'] = JournalEntryFormSet(
                self.request.POST,
                instance=self.object,
                form_kwargs={'organization': getattr(self.request.user, 'organization', None)}
            )
        else:
            context['formset'] = JournalEntryFormSet(
                instance=self.object,
                form_kwargs={'organization': getattr(self.request.user, 'organization', None)}
            )
        
        return context
    
    def form_valid(self, form):
        from django.forms import inlineformset_factory
        from apps.finance.forms import JournalEntryForm
        from decimal import Decimal
        
        context = self.get_context_data()
        formset = context['formset']
        
        # Validate formset
        if not formset.is_valid():
            return self.form_invalid(form)
        
        # Use atomic transaction
        with transaction.atomic():
            # Set organization
            user = self.request.user
            org = getattr(user, 'organization', None)
            
            form.instance.organization = org
            # voucher_type is now set from the form (JV or CV)
            form.instance.created_by = user
            
            # Determine fiscal year from date
            try:
                fiscal_year = FiscalYear.objects.filter(
                    organization=org,
                    start_date__lte=form.instance.date,
                    end_date__gte=form.instance.date
                ).first()
                
                if not fiscal_year:
                    messages.error(self.request, _('No fiscal year found for the selected date.'))
                    return self.form_invalid(form)
                    
                form.instance.fiscal_year = fiscal_year
            except Exception as e:
                messages.error(self.request, _('Error determining fiscal year: ') + str(e))
                return self.form_invalid(form)
            
            # Generate voucher number based on voucher type
            # Format: JV-YYYY-NNN or CV-YYYY-NNN
            voucher_type = form.instance.voucher_type
            year = fiscal_year.start_date.year
            last_voucher = Voucher.objects.filter(
                organization=org,
                fiscal_year=fiscal_year,
                voucher_type=voucher_type
            ).order_by('-voucher_no').first()
            
            if last_voucher and last_voucher.voucher_no:
                try:
                    last_num = int(last_voucher.voucher_no.split('-')[-1])
                    next_num = last_num + 1
                except (ValueError, IndexError):
                    next_num = 1
            else:
                next_num = 1
            
            form.instance.voucher_no = f"{voucher_type}-{year}-{next_num:03d}"
            
            # Save voucher
            self.object = form.save()
            
            # Save formset
            formset.instance = self.object
            formset.save()
            
            # Calculate totals
            total_debit = Decimal('0.00')
            total_credit = Decimal('0.00')
            
            for entry in self.object.entries.all():
                total_debit += entry.debit
                total_credit += entry.credit
            
            # Validate balance
            if total_debit != total_credit:
                messages.error(
                    self.request,
                    _('Voucher is not balanced. Debit: {}, Credit: {}').format(
                        total_debit, total_credit
                    )
                )
                return self.form_invalid(form)
            
            if total_debit == Decimal('0.00'):
                messages.error(self.request, _('Voucher has no entries or all amounts are zero.'))
                return self.form_invalid(form)
            
            messages.success(self.request, _('Journal Voucher created successfully.'))
            return HttpResponseRedirect(self.get_success_url())


class VoucherDetailView(LoginRequiredMixin, DetailView):
    """
    Display voucher header and journal entries.
    
    Shows:
    - Voucher header info
    - Table of journal entries (Dr/Cr)
    - Post button if status is DRAFT
    """
    model = Voucher
    template_name = 'finance/voucher_detail.html'
    context_object_name = 'voucher'
    
    def get_queryset(self):
        user = self.request.user
        org = getattr(user, 'organization', None)
        return Voucher.objects.filter(organization=org).select_related(
            'fiscal_year', 'fund', 'posted_by', 'created_by'
        ).prefetch_related('entries__budget_head')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = f"Voucher: {self.object.voucher_no}"
        context['entries'] = self.object.entries.all().select_related('budget_head')
        context['total_debit'] = self.object.get_total_debit()
        context['total_credit'] = self.object.get_total_credit()
        context['is_balanced'] = self.object.is_balanced()
        return context


class PostVoucherView(LoginRequiredMixin, View):
    """
    Post a voucher to the General Ledger.
    
    Only allowed if:
    - Voucher is not already posted
    - Voucher is balanced
    """
    
    def post(self, request, pk):
        user = request.user
        org = getattr(user, 'organization', None)
        
        voucher = get_object_or_404(
            Voucher.objects.filter(organization=org),
            pk=pk
        )
        
        # Check if already posted
        if voucher.is_posted:
            messages.warning(request, _('Voucher is already posted.'))
            return redirect('finance:voucher_detail', pk=pk)
        
        # Check if balanced
        if not voucher.is_balanced():
            messages.error(
                request,
                _('Cannot post unbalanced voucher. Debit: {}, Credit: {}').format(
                    voucher.get_total_debit(),
                    voucher.get_total_credit()
                )
            )
            return redirect('finance:voucher_detail', pk=pk)
        
        try:
            with transaction.atomic():
                voucher.post_voucher(user)
                messages.success(request, _('Voucher posted successfully.'))
        except Exception as e:
            messages.error(request, _('Error posting voucher: ') + str(e))
        
        return redirect('finance:voucher_detail', pk=pk)


# ============================================================================
# AJAX Views for Dynamic Filtering
# ============================================================================

from django.shortcuts import render
from apps.finance.models import FunctionCode, AccountType
from apps.budgeting.models import Department


def load_functions(request):
    """
    AJAX view to load functions filtered by department.
    Used by VoucherForm header filters.
    """
    department_id = request.GET.get('department')
    functions = FunctionCode.objects.none()
    
    if department_id:
        try:
            dept = Department.objects.get(id=department_id)
            functions = dept.related_functions.all().order_by('code')
        except (ValueError, TypeError, Department.DoesNotExist):
            pass
            
    return render(request, 'expenditure/partials/function_options.html', {'functions': functions})


def load_budget_heads_options(request):
    """
    AJAX view to load budget head options filtered by department and/or function.
    Returns options as a script that updates all budget_head selects in the formset.
    """
    department_id = request.GET.get('department')
    function_id = request.GET.get('function')
    account_type = request.GET.get('account_type')
    
    # Base queryset - all posting-allowed heads
    budget_heads = BudgetHead.objects.filter(
        posting_allowed=True,
        is_active=True
    ).select_related('global_head', 'function').order_by('global_head__code')
    
    if account_type:
        budget_heads = budget_heads.filter(global_head__account_type=account_type)
    
    # Filter by GlobalHead department scope
    if department_id:
        try:
            dept = Department.objects.get(id=department_id)
            # Only show budget heads whose GlobalHead is applicable to this department
            from django.db.models import Q
            budget_heads = budget_heads.filter(
                Q(global_head__scope='UNIVERSAL') |
                Q(global_head__applicable_departments=dept)
            )
        except (ValueError, TypeError, Department.DoesNotExist):
            pass
    
    # Filter by allocation (Scenario 1: only show heads with budget)
    try:
        user = request.user
        org = getattr(user, 'organization', None)
        if org:
            from django.apps import apps
            from django.db.models import Exists, OuterRef
            
            FiscalYear = apps.get_model('budgeting', 'FiscalYear')
            BudgetAllocation = apps.get_model('budgeting', 'BudgetAllocation')
            
            # Get current operating fiscal year
            fy = FiscalYear.get_current_operating_year(org)
            if fy:
                has_allocation = BudgetAllocation.objects.filter(
                    organization=org,
                    fiscal_year=fy,
                    budget_head=OuterRef('pk')
                )
                
                budget_heads = budget_heads.annotate(
                    has_allocation=Exists(has_allocation)
                ).filter(has_allocation=True)
    except Exception as e:
        print(f"ERROR in load_budget_heads_options: {e}")
        # Fallback: don't filter by allocation if error occurs, to avoid 500
        pass
    
    print(f"DEBUG: load_budget_heads_options params - Dept: {department_id}, Func: {function_id}, Type: {account_type}")
    
    if function_id:
        budget_heads = budget_heads.filter(function_id=function_id)
    elif department_id:
        try:
            dept = Department.objects.get(id=department_id)
            budget_heads = budget_heads.filter(function__in=dept.related_functions.all())
        except (ValueError, TypeError, Department.DoesNotExist):
            pass
            
    print(f"DEBUG: Returning {budget_heads.count()} budget heads")
    return render(request, 'finance/partials/budget_head_formset_options.html', {'budget_heads': budget_heads})

