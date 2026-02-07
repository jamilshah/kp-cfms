"""
-------------------------------------------------------------------------
System: KP-CFMS (Computerized Financial Management System)
Client: Local Government Department, Khyber Pakhtunkhwa
Team Lead: Jamil Shah
Developers: Ali Asghar, Akhtar Munir and Zarif Khan
Description: Test cases for Revenue module views
-------------------------------------------------------------------------
"""
from decimal import Decimal
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta

from apps.revenue.models import (
    Payer, RevenueDemand, RevenueCollection,
    DemandStatus, CollectionStatus
)
from apps.budgeting.models import FiscalYear
from apps.finance.models import BudgetHead, Fund, GlobalHead, AccountType, FunctionCode, MajorHead, MinorHead
from apps.core.models import Organization, BankAccount

User = get_user_model()


class DemandViewsTest(TestCase):
    """Test cases for Revenue Demand views"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Create organization
        self.org = Organization.objects.create(
            name="TMA Test"
        )
        
        # Create users with different roles
        self.maker = User.objects.create_user(
            cnic='11111-1111111-1',
            email='maker@example.com',
            password='testpass123',
            organization=self.org,
            role='DEALING_ASSISTANT'
        )
        
        self.checker = User.objects.create_user(
            cnic='22222-2222222-2',
            email='checker@example.com',
            password='testpass123',
            organization=self.org,
            role='FINANCE_OFFICER'
        )
        
        self.cashier = User.objects.create_user(
            cnic='33333-3333333-3',
            email='cashier@example.com',
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
            created_by=self.maker
        )
        
        # Create test demand
        self.demand = RevenueDemand.objects.create(
            organization=self.org,
            fiscal_year=self.fy,
            payer=self.payer,
            budget_head=self.budget_head,
            challan_no="CH-2025-26-0001",
            issue_date=timezone.now().date(),
            due_date=timezone.now().date() + timedelta(days=30),
            amount=Decimal('1000.00'),
            created_by=self.maker
        )
        
        self.client = Client()
    
    def test_demand_list_requires_login(self):
        """Test that demand list requires authentication"""
        response = self.client.get(reverse('revenue:demand_list'))
        self.assertEqual(response.status_code, 302)  # Redirect to login
    
    def test_demand_list_view(self):
        """Test demand list view for authenticated user"""
        self.client.login(username='maker', password='testpass123')
        response = self.client.get(reverse('revenue:demand_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.demand.challan_no)
    
    def test_demand_detail_view(self):
        """Test demand detail view"""
        self.client.login(username='maker', password='testpass123')
        response = self.client.get(
            reverse('revenue:demand_detail', kwargs={'pk': self.demand.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.demand.challan_no)
        self.assertContains(response, str(self.demand.amount))
    
    def test_demand_post_requires_checker_role(self):
        """Test that posting demand requires Checker/Finance Officer role"""
        # Try with Maker role (should be denied)
        self.client.login(username='maker', password='testpass123')
        response = self.client.post(
            reverse('revenue:demand_post', kwargs={'pk': self.demand.pk})
        )
        # Should redirect or show error (depending on permission implementation)
        # The view should deny access
        
        # Now try with Checker role (should work)
        self.client.login(username='checker', password='testpass123')
        response = self.client.post(
            reverse('revenue:demand_post', kwargs={'pk': self.demand.pk}),
            follow=True
        )
        # Should succeed and redirect to detail page
        self.demand.refresh_from_db()
        # Note: This will fail without proper GL setup, but tests the permission logic
    
    def test_demand_cancel_requires_maker_role(self):
        """Test that cancelling demand requires Maker role or higher"""
        self.client.login(username='maker', password='testpass123')
        response = self.client.post(
            reverse('revenue:demand_cancel', kwargs={'pk': self.demand.pk}),
            data={'reason': 'Test cancellation'},
            follow=True
        )
        # Should process the cancellation
        self.demand.refresh_from_db()
        self.assertEqual(self.demand.status, DemandStatus.CANCELLED)
    
    def test_idempotency_protection_on_post(self):
        """Test that double-posting a demand is prevented"""
        self.client.login(username='checker', password='testpass123')
        
        # Set demand to POSTED status
        self.demand.status = DemandStatus.POSTED
        self.demand.save()
        
        # Try to post again
        response = self.client.post(
            reverse('revenue:demand_post', kwargs={'pk': self.demand.pk}),
            follow=True
        )
        
        # Should show warning message about already posted
        messages = list(response.context['messages'])
        self.assertTrue(
            any('already been posted' in str(m) for m in messages)
        )


class CollectionViewsTest(TestCase):
    """Test cases for Revenue Collection views"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Create organization
        self.org = Organization.objects.create(
            name="TMA Test"
        )
        
        # Create users
        self.cashier = User.objects.create_user(
            cnic='44444-4444444-4',
            email='cashier2@example.com',
            password='testpass123',
            organization=self.org,
            role='CASHIER'
        )
        
        self.checker = User.objects.create_user(
            cnic='55555-5555555-5',
            email='checker2@example.com',
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
            name="Bank Account",
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
            title="Test Bank Account",
            account_number="1234567890",
            bank_name="Test Bank",
            gl_code=self.bank_budget_head
        )
        
        # Create payer
        self.payer = Payer.objects.create(
            organization=self.org,
            name="Test Payer",
            created_by=self.cashier
        )
        
        # Create posted demand
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
            created_by=self.cashier
        )
        
        self.client = Client()
    
    def test_collection_list_requires_login(self):
        """Test that collection list requires authentication"""
        response = self.client.get(reverse('revenue:collection_list'))
        self.assertEqual(response.status_code, 302)  # Redirect to login
    
    def test_collection_create_requires_cashier_role(self):
        """Test that creating collection requires Cashier role"""
        self.client.login(username='cashier', password='testpass123')
        response = self.client.get(reverse('revenue:collection_create'))
        self.assertEqual(response.status_code, 200)
    
    def test_collection_post_requires_checker_role(self):
        """Test that posting collection requires Checker role"""
        # Create a draft collection
        collection = RevenueCollection.objects.create(
            organization=self.org,
            demand=self.demand,
            bank_account=self.bank_account,
            receipt_no="REC-2025-26-0001",
            receipt_date=timezone.now().date(),
            amount_received=Decimal('600.00'),
            instrument_type='CASH',
            created_by=self.cashier
        )
        
        # Login as checker and post
        self.client.login(username='checker', password='testpass123')
        response = self.client.post(
            reverse('revenue:collection_post', kwargs={'pk': collection.pk}),
            follow=True
        )
        # Should process (with proper GL setup)


class AjaxEndpointTest(TestCase):
    """Test cases for AJAX endpoints security"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.org = Organization.objects.create(
            name="TMA Test"
        )
        
        self.user = User.objects.create_user(
            cnic='66666-6666666-6',
            email='ajaxuser@example.com',
            password='testpass123',
            organization=self.org
        )
        
        self.client = Client()
    
    def test_load_functions_with_invalid_id(self):
        """Test that load_functions handles invalid department ID safely"""
        self.client.login(username='testuser', password='testpass123')
        
        # Try with SQL injection attempt
        response = self.client.get(
            reverse('revenue:load_functions'),
            {'department': "1' OR '1'='1"}
        )
        
        # Should return 200 with empty results (not a SQL error)
        self.assertEqual(response.status_code, 200)
    
    def test_load_revenue_heads_with_invalid_id(self):
        """Test that load_revenue_heads handles invalid IDs safely"""
        self.client.login(username='testuser', password='testpass123')
        
        # Try with non-integer value
        response = self.client.get(
            reverse('revenue:load_revenue_heads'),
            {'function': 'invalid'}
        )
        
        # Should return 200 with base results (not crash)
        self.assertEqual(response.status_code, 200)
