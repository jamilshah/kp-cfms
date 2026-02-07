"""
-------------------------------------------------------------------------
System: KP-CFMS (Computerized Financial Management System)
Client: Local Government Department, Khyber Pakhtunkhwa
Team Lead: Jamil Shah
Developers: Ali Asghar, Akhtar Munir and Zarif Khan
Description: Test cases for Revenue module models
-------------------------------------------------------------------------
"""
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import timedelta

from apps.revenue.models import (
    Payer, RevenueDemand, RevenueCollection,
    DemandStatus, CollectionStatus
)
from apps.budgeting.models import FiscalYear, Department
from apps.finance.models import BudgetHead, Fund, GlobalHead, AccountType, FunctionCode, MajorHead, MinorHead
from apps.core.models import Organization, BankAccount
from apps.core.exceptions import WorkflowTransitionException

User = get_user_model()


class PayerModelTest(TestCase):
    """Test cases for Payer model"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.org = Organization.objects.create(
            name="TMA Test"
        )
        self.user = User.objects.create_user(
            cnic='12345-1234567-1',
            email='testuser@example.com',
            password='testpass123',
            organization=self.org
        )
        
    def test_create_payer(self):
        """Test basic payer creation"""
        payer = Payer.objects.create(
            organization=self.org,
            name="John Doe",
            cnic_ntn="12345-1234567-1",
            contact_no="0300-1234567",
            created_by=self.user
        )
        self.assertEqual(str(payer), "John Doe")
        self.assertTrue(payer.is_active)
        self.assertEqual(payer.organization, self.org)
        
    def test_payer_unique_constraint(self):
        """Test organization + name uniqueness"""
        Payer.objects.create(
            organization=self.org,
            name="Duplicate Test",
            created_by=self.user
        )
        
        # Creating another payer with same name in same org should raise error
        with self.assertRaises(Exception):
            Payer.objects.create(
                organization=self.org,
                name="Duplicate Test",
                created_by=self.user
            )
    
    def test_payer_cnic_validation(self):
        """Test CNIC format validation"""
        # Valid CNIC format
        payer = Payer(
            organization=self.org,
            name="Valid CNIC",
            cnic_ntn="12345-1234567-1",
            created_by=self.user
        )
        payer.full_clean()  # Should not raise
        
        # Invalid CNIC format - should fail validation
        payer_invalid = Payer(
            organization=self.org,
            name="Invalid CNIC",
            cnic_ntn="invalid-format",
            created_by=self.user
        )
        with self.assertRaises(ValidationError):
            payer_invalid.full_clean()


class RevenueDemandModelTest(TestCase):
    """Test cases for RevenueDemand model"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Create organization
        self.org = Organization.objects.create(
            name="TMA Test"
        )
        
        # Create user
        self.user = User.objects.create_user(
            cnic='12345-1234567-1',
            email='testuser@example.com',
            password='testpass123',
            organization=self.org,
            role='FINANCE_OFFICER'
        )
        
        # Create fiscal year
        self.fy = FiscalYear.objects.create(
            year_name="2025-26",
            start_date=timezone.now().date(),
            end_date=timezone.now().date() + timedelta(days=365)
        )
        
        # Create department (global master data - no organization)
        self.dept = Department.objects.create(
            name="Finance",
            code="FIN"
        )
        
        self.function = FunctionCode.objects.create(
            code="401",
            name="General Administration"
        )
        
        # Create fund
        self.fund = Fund.objects.create(
            name="General Fund",
            code="GF01"
        )
        
        # Create account hierarchy: MajorHead → MinorHead → GlobalHead
        self.major_head = MajorHead.objects.create(
            code="C01",
            name="Tax Revenue"
        )
        
        self.minor_head = MinorHead.objects.create(
            code="C011",
            name="Property Tax",
            major=self.major_head
        )
        
        # Create revenue head (global head)
        self.global_head = GlobalHead.objects.create(
            code="C01101",
            name="Property Tax",
            minor=self.minor_head,
            account_type=AccountType.REVENUE
        )
        
        # Create budget head
        self.budget_head = BudgetHead.objects.create(
            fund=self.fund,
            global_head=self.global_head,
            function=self.function,
            posting_allowed=True
        )
        
        # Create AR system head with hierarchy
        self.ar_major = MajorHead.objects.create(
            code="A02",
            name="Advances and Deposits"
        )
        
        self.ar_minor = MinorHead.objects.create(
            code="A021",
            name="Receivables",
            major=self.ar_major
        )
        
        self.ar_global_head = GlobalHead.objects.create(
            code="A02101",
            name="Accounts Receivable",
            minor=self.ar_minor,
            account_type=AccountType.ASSET,
            system_code='AR'
        )
        
        self.ar_head = BudgetHead.objects.create(
            fund=self.fund,
            global_head=self.ar_global_head,
            function=self.function,
            posting_allowed=True
        )
        
        # Create payer
        self.payer = Payer.objects.create(
            organization=self.org,
            name="Test Payer",
            created_by=self.user
        )
        
    def test_demand_creation(self):
        """Test basic demand creation"""
        demand = RevenueDemand.objects.create(
            organization=self.org,
            fiscal_year=self.fy,
            payer=self.payer,
            budget_head=self.budget_head,
            challan_no="CH-2025-26-0001",
            issue_date=timezone.now().date(),
            due_date=timezone.now().date() + timedelta(days=30),
            amount=Decimal('1000.00'),
            created_by=self.user
        )
        
        self.assertEqual(demand.status, DemandStatus.DRAFT)
        self.assertEqual(demand.amount, Decimal('1000.00'))
        self.assertIsNone(demand.accrual_voucher)
        
    def test_demand_validation_revenue_head(self):
        """Test that budget_head must be a revenue account"""
        # Create expense head with hierarchy
        expense_major = MajorHead.objects.create(
            code="E01",
            name="Recurring Expenses"
        )
        
        expense_minor = MinorHead.objects.create(
            code="E011",
            name="Personal Emoluments",
            major=expense_major
        )
        
        expense_global = GlobalHead.objects.create(
            code="E01101",
            name="Salaries",
            minor=expense_minor,
            account_type=AccountType.EXPENDITURE
        )
        
        expense_head = BudgetHead.objects.create(
            fund=self.fund,
            global_head=expense_global,
            function=self.function,
            posting_allowed=True
        )
        
        # Try to create demand with expense head
        demand = RevenueDemand(
            organization=self.org,
            fiscal_year=self.fy,
            payer=self.payer,
            budget_head=expense_head,  # Wrong type!
            challan_no="CH-2025-26-0002",
            issue_date=timezone.now().date(),
            due_date=timezone.now().date() + timedelta(days=30),
            amount=Decimal('1000.00'),
            created_by=self.user
        )
        
        with self.assertRaises(ValidationError):
            demand.clean()
    
    def test_demand_date_validation(self):
        """Test that due date cannot be before issue date"""
        demand = RevenueDemand(
            organization=self.org,
            fiscal_year=self.fy,
            payer=self.payer,
            budget_head=self.budget_head,
            challan_no="CH-2025-26-0003",
            issue_date=timezone.now().date(),
            due_date=timezone.now().date() - timedelta(days=10),  # Before issue date!
            amount=Decimal('1000.00'),
            created_by=self.user
        )
        
        with self.assertRaises(ValidationError):
            demand.clean()
    
    def test_demand_amount_validation(self):
        """Test that amount must be positive"""
        demand = RevenueDemand(
            organization=self.org,
            fiscal_year=self.fy,
            payer=self.payer,
            budget_head=self.budget_head,
            challan_no="CH-2025-26-0004",
            issue_date=timezone.now().date(),
            due_date=timezone.now().date() + timedelta(days=30),
            amount=Decimal('-100.00'),  # Negative!
            created_by=self.user
        )
        
        with self.assertRaises(ValidationError):
            demand.clean()
    
    def test_demand_outstanding_calculation(self):
        """Test outstanding balance calculation"""
        demand = RevenueDemand.objects.create(
            organization=self.org,
            fiscal_year=self.fy,
            payer=self.payer,
            budget_head=self.budget_head,
            challan_no="CH-2025-26-0005",
            issue_date=timezone.now().date(),
            due_date=timezone.now().date() + timedelta(days=30),
            amount=Decimal('1000.00'),
            created_by=self.user
        )
        
        # Initially, outstanding should equal the demand amount
        self.assertEqual(demand.get_outstanding_balance(), Decimal('1000.00'))
        
    def test_demand_challan_number_uniqueness(self):
        """Test fiscal year + challan number uniqueness"""
        RevenueDemand.objects.create(
            organization=self.org,
            fiscal_year=self.fy,
            payer=self.payer,
            budget_head=self.budget_head,
            challan_no="CH-2025-26-0006",
            issue_date=timezone.now().date(),
            due_date=timezone.now().date() + timedelta(days=30),
            amount=Decimal('1000.00'),
            created_by=self.user
        )
        
        # Try to create another demand with same challan_no in same FY
        with self.assertRaises(Exception):
            RevenueDemand.objects.create(
                organization=self.org,
                fiscal_year=self.fy,
                payer=self.payer,
                budget_head=self.budget_head,
                challan_no="CH-2025-26-0006",  # Duplicate!
                issue_date=timezone.now().date(),
                due_date=timezone.now().date() + timedelta(days=30),
                amount=Decimal('2000.00'),
                created_by=self.user
            )


class RevenueCollectionModelTest(TestCase):
    """Test cases for RevenueCollection model"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Create organization
        self.org = Organization.objects.create(
            name="TMA Test"
        )
        
        # Create user
        self.user = User.objects.create_user(
            cnic='12345-1234567-1',
            email='testuser@example.com',
            password='testpass123',
            organization=self.org,
            role='CASHIER'
        )
        
        # Create fiscal year
        self.fy = FiscalYear.objects.create(
            year_name="2025-26",
            start_date=timezone.now().date(),
            end_date=timezone.now().date() + timedelta(days=365)
        )
        
        # Create function
        self.function = FunctionCode.objects.create(
            code="401",
            name="General Administration"
        )
        
        # Create fund
        self.fund = Fund.objects.create(
            name="General Fund",
            code="GF01"
        )
        
        # Create account hierarchy for revenue
        self.major_head = MajorHead.objects.create(
            code="C01",
            name="Tax Revenue"
        )
        
        self.minor_head = MinorHead.objects.create(
            code="C011",
            name="Property Tax",
            major=self.major_head
        )
        
        # Create revenue head
        self.global_head = GlobalHead.objects.create(
            code="C01101",
            name="Property Tax",
            minor=self.minor_head,
            account_type=AccountType.REVENUE
        )
        
        self.budget_head = BudgetHead.objects.create(
            fund=self.fund,
            global_head=self.global_head,
            function=self.function,
            posting_allowed=True
        )
        
        # Create bank account head with hierarchy
        self.bank_major = MajorHead.objects.create(
            code="A01",
            name="Current Assets"
        )
        
        self.bank_minor = MinorHead.objects.create(
            code="A011",
            name="Cash and Bank",
            major=self.bank_major
        )
        
        self.bank_global_head = GlobalHead.objects.create(
            code="A01101",
            name="Bank Account - NBP",
            minor=self.bank_minor,
            account_type=AccountType.ASSET
        )
        
        self.bank_budget_head = BudgetHead.objects.create(
            fund=self.fund,
            global_head=self.bank_global_head,
            function=self.function,
            posting_allowed=True
        )
        
        # Create bank account
        self.bank_account = BankAccount.objects.create(
            organization=self.org,
            title="NBP Main Account",
            account_number="1234567890",
            bank_name="National Bank",
            gl_code=self.bank_budget_head
        )
        
        # Create AR system head with hierarchy
        self.ar_major = MajorHead.objects.create(
            code="A02",
            name="Advances and Deposits"
        )
        
        self.ar_minor = MinorHead.objects.create(
            code="A021",
            name="Receivables",
            major=self.ar_major
        )
        
        self.ar_global_head = GlobalHead.objects.create(
            code="A02101",
            name="Accounts Receivable",
            minor=self.ar_minor,
            account_type=AccountType.ASSET,
            system_code='AR'
        )
        
        self.ar_head = BudgetHead.objects.create(
            fund=self.fund,
            global_head=self.ar_global_head,
            function=self.function,
            posting_allowed=True
        )
        
        # Create payer
        self.payer = Payer.objects.create(
            organization=self.org,
            name="Test Payer",
            created_by=self.user
        )
        
        # Create demand
        self.demand = RevenueDemand.objects.create(
            organization=self.org,
            fiscal_year=self.fy,
            payer=self.payer,
            budget_head=self.budget_head,
            challan_no="CH-2025-26-0001",
            issue_date=timezone.now().date(),
            due_date=timezone.now().date() + timedelta(days=30),
            amount=Decimal('1000.00'),
            status=DemandStatus.POSTED,
            created_by=self.user
        )
    
    def test_collection_creation(self):
        """Test basic collection creation"""
        collection = RevenueCollection.objects.create(
            organization=self.org,
            demand=self.demand,
            bank_account=self.bank_account,
            receipt_no="REC-2025-26-0001",
            receipt_date=timezone.now().date(),
            amount_received=Decimal('600.00'),
            instrument_type='CASH',
            created_by=self.user
        )
        
        self.assertEqual(collection.status, CollectionStatus.DRAFT)
        self.assertEqual(collection.amount_received, Decimal('600.00'))
        
    def test_collection_amount_validation(self):
        """Test that collection cannot exceed outstanding balance"""
        collection = RevenueCollection(
            organization=self.org,
            demand=self.demand,
            bank_account=self.bank_account,
            receipt_no="REC-2025-26-0002",
            receipt_date=timezone.now().date(),
            amount_received=Decimal('1500.00'),  # More than demand!
            instrument_type='CASH',
            created_by=self.user
        )
        
        with self.assertRaises(ValidationError):
            collection.clean()
    
    def test_collection_receipt_number_uniqueness(self):
        """Test organization + receipt_no uniqueness"""
        RevenueCollection.objects.create(
            organization=self.org,
            demand=self.demand,
            bank_account=self.bank_account,
            receipt_no="REC-2025-26-0003",
            receipt_date=timezone.now().date(),
            amount_received=Decimal('500.00'),
            instrument_type='CASH',
            created_by=self.user
        )
        
        # Try to create another collection with same receipt_no
        with self.assertRaises(Exception):
            RevenueCollection.objects.create(
                organization=self.org,
                demand=self.demand,
                bank_account=self.bank_account,
                receipt_no="REC-2025-26-0003",  # Duplicate!
                receipt_date=timezone.now().date(),
                amount_received=Decimal('300.00'),
                instrument_type='CASH',
                created_by=self.user
            )
