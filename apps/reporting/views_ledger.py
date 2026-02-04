"""
-------------------------------------------------------------------------
System: KP-CFMS (Computerized Financial Management System)
Client: Local Government Department, Khyber Pakhtunkhwa
Team Lead: Jamil Shah
Developers: Ali Asghar, Akhtar Munir and Zarif Khan
Description: Views for financial ledger reports including General Ledger,
             Trial Balance, and Account Statement.
-------------------------------------------------------------------------
"""
from decimal import Decimal
from datetime import date, datetime
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Sum, Q, F, Case, When, Value, DecimalField
from django.db.models.functions import Coalesce

from apps.core.mixins import TenantAwareMixin
from apps.finance.models import JournalEntry, BudgetHead, Voucher
from apps.budgeting.models import FiscalYear


class GeneralLedgerView(LoginRequiredMixin, TenantAwareMixin, TemplateView):
    """
    General Ledger by Account Report.
    
    Shows all journal entries for a selected budget head with running balance.
    """
    template_name = 'reporting/general_ledger.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        organization = self.request.user.organization
        
        # Get filter parameters
        budget_head_id = self.request.GET.get('budget_head')
        date_from = self.request.GET.get('date_from')
        date_to = self.request.GET.get('date_to')
        
        # Budget heads loaded via AJAX autocomplete for performance
        
        # Get active fiscal year for default dates
        fiscal_year = FiscalYear.objects.filter(
            organization=organization,
            is_active=True
        ).first()
        
        if fiscal_year:
            context['default_date_from'] = fiscal_year.start_date
            context['default_date_to'] = fiscal_year.end_date
        
        # If budget head selected, fetch entries
        if budget_head_id:
            try:
                budget_head = BudgetHead.objects.select_related(
                    'global_head', 'fund', 'function'
                ).get(pk=budget_head_id)
                context['selected_budget_head'] = budget_head
                
                # Cache account type to avoid repeated lookups
                account_type = budget_head.global_head.account_type
                is_debit_account = account_type in ['AST', 'EXP']
                
                # Build query with optimized select_related
                entries_query = JournalEntry.objects.filter(
                    budget_head=budget_head,
                    voucher__is_posted=True,
                    voucher__organization=organization
                ).select_related('voucher', 'budget_head')
                
                # Apply date filters
                if date_from:
                    entries_query = entries_query.filter(voucher__date__gte=date_from)
                    context['filter_date_from'] = date_from
                if date_to:
                    entries_query = entries_query.filter(voucher__date__lte=date_to)
                    context['filter_date_to'] = date_to
                
                # Order by date and voucher
                entries = entries_query.order_by('voucher__date', 'voucher__id')
                
                # Calculate running balance
                entries_with_balance = []
                running_balance = Decimal('0.00')
                
                for entry in entries:
                    # Use cached account type check
                    if is_debit_account:
                        running_balance += (entry.debit - entry.credit)
                    else:  # LIABILITY, EQUITY, REVENUE
                        running_balance += (entry.credit - entry.debit)
                    
                    entries_with_balance.append({
                        'entry': entry,
                        'balance': running_balance
                    })
                
                context['entries'] = entries_with_balance
                context['final_balance'] = running_balance
                
            except BudgetHead.DoesNotExist:
                context['error'] = 'Selected budget head not found.'
        
        context['filter_budget_head'] = budget_head_id
        
        return context


class TrialBalanceView(LoginRequiredMixin, TenantAwareMixin, TemplateView):
    """
    Trial Balance Report.
    
    Shows all budget heads with their debit and credit balances as of a specific date.
    """
    template_name = 'reporting/trial_balance.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        organization = self.request.user.organization
        
        # Get as-of date parameter
        as_of_date_str = self.request.GET.get('as_of_date')
        if as_of_date_str:
            as_of_date = datetime.strptime(as_of_date_str, '%Y-%m-%d').date()
            context['as_of_date'] = as_of_date
        else:
            # Default to today
            as_of_date = date.today()
            context['as_of_date'] = as_of_date
        
        
        # Get all budget heads with balances (optimized with select_related)
        budget_heads = BudgetHead.objects.filter(
            is_active=True
        ).select_related('global_head', 'fund', 'function').annotate(
            total_debit=Coalesce(
                Sum('journal_entries__debit',
                    filter=Q(journal_entries__voucher__is_posted=True,
                            journal_entries__voucher__organization=organization,
                            journal_entries__voucher__date__lte=as_of_date)),
                Decimal('0.00')
            ),
            total_credit=Coalesce(
                Sum('journal_entries__credit',
                    filter=Q(journal_entries__voucher__is_posted=True,
                            journal_entries__voucher__organization=organization,
                            journal_entries__voucher__date__lte=as_of_date)),
                Decimal('0.00')
            )
        ).filter(
            Q(total_debit__gt=0) | Q(total_credit__gt=0)
        ).order_by('fund', 'function__code', 'global_head__code')
        
        # Calculate balances and categorize
        accounts_data = []
        total_debit_balance = Decimal('0.00')
        total_credit_balance = Decimal('0.00')
        
        for head in budget_heads:
            # Calculate net balance based on account type
            if head.global_head.account_type in ['AST', 'EXP']:
                # Debit balance accounts
                balance = head.total_debit - head.total_credit
                if balance > 0:
                    debit_balance = balance
                    credit_balance = Decimal('0.00')
                else:
                    debit_balance = Decimal('0.00')
                    credit_balance = abs(balance)
            else:  # LIABILITY, EQUITY, REVENUE
                # Credit balance accounts
                balance = head.total_credit - head.total_debit
                if balance > 0:
                    credit_balance = balance
                    debit_balance = Decimal('0.00')
                else:
                    credit_balance = Decimal('0.00')
                    debit_balance = abs(balance)
            
            accounts_data.append({
                'head': head,
                'debit_balance': debit_balance,
                'credit_balance': credit_balance
            })
            
            total_debit_balance += debit_balance
            total_credit_balance += credit_balance
        
        context['accounts'] = accounts_data
        context['total_debit_balance'] = total_debit_balance
        context['total_credit_balance'] = total_credit_balance
        context['is_balanced'] = (total_debit_balance == total_credit_balance)
        
        return context


class AccountStatementView(LoginRequiredMixin, TenantAwareMixin, TemplateView):
    """
    Account Statement Report.
    
    Similar to General Ledger but formatted as a statement with opening/closing balances.
    """
    template_name = 'reporting/account_statement.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        organization = self.request.user.organization
        
        # Get filter parameters
        budget_head_id = self.request.GET.get('budget_head')
        date_from = self.request.GET.get('date_from')
        date_to = self.request.GET.get('date_to')
        
        # Budget heads loaded via AJAX autocomplete for performance
        
        # Get active fiscal year for default dates
        fiscal_year = FiscalYear.objects.filter(
            organization=organization,
            is_active=True
        ).first()
        
        if fiscal_year:
            context['default_date_from'] = fiscal_year.start_date
            context['default_date_to'] = fiscal_year.end_date
        
        # If budget head selected, fetch entries
        if budget_head_id and date_from and date_to:
            try:
                budget_head = BudgetHead.objects.select_related(
                    'global_head', 'fund', 'function'
                ).get(pk=budget_head_id)
                context['selected_budget_head'] = budget_head
                context['filter_date_from'] = date_from
                context['filter_date_to'] = date_to
                
                date_from_obj = datetime.strptime(date_from, '%Y-%m-%d').date()
                date_to_obj = datetime.strptime(date_to, '%Y-%m-%d').date()
                
                # Calculate opening balance (before date_from)
                opening_entries = JournalEntry.objects.filter(
                    budget_head=budget_head,
                    voucher__is_posted=True,
                    voucher__organization=organization,
                    voucher__date__lt=date_from_obj
                ).aggregate(
                    total_debit=Coalesce(Sum('debit'), Decimal('0.00')),
                    total_credit=Coalesce(Sum('credit'), Decimal('0.00'))
                )
                
                # Cache account type
                account_type = budget_head.global_head.account_type
                is_debit_account = account_type in ['AST', 'EXP']
                
                if is_debit_account:
                    opening_balance = opening_entries['total_debit'] - opening_entries['total_credit']
                else:
                    opening_balance = opening_entries['total_credit'] - opening_entries['total_debit']
                
                context['opening_balance'] = opening_balance
                
                # Get entries in period with optimized query
                entries = JournalEntry.objects.filter(
                    budget_head=budget_head,
                    voucher__is_posted=True,
                    voucher__organization=organization,
                    voucher__date__gte=date_from_obj,
                    voucher__date__lte=date_to_obj
                ).select_related('voucher', 'budget_head').order_by('voucher__date', 'voucher__id')
                
                # Calculate running balance
                entries_with_balance = []
                running_balance = opening_balance
                
                for entry in entries:
                    # Use cached account type check
                    if is_debit_account:
                        running_balance += (entry.debit - entry.credit)
                    else:
                        running_balance += (entry.credit - entry.debit)
                    
                    entries_with_balance.append({
                        'entry': entry,
                        'balance': running_balance
                    })
                
                context['entries'] = entries_with_balance
                context['closing_balance'] = running_balance
                
            except BudgetHead.DoesNotExist:
                context['error'] = 'Selected budget head not found.'
        
        context['filter_budget_head'] = budget_head_id
        
        return context


class PendingLiabilitiesView(LoginRequiredMixin, TenantAwareMixin, TemplateView):
    """
    Pending Liabilities Report.
    
    Shows unpaid liabilities (Taxes, Retention Money, etc.) that require payment.
    Filters for Liability accounts with positive Credit balance.
    """
    template_name = 'reporting/pending_liabilities.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        organization = self.request.user.organization
        
        # Get as-of date (default today)
        context['as_of_date'] = date.today()
        
        # Get Liability Heads with balances
        liabilities = BudgetHead.objects.filter(
            is_active=True,
            global_head__account_type='LIA'  # Filter for Liabilities
        ).select_related('global_head', 'fund', 'function').annotate(
            total_debit=Coalesce(
                Sum('journal_entries__debit',
                    filter=Q(journal_entries__voucher__is_posted=True,
                            journal_entries__voucher__organization=organization)),
                Decimal('0.00')
            ),
            total_credit=Coalesce(
                Sum('journal_entries__credit',
                    filter=Q(journal_entries__voucher__is_posted=True,
                            journal_entries__voucher__organization=organization)),
                Decimal('0.00')
            )
        )
        
        # Calculate Pending Balances
        # Liability Balance = Credit (Owed) - Debit (Paid)
        pending_items = []
        total_pending = Decimal('0.00')
        
        for head in liabilities:
            balance = head.total_credit - head.total_debit
            if balance > Decimal('0.00'):
                pending_items.append({
                    'head': head,
                    'balance': balance,
                })
                total_pending += balance
        
        context['pending_items'] = pending_items
        context['total_pending'] = total_pending
        
        return context
