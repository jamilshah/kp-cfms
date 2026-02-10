"""
-------------------------------------------------------------------------
System: KP-CFMS (Computerized Financial Management System)
Client: Local Government Department, Khyber Pakhtunkhwa
Team Lead: Jamil Shah
Developers: Ali Asghar, Akhtar Munir and Zarif Khan
Description: Provincial analytics service for LCB Dashboard.
             Aggregates data across all TMAs for macro-level insights.
-------------------------------------------------------------------------
"""
from decimal import Decimal
from typing import Dict, List, Optional, Any
from django.db.models import Sum, Q, Count, F, Case, When, DecimalField
from django.db.models.functions import Coalesce

from apps.budgeting.models import BudgetAllocation, FiscalYear
from apps.revenue.models import RevenueDemand, RevenueCollection, DemandStatus, CollectionStatus
from apps.expenditure.models import Bill
from apps.core.models import BankAccount, Organization, Division, District
from apps.finance.models import JournalEntry, AccountType, BudgetHead


class ProvincialAnalyticsService:
    """
    Service class for provincial-level dashboard analytics.
    
    Aggregates data across all TMAs to provide macro-level insights
    for LCB Officers and Provincial Administrators.
    """
    
    @staticmethod
    def get_provincial_totals(
        fiscal_year: FiscalYear,
        division: Optional[Division] = None,
        district: Optional[District] = None
    ) -> Dict[str, Any]:
        """
        Get province-wide financial totals.
        
        Args:
            fiscal_year: The fiscal year to analyze.
            division: Optional division filter.
            district: Optional district filter.
            
        Returns:
            Dictionary containing:
                - total_budget: Sum of revised allocations across all TMAs
                - total_utilization: Sum of spent amounts across all TMAs
                - utilization_percent: Overall utilization percentage
                - total_demand: Sum of revenue demands
                - total_collection: Sum of revenue collections
                - recovery_percent: Overall recovery percentage
                - total_cash: Sum of all bank account balances
                - total_liabilities: Sum of pending bills
        """
        # Build organization filter
        orgs = Organization.objects.filter(is_active=True, org_type__in=['TMA', 'TOWN'])
        
        if district:
            orgs = orgs.filter(tehsil__district=district)
        elif division:
            orgs = orgs.filter(tehsil__district__division=division)
        
        org_ids = list(orgs.values_list('id', flat=True))
        
        # Budget totals
        budget_totals = BudgetAllocation.objects.filter(
            fiscal_year=fiscal_year,
            organization_id__in=org_ids
        ).aggregate(
            total_budget=Sum('revised_allocation'),
            total_utilization=Sum('spent_amount')
        )
        
        total_budget = budget_totals['total_budget'] or Decimal('0.00')
        total_utilization = budget_totals['total_utilization'] or Decimal('0.00')
        
        utilization_percent = Decimal('0.00')
        if total_budget > Decimal('0.00'):
            utilization_percent = (total_utilization / total_budget * 100).quantize(Decimal('0.01'))
        
        # Revenue totals
        demand_total = RevenueDemand.objects.filter(
            fiscal_year=fiscal_year,
            organization_id__in=org_ids,
            status__in=[DemandStatus.POSTED, DemandStatus.PARTIAL, DemandStatus.PAID]
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        collection_total = RevenueCollection.objects.filter(
            demand__fiscal_year=fiscal_year,
            demand__organization_id__in=org_ids,
            status=CollectionStatus.POSTED
        ).aggregate(total=Sum('amount_received'))['total'] or Decimal('0.00')
        
        recovery_percent = Decimal('0.00')
        if demand_total > Decimal('0.00'):
            recovery_percent = (collection_total / demand_total * 100).quantize(Decimal('0.01'))
        
        # Cash position (sum of all bank balances)
        accounts = BankAccount.objects.filter(
            is_active=True,
            organization_id__in=org_ids
        )
        
        total_cash = Decimal('0.00')
        for account in accounts:
            gl_entries = JournalEntry.objects.filter(
                budget_head=account.gl_code,
                voucher__is_posted=True,
                voucher__organization_id__in=org_ids
            ).aggregate(
                total_debit=Sum('debit'),
                total_credit=Sum('credit')
            )
            
            debit_total = gl_entries['total_debit'] or Decimal('0.00')
            credit_total = gl_entries['total_credit'] or Decimal('0.00')
            total_cash += (debit_total - credit_total)
        
        # Pending liabilities
        liabilities = Bill.objects.filter(
            status='APPROVED',
            organization_id__in=org_ids
        ).aggregate(
            count=Count('id'),
            total_amount=Sum('net_amount')
        )
        
        return {
            'total_budget': total_budget,
            'total_utilization': total_utilization,
            'utilization_percent': utilization_percent,
            'total_demand': demand_total,
            'total_collection': collection_total,
            'recovery_percent': recovery_percent,
            'total_cash': total_cash,
            'total_liabilities': liabilities['total_amount'] or Decimal('0.00'),
            'liabilities_count': liabilities['count'] or 0,
            'tma_count': len(org_ids),
        }
    
    @staticmethod
    def get_tma_performance_ranking(
        fiscal_year: FiscalYear,
        division: Optional[Division] = None,
        district: Optional[District] = None
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Rank TMAs by revenue recovery performance.
        
        Args:
            fiscal_year: The fiscal year to analyze.
            division: Optional division filter.
            district: Optional district filter.
            
        Returns:
            Dictionary with 'top_performers' and 'laggards' lists.
        """
        # Build organization filter
        orgs = Organization.objects.filter(is_active=True, org_type__in=['TMA', 'TOWN'])
        
        if district:
            orgs = orgs.filter(tehsil__district=district)
        elif division:
            orgs = orgs.filter(tehsil__district__division=division)
        
        # Aggregate revenue data per TMA
        tma_performance = []
        
        for org in orgs:
            demand_total = RevenueDemand.objects.filter(
                fiscal_year=fiscal_year,
                organization=org,
                status__in=[DemandStatus.POSTED, DemandStatus.PARTIAL, DemandStatus.PAID]
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            
            collection_total = RevenueCollection.objects.filter(
                demand__fiscal_year=fiscal_year,
                demand__organization=org,
                status=CollectionStatus.POSTED
            ).aggregate(total=Sum('amount_received'))['total'] or Decimal('0.00')
            
            recovery_percent = Decimal('0.00')
            if demand_total > Decimal('0.00'):
                recovery_percent = (collection_total / demand_total * 100).quantize(Decimal('0.01'))
            
            tma_performance.append({
                'name': org.name,
                'demand': demand_total,
                'collection': collection_total,
                'recovery_percent': float(recovery_percent),
            })
        
        # Sort by recovery percentage
        tma_performance.sort(key=lambda x: x['recovery_percent'], reverse=True)
        
        return {
            'top_performers': tma_performance[:5],
            'laggards': tma_performance[-5:] if len(tma_performance) > 5 else [],
        }
    
    @staticmethod
    def get_expense_composition(
        fiscal_year: FiscalYear,
        division: Optional[Division] = None,
        district: Optional[District] = None
    ) -> List[Dict[str, Any]]:
        """
        Get province-wide expense composition by major object code.
        
        Args:
            fiscal_year: The fiscal year to analyze.
            division: Optional division filter.
            district: Optional district filter.
            
        Returns:
            List of expense categories with amounts for pie chart.
        """
        # Build organization filter
        orgs = Organization.objects.filter(is_active=True, org_type__in=['TMA', 'TOWN'])
        
        if district:
            orgs = orgs.filter(tehsil__district=district)
        elif division:
            orgs = orgs.filter(tehsil__district__division=division)
        
        org_ids = list(orgs.values_list('id', flat=True))
        
        # Aggregate by major object code
        entries = JournalEntry.objects.filter(
            voucher__fiscal_year=fiscal_year,
            voucher__is_posted=True,
            voucher__organization_id__in=org_ids,
            debit__gt=0
        ).filter(
            Q(budget_head__nam_head__isnull=False, budget_head__nam_head__account_type=AccountType.EXPENDITURE) |
            Q(budget_head__sub_head__isnull=False, budget_head__sub_head__nam_head__account_type=AccountType.EXPENDITURE)
        )
        
        # Employee Related (A01)
        employee_total = entries.filter(
            Q(budget_head__nam_head__isnull=False, budget_head__nam_head__code__startswith='A01') |
            Q(budget_head__sub_head__isnull=False, budget_head__sub_head__nam_head__code__startswith='A01')
        ).aggregate(total=Sum('debit'))['total'] or Decimal('0.00')
        
        # Operating Expenses (A03)
        operating_total = entries.filter(
            Q(budget_head__nam_head__isnull=False, budget_head__nam_head__code__startswith='A03') |
            Q(budget_head__sub_head__isnull=False, budget_head__sub_head__nam_head__code__startswith='A03')
        ).aggregate(total=Sum('debit'))['total'] or Decimal('0.00')
        
        # Assets/Development (A09, A12)
        development_total = entries.filter(
            Q(budget_head__nam_head__isnull=False, budget_head__nam_head__code__startswith='A09') |
            Q(budget_head__nam_head__isnull=False, budget_head__nam_head__code__startswith='A12') |
            Q(budget_head__sub_head__isnull=False, budget_head__sub_head__nam_head__code__startswith='A09') |
            Q(budget_head__sub_head__isnull=False, budget_head__sub_head__nam_head__code__startswith='A12')
        ).aggregate(total=Sum('debit'))['total'] or Decimal('0.00')
        
        # Other (everything else)
        other_total = entries.exclude(
            Q(budget_head__nam_head__isnull=False, budget_head__nam_head__code__startswith='A01') |
            Q(budget_head__nam_head__isnull=False, budget_head__nam_head__code__startswith='A03') |
            Q(budget_head__nam_head__isnull=False, budget_head__nam_head__code__startswith='A09') |
            Q(budget_head__nam_head__isnull=False, budget_head__nam_head__code__startswith='A12') |
            Q(budget_head__sub_head__isnull=False, budget_head__sub_head__nam_head__code__startswith='A01') |
            Q(budget_head__sub_head__isnull=False, budget_head__sub_head__nam_head__code__startswith='A03') |
            Q(budget_head__sub_head__isnull=False, budget_head__sub_head__nam_head__code__startswith='A09') |
            Q(budget_head__sub_head__isnull=False, budget_head__sub_head__nam_head__code__startswith='A12')
        ).aggregate(total=Sum('debit'))['total'] or Decimal('0.00')
        
        return [
            {
                'category': 'Employee Related (A01)',
                'amount': float(employee_total),
                'color': '#1a5276'
            },
            {
                'category': 'Operating Expenses (A03)',
                'amount': float(operating_total),
                'color': '#2e86ab'
            },
            {
                'category': 'Assets/Development (A09/A12)',
                'amount': float(development_total),
                'color': '#28a745'
            },
            {
                'category': 'Other Expenses',
                'amount': float(other_total),
                'color': '#6c757d'
            },
        ]
    
    @staticmethod
    def get_deficit_tmas(
        fiscal_year: FiscalYear,
        division: Optional[Division] = None,
        district: Optional[District] = None
    ) -> List[Dict[str, Any]]:
        """
        Identify TMAs where expenditure exceeds revenue.
        
        Args:
            fiscal_year: The fiscal year to analyze.
            division: Optional division filter.
            district: Optional district filter.
            
        Returns:
            List of TMAs in deficit with amounts.
        """
        # Build organization filter
        orgs = Organization.objects.filter(is_active=True, org_type__in=['TMA', 'TOWN'])
        
        if district:
            orgs = orgs.filter(tehsil__district=district)
        elif division:
            orgs = orgs.filter(tehsil__district__division=division)
        
        deficit_tmas = []
        
        for org in orgs:
            # Total expenditure
            expenditure = JournalEntry.objects.filter(
                voucher__fiscal_year=fiscal_year,
                voucher__is_posted=True,
                voucher__organization=org,
                budget_head__global_head__account_type=AccountType.EXPENDITURE,
                debit__gt=0
            ).aggregate(total=Sum('debit'))['total'] or Decimal('0.00')
            
            # Total revenue
            revenue = RevenueCollection.objects.filter(
                demand__fiscal_year=fiscal_year,
                demand__organization=org,
                status=CollectionStatus.POSTED
            ).aggregate(total=Sum('amount_received'))['total'] or Decimal('0.00')
            
            deficit = expenditure - revenue
            
            if deficit > Decimal('0.00'):
                deficit_tmas.append({
                    'name': org.name,
                    'expenditure': expenditure,
                    'revenue': revenue,
                    'deficit': deficit,
                })
        
        # Sort by deficit amount (highest first)
        deficit_tmas.sort(key=lambda x: x['deficit'], reverse=True)
        
        return deficit_tmas[:10]  # Top 10 deficits
    
    @staticmethod
    def get_low_utilization_tmas(
        fiscal_year: FiscalYear,
        threshold: Decimal = Decimal('10.00'),
        division: Optional[Division] = None,
        district: Optional[District] = None
    ) -> List[Dict[str, Any]]:
        """
        Identify TMAs with low budget utilization (<10%).
        
        Args:
            fiscal_year: The fiscal year to analyze.
            threshold: Utilization percentage threshold (default 10%).
            division: Optional division filter.
            district: Optional district filter.
            
        Returns:
            List of TMAs with low utilization.
        """
        # Build organization filter
        orgs = Organization.objects.filter(is_active=True, org_type__in=['TMA', 'TOWN'])
        
        if district:
            orgs = orgs.filter(tehsil__district=district)
        elif division:
            orgs = orgs.filter(tehsil__district__division=division)
        
        low_utilization_tmas = []
        
        for org in orgs:
            totals = BudgetAllocation.objects.filter(
                fiscal_year=fiscal_year,
                organization=org
            ).aggregate(
                total_budget=Sum('revised_allocation'),
                total_spent=Sum('spent_amount')
            )
            
            total_budget = totals['total_budget'] or Decimal('0.00')
            total_spent = totals['total_spent'] or Decimal('0.00')
            
            if total_budget > Decimal('0.00'):
                utilization_pct = (total_spent / total_budget * 100).quantize(Decimal('0.01'))
                
                if utilization_pct < threshold:
                    low_utilization_tmas.append({
                        'name': org.name,
                        'budget': total_budget,
                        'spent': total_spent,
                        'utilization_pct': float(utilization_pct),
                    })
        
        # Sort by utilization percentage (lowest first)
        low_utilization_tmas.sort(key=lambda x: x['utilization_pct'])
        
        return low_utilization_tmas[:10]  # Top 10 slow movers
