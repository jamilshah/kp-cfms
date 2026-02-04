"""
-------------------------------------------------------------------------
System: KP-CFMS (Computerized Financial Management System)
Client: Local Government Department, Khyber Pakhtunkhwa
Team Lead: Jamil Shah
Developers: Ali Asghar, Akhtar Munir and Zarif Khan
Description: Dashboard service layer for aggregating financial metrics.
             Implements caching-friendly methods for KPI calculations.
-------------------------------------------------------------------------
"""
from decimal import Decimal
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from django.db.models import Sum, Q, Count, F
from django.utils import timezone

from apps.budgeting.models import BudgetAllocation, FiscalYear
from apps.revenue.models import RevenueDemand, RevenueCollection, DemandStatus, CollectionStatus
from apps.expenditure.models import Bill
from apps.core.models import BankAccount, Organization
from apps.finance.models import JournalEntry, AccountType, BudgetHead


class DashboardService:
    """
    Service class for dashboard data aggregation.
    
    Provides methods to calculate KPIs and generate chart data
    for the Executive Dashboard.
    """
    
    @staticmethod
    def get_budget_summary(
        fiscal_year: FiscalYear,
        organization: Optional[Organization] = None
    ) -> Dict[str, Any]:
        """
        Get budget summary with salary vs non-salary breakdown.
        
        Args:
            fiscal_year: The fiscal year to analyze.
            organization: The organization to filter by (None for provincial summary).
            
        Returns:
            Dictionary containing:
                - total_budget: Total revised allocation
                - total_utilization: Total spent amount
                - utilization_percent: Percentage utilized
                - salary_budget: Budget for salary heads (A01*)
                - salary_spent: Spent on salary heads
                - nonsalary_budget: Budget for non-salary heads
                - nonsalary_spent: Spent on non-salary heads
        """
        # Base queryset
        allocations = BudgetAllocation.objects.filter(fiscal_year=fiscal_year)
        
        if organization:
            allocations = allocations.filter(organization=organization)
        
        # Total aggregates
        totals = allocations.aggregate(
            total_budget=Sum('revised_allocation'),
            total_utilization=Sum('spent_amount')
        )
        
        # Salary heads (A01*)
        salary_allocations = allocations.filter(
            budget_head__global_head__code__startswith='A01'
        ).aggregate(
            salary_budget=Sum('revised_allocation'),
            salary_spent=Sum('spent_amount')
        )
        
        # Non-salary heads (everything else)
        nonsalary_allocations = allocations.exclude(
            budget_head__global_head__code__startswith='A01'
        ).aggregate(
            nonsalary_budget=Sum('revised_allocation'),
            nonsalary_spent=Sum('spent_amount')
        )
        
        total_budget = totals['total_budget'] or Decimal('0.00')
        total_utilization = totals['total_utilization'] or Decimal('0.00')
        
        utilization_percent = Decimal('0.00')
        if total_budget > Decimal('0.00'):
            utilization_percent = (total_utilization / total_budget * 100).quantize(Decimal('0.01'))
        
        return {
            'total_budget': total_budget,
            'total_utilization': total_utilization,
            'utilization_percent': utilization_percent,
            'salary_budget': salary_allocations['salary_budget'] or Decimal('0.00'),
            'salary_spent': salary_allocations['salary_spent'] or Decimal('0.00'),
            'nonsalary_budget': nonsalary_allocations['nonsalary_budget'] or Decimal('0.00'),
            'nonsalary_spent': nonsalary_allocations['nonsalary_spent'] or Decimal('0.00'),
        }
    
    @staticmethod
    def get_revenue_summary(
        fiscal_year: FiscalYear,
        organization: Optional[Organization] = None
    ) -> Dict[str, Any]:
        """
        Get revenue summary with demand vs collection analysis.
        
        Args:
            fiscal_year: The fiscal year to analyze.
            organization: The organization to filter by (None for provincial summary).
            
        Returns:
            Dictionary containing:
                - total_demand: Total revenue demand amount
                - total_collection: Total revenue collected
                - recovery_percent: Collection/Demand percentage
                - monthly_trend: List of monthly collection data for last 6 months
        """
        # Base querysets
        demands = RevenueDemand.objects.filter(
            fiscal_year=fiscal_year,
            status__in=[DemandStatus.POSTED, DemandStatus.PARTIAL, DemandStatus.PAID]
        )
        collections = RevenueCollection.objects.filter(
            demand__fiscal_year=fiscal_year,
            status=CollectionStatus.POSTED
        )
        
        if organization:
            demands = demands.filter(organization=organization)
            collections = collections.filter(organization=organization)
        
        # Aggregates
        demand_total = demands.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        collection_total = collections.aggregate(total=Sum('amount_received'))['total'] or Decimal('0.00')
        
        recovery_percent = Decimal('0.00')
        if demand_total > Decimal('0.00'):
            recovery_percent = (collection_total / demand_total * 100).quantize(Decimal('0.01'))
        
        # Monthly trend for last 6 months
        from django.db.models.functions import TruncMonth
        
        six_months_ago = timezone.now() - timedelta(days=180)
        monthly_collections = collections.filter(
            receipt_date__gte=six_months_ago
        ).annotate(
            month=TruncMonth('receipt_date')
        ).values('month').annotate(
            amount=Sum('amount_received')
        ).order_by('month')
        
        monthly_trend = [
            {
                'month': item['month'].strftime('%Y-%m') if item['month'] else '',
                'amount': float(item['amount'])
            }
            for item in monthly_collections
        ]
        
        return {
            'total_demand': demand_total,
            'total_collection': collection_total,
            'recovery_percent': recovery_percent,
            'monthly_trend': monthly_trend,
        }
    
    @staticmethod
    def get_cash_position(organization: Optional[Organization] = None) -> Dict[str, Any]:
        """
        Calculate current cash position across all bank accounts.
        
        Args:
            organization: The organization to filter by (None for provincial summary).
            
        Returns:
            Dictionary containing:
                - total_cash: Total cash across all bank accounts
                - accounts: List of individual account balances
        """
        # Get bank accounts
        accounts_qs = BankAccount.objects.filter(is_active=True)
        
        if organization:
            accounts_qs = accounts_qs.filter(organization=organization)
        
        accounts_data = []
        total_cash = Decimal('0.00')
        
        for account in accounts_qs:
            # Calculate current balance from GL
            # Calculate current balance using model method (safe & filtered)
            current_balance = account.get_balance()
            
            accounts_data.append({
                'title': account.title,
                'bank_name': account.bank_name,
                'account_number': account.masked_account_number,
                'balance': current_balance,
            })
            
            total_cash += current_balance
        
        return {
            'total_cash': total_cash,
            'accounts': accounts_data,
        }
    
    @staticmethod
    def get_pending_liabilities(organization: Optional[Organization] = None) -> Dict[str, Any]:
        """
        Get count and amount of pending liabilities (approved but unpaid bills).
        
        Args:
            organization: The organization to filter by (None for provincial summary).
            
        Returns:
            Dictionary containing:
                - count: Number of approved but unpaid bills
                - total_amount: Total amount of pending liabilities
        """
        bills = Bill.objects.filter(status='APPROVED')
        
        if organization:
            bills = bills.filter(organization=organization)
        
        aggregates = bills.aggregate(
            count=Count('id'),
            total_amount=Sum('net_amount')
        )
        
        return {
            'count': aggregates['count'] or 0,
            'total_amount': aggregates['total_amount'] or Decimal('0.00'),
        }
    
    @staticmethod
    def get_top_expenditure_heads(
        fiscal_year: FiscalYear,
        organization: Optional[Organization] = None,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Get top expenditure heads by spending.
        
        Args:
            fiscal_year: The fiscal year to analyze.
            organization: The organization to filter by.
            limit: Number of top heads to return.
            
        Returns:
            List of dictionaries with head name and amount spent.
        """
        # Get expenditure journal entries
        entries = JournalEntry.objects.filter(
            voucher__fiscal_year=fiscal_year,
            voucher__is_posted=True,
            budget_head__global_head__account_type=AccountType.EXPENDITURE,
            debit__gt=0  # Expenditure is debited
        )
        
        if organization:
            entries = entries.filter(voucher__organization=organization)
        
        # Group by budget head and sum debits
        top_heads = entries.values(
            'budget_head__global_head__name',
            'budget_head__global_head__code'
        ).annotate(
            total_spent=Sum('debit')
        ).order_by('-total_spent')[:limit]
        
        return [
            {
                'head': item['budget_head__global_head__name'],
                'code': item['budget_head__global_head__code'],
                'amount': float(item['total_spent'])
            }
            for item in top_heads
        ]
    
    @staticmethod
    def get_budget_alerts(
        fiscal_year: FiscalYear,
        organization: Optional[Organization] = None,
        threshold: Decimal = Decimal('90.00')
    ) -> List[Dict[str, Any]]:
        """
        Get budget heads near exhaustion (>90% utilized).
        
        Args:
            fiscal_year: The fiscal year to analyze.
            organization: The organization to filter by.
            threshold: Utilization percentage threshold (default 90%).
            
        Returns:
            List of budget heads with high utilization.
        """
        allocations = BudgetAllocation.objects.filter(
            fiscal_year=fiscal_year,
            revised_allocation__gt=0
        ).annotate(
            utilization_pct=F('spent_amount') * 100 / F('revised_allocation')
        ).filter(
            utilization_pct__gte=threshold
        )
        
        if organization:
            allocations = allocations.filter(organization=organization)
        
        return [
            {
                'head': alloc.budget_head.name,
                'code': alloc.budget_head.code,
                'budget': alloc.revised_allocation,
                'spent': alloc.spent_amount,
                'utilization_pct': float(alloc.spent_amount / alloc.revised_allocation * 100),
            }
            for alloc in allocations.select_related('budget_head')[:10]
        ]
