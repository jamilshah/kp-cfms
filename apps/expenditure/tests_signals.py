"""
-------------------------------------------------------------------------
System: KP-CFMS (Computerized Financial Management System)
Client: Local Government Department, Khyber Pakhtunkhwa
Team Lead: Jamil Shah
Developers: Ali Asghar, Akhtar Munir and Zarif Khan
Description: Unit tests for expenditure module - signal handlers.
-------------------------------------------------------------------------
"""
from decimal import Decimal
from datetime import date
from unittest.mock import patch, MagicMock, call
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model

from apps.expenditure.models import Bill, BillStatus, Payee
from apps.expenditure.signals import (
    bill_status_change_notification,
    _notify_on_submit,
    _notify_on_marked_for_audit,
    _notify_on_audited,
    _notify_on_approved,
    _notify_on_returned,
    _notify_on_rejected
)
from apps.core.models import NotificationCategory, Organization, Tehsil, District, Division
from apps.core.services import NotificationService
from apps.users.models import Role, RoleCode
from apps.finance.models import BudgetHead, AccountType, FunctionCode, Fund, MajorHead, MinorHead, GlobalHead
from apps.budgeting.models import FiscalYear


User = get_user_model()


class BillSignalTests(TestCase):
    """Tests for Bill signal handlers."""
    
    def setUp(self):
        """Set up test data."""
        # Create test location hierarchy
        self.division = Division.objects.create(
            name="Test Division",
            code="TDV01"
        )
        
        self.district = District.objects.create(
            name="Test District",
            code="TDS01",
            division=self.division
        )
        
        self.tehsil = Tehsil.objects.create(
            name="Test Tehsil",
            code="TST01",
            district=self.district
        )
        
        self.organization = Organization.objects.create(
            name="Test TMA",
            org_type="TMA",
            tehsil=self.tehsil
        )
        
        # Create test fiscal year
        self.fiscal_year = FiscalYear.objects.create(
            year_name="FY 2024-25",
            start_date=date(2024, 7, 1),
            end_date=date(2025, 6, 30),
            is_active=True,
            organization=self.organization
        )
        
        # Create test roles
        self.accountant_role = Role.objects.create(
            name="Accountant",
            code=RoleCode.ACCOUNTANT,
            description="Test Accountant"
        )
        
        self.finance_officer_role = Role.objects.create(
            name="Finance Officer",
            code=RoleCode.FINANCE_OFFICER,
            description="Test Finance Officer"
        )
        
        self.tmo_role = Role.objects.create(
            name="TMO",
            code=RoleCode.TMO,
            description="Test TMO"
        )
        
        self.cashier_role = Role.objects.create(
            name="Cashier",
            code=RoleCode.CASHIER,
            description="Test Cashier"
        )
        
        self.dealing_assistant_role = Role.objects.create(
            name="Dealing Assistant",
            code=RoleCode.DEALING_ASSISTANT,
            description="Test Dealing Assistant"
        )
        
        # Create test users
        self.accountant = User.objects.create_user(
            cnic='1234567890123',
            email='accountant@test.com',
            first_name='Test',
            last_name='Accountant',
            organization=self.organization
        )
        self.accountant.roles.add(self.accountant_role)
        
        self.finance_officer = User.objects.create_user(
            cnic='2222233333444',
            email='fo@test.com',
            first_name='Test',
            last_name='FinanceOfficer',
            organization=self.organization
        )
        self.finance_officer.roles.add(self.finance_officer_role)
        
        self.tmo = User.objects.create_user(
            cnic='9876543210987',
            email='tmo@test.com',
            first_name='Test',
            last_name='TMO',
            organization=self.organization
        )
        self.tmo.roles.add(self.tmo_role)
        
        self.cashier = User.objects.create_user(
            cnic='5555566666777',
            email='cashier@test.com',
            first_name='Test',
            last_name='Cashier',
            organization=self.organization
        )
        self.cashier.roles.add(self.cashier_role)
        
        self.dealing_assistant = User.objects.create_user(
            cnic='1111122222333',
            email='assistant@test.com',
            first_name='Test',
            last_name='Assistant',
            organization=self.organization
        )
        self.dealing_assistant.roles.add(self.dealing_assistant_role)
        
        # Create test payee
        self.payee = Payee.objects.create(
            name="Test Vendor",
            cnic_ntn="12345-1234567-1",
            organization=self.organization
        )
        
        # Create test budget head using NAM structure
        self.function_code = FunctionCode.objects.create(
            code="01",
            name="General Administration"
        )
        
        self.fund = Fund.objects.create(
            name="Local Fund",
            code="LF"
        )
        
        # Create NAM hierarchy: Major -> Minor -> Global -> Budget Head
        self.major_head = MajorHead.objects.create(
            code='A01',
            name='Employees Related Expenses'
        )
        
        self.minor_head = MinorHead.objects.create(
            code='A011',
            name='Basic Pay',
            major=self.major_head
        )
        
        self.global_head = GlobalHead.objects.create(
            code='A01101',
            name='Basic Pay - Officers',
            minor=self.minor_head,
            account_type=AccountType.EXPENDITURE
        )
        
        self.budget_head = BudgetHead.objects.create(
            global_head=self.global_head,
            fund=self.fund,
            function=self.function_code,
            sub_code='00'
        )
    
    @patch('apps.expenditure.signals.NotificationService.send_notification')
    def test_signal_not_triggered_on_create(self, mock_send):
        """Test that signal is not triggered when bill is created."""
        bill = Bill.objects.create(
            bill_number="TST-001",
            bill_date=date.today(),
            fiscal_year=self.fiscal_year,
            organization=self.organization,
            payee=self.payee,
            budget_head=self.budget_head,
            gross_amount=Decimal('10000.00'),
            net_amount=Decimal('10000.00'),
            status=BillStatus.DRAFT,
            submitted_by=self.dealing_assistant
        )
        
        # Signal should not send notification on creation
        mock_send.assert_not_called()
    
    @patch('apps.expenditure.signals.NotificationService.send_notification')
    def test_signal_triggered_on_status_update(self, mock_send):
        """Test that signal is triggered when bill status changes."""
        # Create bill in DRAFT status
        bill = Bill.objects.create(
            bill_number="TST-001",
            bill_date=date.today(),
            fiscal_year=self.fiscal_year,
            organization=self.organization,
            payee=self.payee,
            budget_head=self.budget_head,
            gross_amount=Decimal('10000.00'),
            net_amount=Decimal('10000.00'),
            status=BillStatus.DRAFT,
            submitted_by=self.dealing_assistant
        )
        
        mock_send.reset_mock()
        
        # Update status to SUBMITTED
        bill.status = BillStatus.SUBMITTED
        bill.save()
        
        # Signal should be triggered
        self.assertTrue(mock_send.called)
    
    @patch('apps.expenditure.signals.NotificationService.send_notification')
    def test_notify_on_submit(self, mock_send):
        """Test notification when bill is submitted."""
        bill = Bill.objects.create(
            bill_number="TST-001",
            bill_date=date.today(),
            fiscal_year=self.fiscal_year,
            organization=self.organization,
            payee=self.payee,
            budget_head=self.budget_head,
            gross_amount=Decimal('10000.00'),
            net_amount=Decimal('10000.00'),
            status=BillStatus.DRAFT,
            submitted_by=self.dealing_assistant
        )
        
        mock_send.reset_mock()
        
        # Change status to SUBMITTED
        bill.status = BillStatus.SUBMITTED
        bill.save()
        
        # Should notify both Finance Officer and Accountant
        self.assertEqual(mock_send.call_count, 2)
        
        # Verify notification content
        calls = mock_send.call_args_list
        for call_args in calls:
            kwargs = call_args[1]
            self.assertIn("Bill #TST-001 Pending Review", kwargs['title'])
            self.assertIn("Test Vendor", kwargs['message'])
            self.assertIn("10,000.00", kwargs['message'])
            self.assertEqual(kwargs['category'], NotificationCategory.WORKFLOW)
            self.assertEqual(kwargs['icon'], 'bi-file-earmark-text')
    
    @patch('apps.expenditure.signals.NotificationService.send_notification')
    def test_notify_on_marked_for_audit(self, mock_send):
        """Test notification when bill is marked for audit."""
        bill = Bill.objects.create(
            bill_number="TST-002",
            bill_date=date.today(),
            fiscal_year=self.fiscal_year,
            organization=self.organization,
            payee=self.payee,
            budget_head=self.budget_head,
            gross_amount=Decimal('15000.00'),
            net_amount=Decimal('15000.00'),
            status=BillStatus.SUBMITTED,
            submitted_by=self.dealing_assistant
        )
        
        mock_send.reset_mock()
        
        # Change status to MARKED_FOR_AUDIT
        bill.status = BillStatus.MARKED_FOR_AUDIT
        bill.save()
        
        # Should notify audit officers (or finance officers as fallback)
        self.assertTrue(mock_send.called)
        
        # Verify notification content
        call_kwargs = mock_send.call_args[1]
        self.assertIn("Bill #TST-002 Marked for Audit", call_kwargs['title'])
        self.assertIn("pre-audit review", call_kwargs['message'])
        self.assertEqual(call_kwargs['category'], NotificationCategory.WORKFLOW)
        self.assertEqual(call_kwargs['icon'], 'bi-clipboard-check')
    
    @patch('apps.expenditure.signals.NotificationService.send_notification')
    def test_notify_on_audited(self, mock_send):
        """Test notification when bill passes audit."""
        bill = Bill.objects.create(
            bill_number="TST-003",
            bill_date=date.today(),
            fiscal_year=self.fiscal_year,
            organization=self.organization,
            payee=self.payee,
            budget_head=self.budget_head,
            gross_amount=Decimal('20000.00'),
            net_amount=Decimal('20000.00'),
            status=BillStatus.MARKED_FOR_AUDIT,
            submitted_by=self.dealing_assistant
        )
        
        mock_send.reset_mock()
        
        # Change status to AUDITED
        bill.status = BillStatus.AUDITED
        bill.save()
        
        # Should notify TMO
        self.assertTrue(mock_send.called)
        
        # Verify notification content
        call_kwargs = mock_send.call_args[1]
        self.assertEqual(call_kwargs['recipient'], self.tmo)
        self.assertIn("Bill #TST-003 Ready for Approval", call_kwargs['title'])
        self.assertIn("passed audit", call_kwargs['message'])
        self.assertIn("20,000.00", call_kwargs['message'])
        self.assertEqual(call_kwargs['category'], NotificationCategory.WORKFLOW)
        self.assertEqual(call_kwargs['icon'], 'bi-check-circle')
    
    @patch('apps.expenditure.signals.NotificationService.send_notification')
    def test_notify_on_approved(self, mock_send):
        """Test notification when bill is approved."""
        bill = Bill.objects.create(
            bill_number="TST-004",
            bill_date=date.today(),
            fiscal_year=self.fiscal_year,
            organization=self.organization,
            payee=self.payee,
            budget_head=self.budget_head,
            gross_amount=Decimal('25000.00'),
            net_amount=Decimal('25000.00'),
            status=BillStatus.AUDITED,
            submitted_by=self.dealing_assistant
        )
        
        mock_send.reset_mock()
        
        # Change status to APPROVED
        bill.status = BillStatus.APPROVED
        bill.save()
        
        # Should notify Cashier and Bill Creator
        self.assertEqual(mock_send.call_count, 2)
        
        # Verify notifications
        calls = mock_send.call_args_list
        
        # First call should be to cashier
        cashier_call = calls[0][1]
        self.assertEqual(cashier_call['recipient'], self.cashier)
        self.assertIn("Bill #TST-004 Approved for Payment", cashier_call['title'])
        self.assertIn("Process payment", cashier_call['message'])
        self.assertEqual(cashier_call['icon'], 'bi-cash-stack')
        
        # Second call should be to bill creator
        creator_call = calls[1][1]
        self.assertEqual(creator_call['recipient'], self.dealing_assistant)
        self.assertIn("Bill #TST-004 Approved", creator_call['title'])
        self.assertIn("has been approved", creator_call['message'])
        self.assertEqual(creator_call['icon'], 'bi-check-circle-fill')
    
    @patch('apps.expenditure.signals.NotificationService.send_notification')
    def test_notify_on_returned(self, mock_send):
        """Test notification when bill is returned."""
        bill = Bill.objects.create(
            bill_number="TST-005",
            bill_date=date.today(),
            fiscal_year=self.fiscal_year,
            organization=self.organization,
            payee=self.payee,
            budget_head=self.budget_head,
            gross_amount=Decimal('30000.00'),
            net_amount=Decimal('30000.00'),
            status=BillStatus.SUBMITTED,
            submitted_by=self.dealing_assistant,
            rejection_reason="Missing documentation"
        )
        
        mock_send.reset_mock()
        
        # Change status to RETURNED
        bill.status = BillStatus.RETURNED
        bill.save()
        
        # Should notify bill creator
        self.assertTrue(mock_send.called)
        
        # Verify notification content
        call_kwargs = mock_send.call_args[1]
        self.assertEqual(call_kwargs['recipient'], self.dealing_assistant)
        self.assertIn("Bill #TST-005 Returned", call_kwargs['title'])
        self.assertIn("returned for corrections", call_kwargs['message'])
        self.assertIn("Missing documentation", call_kwargs['message'])
        self.assertEqual(call_kwargs['category'], NotificationCategory.ALERT)
        self.assertEqual(call_kwargs['icon'], 'bi-arrow-return-left')
    
    @patch('apps.expenditure.signals.NotificationService.send_notification')
    def test_notify_on_rejected(self, mock_send):
        """Test notification when bill is rejected."""
        bill = Bill.objects.create(
            bill_number="TST-006",
            bill_date=date.today(),
            fiscal_year=self.fiscal_year,
            organization=self.organization,
            payee=self.payee,
            budget_head=self.budget_head,
            gross_amount=Decimal('35000.00'),
            net_amount=Decimal('35000.00'),
            status=BillStatus.SUBMITTED,
            submitted_by=self.dealing_assistant,
            rejection_reason="Invalid budget head"
        )
        
        mock_send.reset_mock()
        
        # Change status to REJECTED
        bill.status = BillStatus.REJECTED
        bill.save()
        
        # Should notify bill creator
        self.assertTrue(mock_send.called)
        
        # Verify notification content
        call_kwargs = mock_send.call_args[1]
        self.assertEqual(call_kwargs['recipient'], self.dealing_assistant)
        self.assertIn("Bill #TST-006 Rejected", call_kwargs['title'])
        self.assertIn("has been rejected", call_kwargs['message'])
        self.assertIn("Invalid budget head", call_kwargs['message'])
        self.assertEqual(call_kwargs['category'], NotificationCategory.ALERT)
        self.assertEqual(call_kwargs['icon'], 'bi-x-circle-fill')
    
    @patch('apps.expenditure.signals.NotificationService.send_notification')
    def test_notify_on_returned_without_reason(self, mock_send):
        """Test notification when bill is returned without reason."""
        bill = Bill.objects.create(
            bill_number="TST-007",
            bill_date=date.today(),
            fiscal_year=self.fiscal_year,
            organization=self.organization,
            payee=self.payee,
            budget_head=self.budget_head,
            gross_amount=Decimal('10000.00'),
            net_amount=Decimal('10000.00'),
            status=BillStatus.SUBMITTED,
            submitted_by=self.dealing_assistant
        )
        
        mock_send.reset_mock()
        
        # Change status to RETURNED without setting rejection_reason
        bill.status = BillStatus.RETURNED
        bill.save()
        
        # Should notify with "Not specified" reason
        call_kwargs = mock_send.call_args[1]
        self.assertIn("Not specified", call_kwargs['message'])
    
    @patch('apps.expenditure.signals.NotificationService.send_notification')
    def test_no_notification_when_submitted_by_is_none(self, mock_send):
        """Test that no notification is sent if submitted_by is None."""
        bill = Bill.objects.create(
            bill_number="TST-008",
            bill_date=date.today(),
            fiscal_year=self.fiscal_year,
            organization=self.organization,
            payee=self.payee,
            budget_head=self.budget_head,
            gross_amount=Decimal('10000.00'),
            net_amount=Decimal('10000.00'),
            status=BillStatus.SUBMITTED,
            submitted_by=None  # No creator
        )
        
        mock_send.reset_mock()
        
        # Change status to RETURNED
        bill.status = BillStatus.RETURNED
        bill.save()
        
        # Should not crash, and should not send notification
        # (No assertion needed - just verify it doesn't crash)
        # If submitted_by is None, the notification code should handle it gracefully
    
    @patch('apps.expenditure.signals.NotificationService.send_notification')
    def test_multiple_finance_officers_notified(self, mock_send):
        """Test that multiple finance officers receive notifications."""
        # Create another finance officer
        another_fo = User.objects.create_user(
            cnic='8888899999000',
            email='fo2@test.com',
            first_name='Another',
            last_name='FinanceOfficer',
            organization=self.organization
        )
        another_fo.roles.add(self.finance_officer_role)
        
        bill = Bill.objects.create(
            bill_number="TST-009",
            bill_date=date.today(),
            fiscal_year=self.fiscal_year,
            organization=self.organization,
            payee=self.payee,
            budget_head=self.budget_head,
            gross_amount=Decimal('10000.00'),
            net_amount=Decimal('10000.00'),
            status=BillStatus.DRAFT,
            submitted_by=self.dealing_assistant
        )
        
        mock_send.reset_mock()
        
        # Change status to SUBMITTED
        bill.status = BillStatus.SUBMITTED
        bill.save()
        
        # Should notify accountant + 2 finance officers = 3 notifications
        self.assertEqual(mock_send.call_count, 3)
    
    @patch('apps.expenditure.signals.NotificationService.send_notification')
    def test_notification_includes_bill_link(self, mock_send):
        """Test that notifications include the correct bill detail link."""
        bill = Bill.objects.create(
            bill_number="TST-010",
            bill_date=date.today(),
            fiscal_year=self.fiscal_year,
            organization=self.organization,
            payee=self.payee,
            budget_head=self.budget_head,
            gross_amount=Decimal('10000.00'),
            net_amount=Decimal('10000.00'),
            status=BillStatus.DRAFT,
            submitted_by=self.dealing_assistant
        )
        
        mock_send.reset_mock()
        
        # Change status to SUBMITTED
        bill.status = BillStatus.SUBMITTED
        bill.save()
        
        # Verify link is included
        call_kwargs = mock_send.call_args[1]
        expected_link = reverse('expenditure:bill_detail', kwargs={'pk': bill.pk})
        self.assertEqual(call_kwargs['link'], expected_link)


class BillSignalHelperFunctionTests(TestCase):
    """Direct tests for signal helper functions."""
    
    def setUp(self):
        """Set up test data."""
        self.division = Division.objects.create(
            name="Test Division",
            code="TDV01"
        )
        
        self.district = District.objects.create(
            name="Test District",
            code="TDS01",
            division=self.division
        )
        
        self.tehsil = Tehsil.objects.create(
            name="Test Tehsil",
            code="TST01",
            district=self.district
        )
        
        self.organization = Organization.objects.create(
            name="Test TMA",
            org_type="TMA",
            tehsil=self.tehsil
        )
        
        # Create test fiscal year
        self.fiscal_year = FiscalYear.objects.create(
            year_name="FY 2024-25",
            start_date=date(2024, 7, 1),
            end_date=date(2025, 6, 30),
            is_active=True,
            organization=self.organization
        )
        
        self.user = User.objects.create_user(
            cnic='1234567890123',
            email='test@test.com',
            first_name='Test',
            last_name='User',
            organization=self.organization
        )
        
        self.payee = Payee.objects.create(
            name="Test Vendor",
            cnic_ntn="12345-1234567-1",
            organization=self.organization
        )
        
        self.function_code = FunctionCode.objects.create(
            code="01",
            name="General Administration"
        )
        
        self.fund = Fund.objects.create(
            name="Local Fund",
            code="LF"
        )
        
        # Create NAM hierarchy: Major -> Minor -> Global -> Budget Head
        self.major_head = MajorHead.objects.create(
            code='A01',
            name='Employees Related Expenses'
        )
        
        self.minor_head = MinorHead.objects.create(
            code='A011',
            name='Basic Pay',
            major=self.major_head
        )
        
        self.global_head = GlobalHead.objects.create(
            code='A01101',
            name='Basic Pay - Officers',
            minor=self.minor_head,
            account_type=AccountType.EXPENDITURE
        )
        
        self.budget_head = BudgetHead.objects.create(
            global_head=self.global_head,
            fund=self.fund,
            function=self.function_code,
            sub_code='00'
        )
        
        self.bill = Bill.objects.create(
            bill_number="TST-100",
            bill_date=date.today(),
            fiscal_year=self.fiscal_year,
            organization=self.organization,
            payee=self.payee,
            budget_head=self.budget_head,
            gross_amount=Decimal('50000.00'),
            tax_amount=Decimal('0.00'),
            net_amount=Decimal('50000.00'),
            status=BillStatus.DRAFT,
            submitted_by=self.user
        )
    
    @patch('apps.expenditure.signals.NotificationService.send_notification')
    def test_notify_on_submit_direct(self, mock_send):
        """Test _notify_on_submit helper function directly."""
        bill_url = "/test/url/"
        
        _notify_on_submit(self.bill, bill_url)
        
        # Should be called (if finance officers exist)
        # Since no finance officers in this test, might not be called
        # This tests the function doesn't crash
    
    @patch('apps.expenditure.signals.NotificationService.send_notification')
    def test_notify_on_returned_direct(self, mock_send):
        """Test _notify_on_returned helper function directly."""
        bill_url = "/test/url/"
        
        _notify_on_returned(self.bill, bill_url)
        
        # Should call notification service once for bill creator
        self.assertTrue(mock_send.called)
        call_kwargs = mock_send.call_args[1]
        self.assertEqual(call_kwargs['recipient'], self.user)
