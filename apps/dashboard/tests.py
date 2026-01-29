"""
-------------------------------------------------------------------------
System: KP-CFMS (Computerized Financial Management System)
Client: Local Government Department, Khyber Pakhtunkhwa
Team Lead: Jamil Shah
Developers: Ali Asghar, Akhtar Munir and Zarif Khan
Description: Unit tests for dashboard services.
-------------------------------------------------------------------------
"""
from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta

from apps.core.models import Organization, BankAccount
from apps.budgeting.models import FiscalYear, BudgetAllocation
from apps.finance.models import BudgetHead, Voucher, JournalEntry, AccountType
from apps.revenue.models import RevenueDemand, RevenueCollection
from apps.users.models import CustomUser
from apps.dashboard.services import DashboardService


class DashboardServiceTestCase(TestCase):
    """Test cases for DashboardService methods."""
    
    def setUp(self):
        """Set up test data."""
        # Create organization
        self.org = Organization.objects.create(
            name='Test TMA',
            org_type='TMA',
            is_active=True
        )
        
        # Create fiscal year
        self.fy = FiscalYear.objects.create(
            organization=self.org,
            year_name='2024-25',
            start_date=timezone.now().date() - timedelta(days=180),
            end_date=timezone.now().date() + timedelta(days=180),
            is_active=True
        )
        # Create fund
        from apps.finance.models import Fund
        self.fund = Fund.objects.create(
            name='Current Fund',
            code='GEN',
            description='Current Revenue & Expenditure'
        )
        
        # Create budget heads
        self.salary_head = BudgetHead.objects.create(
            fund=self.fund,
            pifra_object='A01101',
            pifra_description='Basic Pay',
            tma_sub_object='A01101',
            tma_description='Basic Pay',
            account_type=AccountType.EXPENDITURE
        )
        
        self.nonsalary_head = BudgetHead.objects.create(
            fund=self.fund,
            pifra_object='A02101',
            pifra_description='Office Supplies',
            tma_sub_object='A02101',
            tma_description='Office Supplies',
            account_type=AccountType.EXPENDITURE
        )
    
    def test_budget_summary_calculation(self):
        """Test budget summary with salary vs non-salary breakdown."""
        # Create allocations
        BudgetAllocation.objects.create(
            organization=self.org,
            fiscal_year=self.fy,
            budget_head=self.salary_head,
            original_allocation=Decimal('100000.00'),
            revised_allocation=Decimal('120000.00'),
            spent_amount=Decimal('80000.00')
        )
        
        BudgetAllocation.objects.create(
            organization=self.org,
            fiscal_year=self.fy,
            budget_head=self.nonsalary_head,
            original_allocation=Decimal('50000.00'),
            revised_allocation=Decimal('50000.00'),
            spent_amount=Decimal('30000.00')
        )
        
        # Get summary
        summary = DashboardService.get_budget_summary(self.fy, self.org)
        
        # Assertions
        self.assertEqual(summary['total_budget'], Decimal('170000.00'))
        self.assertEqual(summary['total_utilization'], Decimal('110000.00'))
        self.assertEqual(summary['salary_budget'], Decimal('120000.00'))
        self.assertEqual(summary['salary_spent'], Decimal('80000.00'))
        self.assertEqual(summary['nonsalary_budget'], Decimal('50000.00'))
        self.assertEqual(summary['nonsalary_spent'], Decimal('30000.00'))
        
        # Check utilization percentage
        expected_pct = Decimal('64.71')  # 110000/170000 * 100
        self.assertEqual(summary['utilization_percent'], expected_pct)
    
    def test_cash_position_empty(self):
        """Test cash position with no bank accounts."""
        position = DashboardService.get_cash_position(self.org)
        
        self.assertEqual(position['total_cash'], Decimal('0.00'))
        self.assertEqual(len(position['accounts']), 0)
