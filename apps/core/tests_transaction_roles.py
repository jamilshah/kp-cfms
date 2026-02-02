"""
-------------------------------------------------------------------------
System: KP-CFMS (Computerized Financial Management System)
Client: Local Government Department, Khyber Pakhtunkhwa
Team Lead: Jamil Shah
Developers: Ali Asghar, Akhtar Munir and Zarif Khan
Description: Tests for role-based access control on transaction views.
             Ensures proper Maker/Checker/Approver workflow enforcement.
-------------------------------------------------------------------------
"""
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import Group

from apps.users.models import CustomUser, Role
from apps.core.models import Organization, Tehsil, District, Division
from apps.budgeting.models import FiscalYear
from apps.expenditure.models import Payee, Bill
from apps.revenue.models import Payer, RevenueDemand, RevenueCollection
from apps.finance.models import Voucher, Fund, BudgetHead, GlobalHead, MinorHead, MajorHead
from datetime import date, timedelta


class TransactionRoleAccessTestCase(TestCase):
    """Test suite for role-based access control on transaction views."""
    
    def setUp(self):
        """Set up test data."""
        # Create roles
        self.maker_role = Role.objects.create(
            code='DEALING_ASSISTANT',
            name='Dealing Assistant',
            group=Group.objects.create(name='Dealing Assistant'),
            is_system_role=True
        )
        
        self.cashier_role = Role.objects.create(
            code='CASHIER',
            name='Cashier',
            group=Group.objects.create(name='Cashier'),
            is_system_role=True
        )
        
        self.tma_admin_role = Role.objects.create(
            code='TMA_ADMIN',
            name='TMA Administrator',
            group=Group.objects.create(name='TMA Administrator'),
            is_system_role=True
        )
        
        self.accountant_role = Role.objects.create(
            code='ACCOUNTANT',
            name='Accountant',
            group=Group.objects.create(name='Accountant'),
            is_system_role=True
        )
        
        # Create organization
        division = Division.objects.create(name='Test Division', code='TD')
        district = District.objects.create(
            division=division,
            name='Test District',
            code='TDT'
        )
        tehsil = Tehsil.objects.create(
            district=district,
            name='Test Tehsil',
            code='TTL'
        )
        self.organization = Organization.objects.create(
            name='Test TMA',
            tehsil=tehsil,
            org_type='TMA'
        )
        
        # Create fiscal year
        self.fiscal_year = FiscalYear.objects.create(
            organization=self.organization,
            year_name='2025-2026',
            start_date=date(2025, 7, 1),
            end_date=date(2026, 6, 30),
            is_active=True
        )
        
        # Create users
        self.maker_user = CustomUser.objects.create_user(
            cnic='12345-1234567-1',
            email='maker@test.com',
            first_name='Maker',
            last_name='User',
            password='testpass123',
            organization=self.organization
        )
        self.maker_user.roles.add(self.maker_role)
        
        self.cashier_user = CustomUser.objects.create_user(
            cnic='12345-1234567-2',
            email='cashier@test.com',
            first_name='Cashier',
            last_name='User',
            password='testpass123',
            organization=self.organization
        )
        self.cashier_user.roles.add(self.cashier_role)
        
        self.tma_admin_user = CustomUser.objects.create_user(
            cnic='12345-1234567-3',
            email='tmaadmin@test.com',
            first_name='TMA Admin',
            last_name='User',
            password='testpass123',
            organization=self.organization
        )
        self.tma_admin_user.roles.add(self.tma_admin_role)
        
        self.accountant_user = CustomUser.objects.create_user(
            cnic='12345-1234567-4',
            email='accountant@test.com',
            first_name='Accountant',
            last_name='User',
            password='testpass123',
            organization=self.organization
        )
        self.accountant_user.roles.add(self.accountant_role)
        
        self.client = Client()
    
    # ============================================================
    # Expenditure Module Tests
    # ============================================================
    
    def test_maker_can_create_payee(self):
        """Test that Maker (Dealing Assistant) can create payees."""
        self.client.login(cnic='12345-1234567-1', password='testpass123')
        
        url = reverse('expenditure:payee_create')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
    
    def test_tma_admin_cannot_create_payee(self):
        """Test that TMA Admin cannot create payees (403 Forbidden)."""
        self.client.login(cnic='12345-1234567-3', password='testpass123')
        
        url = reverse('expenditure:payee_create')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 403)
    
    def test_accountant_cannot_create_payee(self):
        """Test that Accountant cannot create payees (403 Forbidden)."""
        self.client.login(cnic='12345-1234567-4', password='testpass123')
        
        url = reverse('expenditure:payee_create')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 403)
    
    def test_maker_can_create_bill(self):
        """Test that Maker can create bills."""
        self.client.login(cnic='12345-1234567-1', password='testpass123')
        
        url = reverse('expenditure:bill_create')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
    
    def test_tma_admin_cannot_create_bill(self):
        """Test that TMA Admin cannot create bills."""
        self.client.login(cnic='12345-1234567-3', password='testpass123')
        
        url = reverse('expenditure:bill_create')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 403)
    
    def test_maker_can_create_payment(self):
        """Test that Maker can create payments."""
        self.client.login(cnic='12345-1234567-1', password='testpass123')
        
        url = reverse('expenditure:payment_create')
        response = self.client.get(url)
        
        # May redirect if no approved bills, but should not be 403
        self.assertIn(response.status_code, [200, 302])
    
    def test_tma_admin_cannot_create_payment(self):
        """Test that TMA Admin cannot create payments."""
        self.client.login(cnic='12345-1234567-3', password='testpass123')
        
        url = reverse('expenditure:payment_create')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 403)
    
    # ============================================================
    # Revenue Module Tests
    # ============================================================
    
    def test_maker_can_create_payer(self):
        """Test that Maker can create payers."""
        self.client.login(cnic='12345-1234567-1', password='testpass123')
        
        url = reverse('revenue:payer_create')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
    
    def test_tma_admin_cannot_create_payer(self):
        """Test that TMA Admin cannot create payers."""
        self.client.login(cnic='12345-1234567-3', password='testpass123')
        
        url = reverse('revenue:payer_create')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 403)
    
    def test_maker_can_create_demand(self):
        """Test that Maker can create revenue demands."""
        self.client.login(cnic='12345-1234567-1', password='testpass123')
        
        url = reverse('revenue:demand_create')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
    
    def test_tma_admin_cannot_create_demand(self):
        """Test that TMA Admin cannot create demands."""
        self.client.login(cnic='12345-1234567-3', password='testpass123')
        
        url = reverse('revenue:demand_create')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 403)
    
    def test_cashier_can_create_collection(self):
        """Test that Cashier can create revenue collections."""
        self.client.login(cnic='12345-1234567-2', password='testpass123')
        
        url = reverse('revenue:collection_create')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
    
    def test_maker_cannot_create_collection(self):
        """Test that Maker cannot create collections (only Cashier can)."""
        self.client.login(cnic='12345-1234567-1', password='testpass123')
        
        url = reverse('revenue:collection_create')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 403)
    
    def test_tma_admin_cannot_create_collection(self):
        """Test that TMA Admin cannot create collections."""
        self.client.login(cnic='12345-1234567-3', password='testpass123')
        
        url = reverse('revenue:collection_create')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 403)
    
    # ============================================================
    # Finance Module Tests
    # ============================================================
    
    def test_maker_can_create_voucher(self):
        """Test that Maker can create manual vouchers."""
        self.client.login(cnic='12345-1234567-1', password='testpass123')
        
        url = reverse('finance:voucher_create')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
    
    def test_tma_admin_cannot_create_voucher(self):
        """Test that TMA Admin cannot create vouchers."""
        self.client.login(cnic='12345-1234567-3', password='testpass123')
        
        url = reverse('finance:voucher_create')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 403)
    
    def test_accountant_cannot_create_voucher(self):
        """Test that Accountant cannot create vouchers (only verify)."""
        self.client.login(cnic='12345-1234567-4', password='testpass123')
        
        url = reverse('finance:voucher_create')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 403)


class RoleSegregationSummaryTest(TestCase):
    """Summary test to document role segregation."""
    
    def test_role_segregation_documentation(self):
        """
        Document the role segregation for transactions:
        
        CREATE Operations (Maker - Dealing Assistant):
        - Payees/Payers (Master data)
        - Bills (Expenditure)
        - Payments (Expenditure)
        - Revenue Demands
        - Manual Vouchers
        
        RECORD Operations (Cashier):
        - Revenue Collections (Cash/Bank receipts)
        
        VERIFY Operations (Checker - Accountant):
        - Review bills
        - Review vouchers
        - Review demands
        
        APPROVE Operations (Approver - TMO):
        - Approve bills
        - Approve vouchers
        - Sign payments
        
        CONFIGURE Operations (TMA Admin):
        - User management
        - System settings
        - Master data configuration
        - NOT allowed to create transactions
        """
        self.assertTrue(True)  # Documentation test
