"""
-------------------------------------------------------------------------
System: KP-CFMS (Computerized Financial Management System)
Client: Local Government Department, Khyber Pakhtunkhwa
Team Lead: Jamil Shah
Developers: Ali Asghar, Akhtar Munir and Zarif Khan
Description: Unit tests for the budgeting module.
-------------------------------------------------------------------------
"""
from decimal import Decimal
from datetime import date
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model

from apps.budgeting.models import (
    FiscalYear, BudgetAllocation, ScheduleOfEstablishment,
    QuarterlyRelease, SAERecord, BudgetStatus, ReleaseQuarter
)
from apps.budgeting.services import (
    validate_receipt_growth, validate_reserve_requirement,
    validate_zero_deficit, finalize_budget, check_budget_availability
)
from apps.finance.models import BudgetHead, FunctionCode, AccountType
from apps.core.exceptions import ReserveViolationException, BudgetExceededException


User = get_user_model()


class ServiceFunctionTests(TestCase):
    """Tests for budgeting service functions."""
    
    def test_validate_receipt_growth_within_limit(self) -> None:
        """Test that receipt growth within 15% passes validation."""
        previous = Decimal('1000000.00')
        next_est = Decimal('1100000.00')  # 10% growth
        
        is_valid, error = validate_receipt_growth(previous, next_est)
        
        self.assertTrue(is_valid)
        self.assertIsNone(error)
    
    def test_validate_receipt_growth_at_limit(self) -> None:
        """Test that receipt growth at exactly 15% passes validation."""
        previous = Decimal('1000000.00')
        next_est = Decimal('1150000.00')  # Exactly 15%
        
        is_valid, error = validate_receipt_growth(previous, next_est)
        
        self.assertTrue(is_valid)
        self.assertIsNone(error)
    
    def test_validate_receipt_growth_exceeds_limit(self) -> None:
        """Test that receipt growth exceeding 15% fails validation."""
        previous = Decimal('1000000.00')
        next_est = Decimal('1200000.00')  # 20% growth
        
        is_valid, error = validate_receipt_growth(previous, next_est)
        
        self.assertFalse(is_valid)
        self.assertIsNotNone(error)
        self.assertIn('15%', error)
    
    def test_validate_receipt_growth_zero_previous(self) -> None:
        """Test that zero previous year allows any estimate."""
        previous = Decimal('0.00')
        next_est = Decimal('1000000.00')
        
        is_valid, error = validate_receipt_growth(previous, next_est)
        
        self.assertTrue(is_valid)
        self.assertIsNone(error)
    
    def test_validate_reserve_requirement_pass(self) -> None:
        """Test that 2% reserve requirement passes when met."""
        total_receipts = Decimal('10000000.00')
        contingency = Decimal('250000.00')  # 2.5%
        
        is_valid, error = validate_reserve_requirement(total_receipts, contingency)
        
        self.assertTrue(is_valid)
        self.assertIsNone(error)
    
    def test_validate_reserve_requirement_fail(self) -> None:
        """Test that 2% reserve requirement fails when not met."""
        total_receipts = Decimal('10000000.00')
        contingency = Decimal('100000.00')  # Only 1%
        
        is_valid, error = validate_reserve_requirement(total_receipts, contingency)
        
        self.assertFalse(is_valid)
        self.assertIsNotNone(error)
        self.assertIn('2%', error)
    
    def test_validate_zero_deficit_pass(self) -> None:
        """Test that balanced budget passes zero deficit check."""
        receipts = Decimal('10000000.00')
        expenditure = Decimal('9500000.00')  # Surplus
        
        is_valid, error = validate_zero_deficit(receipts, expenditure)
        
        self.assertTrue(is_valid)
        self.assertIsNone(error)
    
    def test_validate_zero_deficit_fail(self) -> None:
        """Test that deficit budget fails zero deficit check."""
        receipts = Decimal('9000000.00')
        expenditure = Decimal('10000000.00')  # Deficit
        
        is_valid, error = validate_zero_deficit(receipts, expenditure)
        
        self.assertFalse(is_valid)
        self.assertIsNotNone(error)
        self.assertIn('deficit', error.lower())


class FiscalYearModelTests(TestCase):
    """Tests for FiscalYear model."""
    
    def setUp(self) -> None:
        """Set up test data."""
        self.user = User.objects.create_user(
            cnic='12345-1234567-1',
            email='test@example.com',
            password='testpass123',
            first_name='Test',
            role='ADM'
        )
    
    def test_fiscal_year_creation(self) -> None:
        """Test creating a fiscal year."""
        fy = FiscalYear.objects.create(
            year_name='2026-27',
            start_date=date(2026, 7, 1),
            end_date=date(2027, 6, 30),
            created_by=self.user,
            updated_by=self.user
        )
        
        self.assertEqual(str(fy), 'FY 2026-27')
        self.assertFalse(fy.is_active)
        self.assertFalse(fy.is_locked)
        self.assertEqual(fy.status, BudgetStatus.DRAFT)
    
    def test_can_edit_budget(self) -> None:
        """Test can_edit_budget method."""
        fy = FiscalYear.objects.create(
            year_name='2026-27',
            start_date=date(2026, 7, 1),
            end_date=date(2027, 6, 30),
            is_active=True,
            created_by=self.user,
            updated_by=self.user
        )
        
        self.assertTrue(fy.can_edit_budget())
        
        fy.is_locked = True
        fy.save()
        
        self.assertFalse(fy.can_edit_budget())
    
    def test_lock_budget(self) -> None:
        """Test locking a fiscal year budget."""
        fy = FiscalYear.objects.create(
            year_name='2026-27',
            start_date=date(2026, 7, 1),
            end_date=date(2027, 6, 30),
            is_active=True,
            created_by=self.user,
            updated_by=self.user
        )
        
        fy.lock_budget('SAE-2026-0001')
        
        self.assertTrue(fy.is_locked)
        self.assertFalse(fy.is_active)
        self.assertEqual(fy.sae_number, 'SAE-2026-0001')
        self.assertEqual(fy.status, BudgetStatus.LOCKED)


class BudgetAllocationModelTests(TestCase):
    """Tests for BudgetAllocation model."""
    
    def setUp(self) -> None:
        """Set up test data."""
        self.user = User.objects.create_user(
            cnic='12345-1234567-1',
            email='test@example.com',
            password='testpass123',
            first_name='Test',
            role='ADM'
        )
        
        self.function = FunctionCode.objects.create(
            code='AD',
            name='Administration'
        )
        
        self.budget_head = BudgetHead.objects.create(
            fund_id=1,
            function=self.function,
            pifra_object='A01101',
            pifra_description='Basic Pay of Officers',
            tma_sub_object='A01101-001',
            tma_description='TMO Salary',
            account_type=AccountType.EXPENDITURE,
            created_by=self.user,
            updated_by=self.user
        )
        
        self.fiscal_year = FiscalYear.objects.create(
            year_name='2026-27',
            start_date=date(2026, 7, 1),
            end_date=date(2027, 6, 30),
            is_active=True,
            created_by=self.user,
            updated_by=self.user
        )
    
    def test_get_available_budget(self) -> None:
        """Test calculating available budget."""
        allocation = BudgetAllocation.objects.create(
            fiscal_year=self.fiscal_year,
            budget_head=self.budget_head,
            original_allocation=Decimal('1000000.00'),
            released_amount=Decimal('250000.00'),
            spent_amount=Decimal('100000.00'),
            created_by=self.user,
            updated_by=self.user
        )
        
        available = allocation.get_available_budget()
        
        self.assertEqual(available, Decimal('150000.00'))
    
    def test_can_spend(self) -> None:
        """Test budget spending validation."""
        allocation = BudgetAllocation.objects.create(
            fiscal_year=self.fiscal_year,
            budget_head=self.budget_head,
            original_allocation=Decimal('1000000.00'),
            released_amount=Decimal('250000.00'),
            spent_amount=Decimal('100000.00'),
            created_by=self.user,
            updated_by=self.user
        )
        
        self.assertTrue(allocation.can_spend(Decimal('100000.00')))
        self.assertFalse(allocation.can_spend(Decimal('200000.00')))


class QuarterlyReleaseTests(TestCase):
    """Tests for quarterly release functionality."""
    
    def test_get_quarter_for_date(self) -> None:
        """Test quarter detection for dates."""
        self.assertEqual(
            QuarterlyRelease.get_quarter_for_date(date(2026, 7, 15)),
            ReleaseQuarter.Q1
        )
        self.assertEqual(
            QuarterlyRelease.get_quarter_for_date(date(2026, 11, 1)),
            ReleaseQuarter.Q2
        )
        self.assertEqual(
            QuarterlyRelease.get_quarter_for_date(date(2027, 2, 15)),
            ReleaseQuarter.Q3
        )
        self.assertEqual(
            QuarterlyRelease.get_quarter_for_date(date(2027, 5, 1)),
            ReleaseQuarter.Q4
        )
