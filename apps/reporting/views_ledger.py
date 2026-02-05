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
    General Ledger Report.
    
    Shows all journal entries:
    - For a selected budget head with running balance, OR
    - For all accounts (when no head selected) without running balance
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
        fiscal_year = FiscalYear.get_current_operating_year()
        
        if fiscal_year:
            context['default_date_from'] = fiscal_year.start_date
            context['default_date_to'] = fiscal_year.end_date
        
        # If budget head selected, fetch entries with running balance
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
                context['single_account'] = True
                
            except BudgetHead.DoesNotExist:
                context['error'] = 'Selected budget head not found.'
        
        else:
            # No budget head selected - show all transactions (multi-account view)
            entries_query = JournalEntry.objects.filter(
                voucher__is_posted=True,
                voucher__organization=organization
            ).select_related('voucher', 'budget_head', 'budget_head__global_head', 'budget_head__function')
            
            # Apply date filters
            if date_from:
                entries_query = entries_query.filter(voucher__date__gte=date_from)
                context['filter_date_from'] = date_from
            if date_to:
                entries_query = entries_query.filter(voucher__date__lte=date_to)
                context['filter_date_to'] = date_to
            
            # Order by date and voucher
            entries = entries_query.order_by('voucher__date', 'voucher__id')
            
            # For multi-account view, no running balance
            context['entries'] = [{'entry': entry} for entry in entries]
            context['single_account'] = False
            
            # Calculate totals
            total_debit = sum(entry.debit for entry in entries)
            total_credit = sum(entry.credit for entry in entries)
            context['total_debit'] = total_debit
            context['total_credit'] = total_credit
        
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
        fiscal_year = FiscalYear.get_current_operating_year()
        
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
    Includes approved bills (AP) and tax liability GL balances for the current fiscal year.
    """
    template_name = 'reporting/pending_liabilities.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        organization = self.request.user.organization
        
        # Get current operating fiscal year
        fiscal_year = FiscalYear.get_current_operating_year()
        
        if not fiscal_year:
            context['no_fiscal_year'] = True
            context['as_of_date'] = date.today()
            context['pending_items'] = []
            context['total_pending'] = Decimal('0.00')
            context['approved_bills_total'] = Decimal('0.00')
            context['tax_liability_total'] = Decimal('0.00')
            return context
        
        context['fiscal_year'] = fiscal_year
        context['as_of_date'] = date.today()
        
        # Import Bill model here to avoid circular imports
        from apps.expenditure.models import Bill
        from apps.finance.models import GlobalHead
        
        # 1. Calculate Approved Bills (AP) - not yet paid
        approved_bills = Bill.objects.filter(
            organization=organization,
            fiscal_year=fiscal_year,
            status='APPROVED'  # Bills approved but not paid
        ).aggregate(
            total=Coalesce(Sum('net_amount'), Decimal('0.00'))
        )
        approved_bills_total = approved_bills['total']
        
        # 2. Calculate Tax Liability GL Balances (withheld taxes not yet remitted)
        # Get tax liability heads using system_code
        from apps.finance.models import SystemCode
        
        tax_liability_heads = GlobalHead.objects.filter(
            system_code__in=[
                SystemCode.TAX_IT,      # Income Tax Payable
                SystemCode.TAX_GST,     # GST/Sales Tax Payable
                SystemCode.CLEARING_IT, # Income Tax Withheld (clearing)
                SystemCode.CLEARING_GST # GST Withheld (clearing)
            ]
        ).values_list('id', flat=True)
        
        # Get balances for tax liability heads scoped to org & fiscal year
        # BudgetHead doesn't have fiscal_year or organization directly,
        # so we filter via voucher fiscal_year and organization in the journal entry aggregation
        tax_liabilities = BudgetHead.objects.filter(
            global_head_id__in=tax_liability_heads,
            is_active=True
        ).select_related('global_head', 'fund', 'function').annotate(
            total_debit=Coalesce(
                Sum('journal_entries__debit',
                    filter=Q(journal_entries__voucher__is_posted=True,
                            journal_entries__voucher__organization=organization,
                            journal_entries__voucher__fiscal_year=fiscal_year)),
                Decimal('0.00')
            ),
            total_credit=Coalesce(
                Sum('journal_entries__credit',
                    filter=Q(journal_entries__voucher__is_posted=True,
                            journal_entries__voucher__organization=organization,
                            journal_entries__voucher__fiscal_year=fiscal_year)),
                Decimal('0.00')
            )
        )
        
        # Calculate Tax Liability Balances (Credit - Debit = amount owed)
        pending_items = []
        tax_liability_total = Decimal('0.00')
        
        for head in tax_liabilities:
            balance = head.total_credit - head.total_debit
            if balance > Decimal('0.00'):
                pending_items.append({
                    'head': head,
                    'balance': balance,
                })
                tax_liability_total += balance
        
        # Total pending liabilities
        total_pending = approved_bills_total + tax_liability_total
        
        context['pending_items'] = pending_items
        context['total_pending'] = total_pending
        context['approved_bills_total'] = approved_bills_total
        context['tax_liability_total'] = tax_liability_total
        
        return context
