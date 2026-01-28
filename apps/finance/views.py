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
from typing import Dict, Any

from apps.users.permissions import AdminRequiredMixin
from apps.finance.models import BudgetHead, Fund, ChequeBook, ChequeLeaf, LeafStatus
from apps.finance.forms import BudgetHeadForm, ChequeBookForm, ChequeLeafCancelForm
from apps.core.models import BankAccount


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
    """List all Budget Heads (Chart of Accounts)."""
    model = BudgetHead
    template_name = 'finance/budget_head_list.html'
    context_object_name = 'budget_heads'
    ordering = ['pifra_object', 'tma_sub_object']
    # Disable pagination for Tree View
    paginate_by = None

    def get_queryset(self):
        qs = super().get_queryset()
        query = self.request.GET.get('q')
        if query:
            qs = qs.filter(
                tma_description__icontains=query
            ) | qs.filter(
                pifra_object__icontains=query
            )
        return qs

    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context['page_title'] = _('Chart of Accounts Management')
        
        # Build Tree Structure (Flat list with levels)
        # Assumes queryset is sorted by pifra_object
        heads = list(context['budget_heads'])
        tree_list = []
        
        # Stack keeps track of current branch chain: [(code, level), ...]
        stack = []
        
        for head in heads:
            code = head.pifra_object
            
            # Pop stack until we find the parent (or stack empty)
            # Parent is defined as: current code starts with parent code AND is strictly longer
            while stack and (not code.startswith(stack[-1][0]) or code == stack[-1][0]):
                stack.pop()
            
            level = len(stack)
            
            # Add to tree list wrapper
            tree_list.append({
                'obj': head,
                'level': level,
                'is_leaf': True, # Will update next
                'parent_code': stack[-1][0] if stack else None
            })
            
            # If previous item was parent of this one, update previous item's leaf status
            if stack:
                 # Find the last item added to tree_list which corresponds to stack[-1]
                 # Actually, simplify: if we added a child, the parent (stack top) is not a leaf.
                 # We can't easily track back to the dict object unless we keep it in stack.
                 pass

            # Push current to stack
            stack.append((code, level))
            
        # Post-process to identifying leaves (visual polish, optional)
        # Simple scan: if next item.level > current.level, current is not leaf.
        for i in range(len(tree_list) - 1):
            if tree_list[i+1]['level'] > tree_list[i]['level']:
                tree_list[i]['is_leaf'] = False
                
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
