"""
-------------------------------------------------------------------------
System: KP-CFMS (Computerized Financial Management System)
Client: Local Government Department, Khyber Pakhtunkhwa
Team Lead: Jamil Shah
Developers: Ali Asghar, Akhtar Munir and Zarif Khan
Description: Comprehensive tests for System Code functionality including
             GL automation, account configuration, and workflow integration.
-------------------------------------------------------------------------
"""
from decimal import Decimal
from django.test import TestCase
from django.core.management import call_command
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from io import StringIO

from apps.finance.models import (
    MajorHead, MinorHead, GlobalHead, BudgetHead, Fund, FunctionCode,
    SystemCode, AccountType, Voucher, JournalEntry, VoucherType
)
from apps.core.models import Organization
from apps.budgeting.models import FiscalYear
from apps.expenditure.models import Payee, Bill, BillLine, Payment, BillStatus
from apps.revenue.models import Payer, RevenueDemand, RevenueCollection

User = get_user_model()


class SystemCodeModelTests(TestCase):
    """Test System Code enum and model relationships."""
    
    def test_system_code_enum_complete(self):
        """Test that all required system codes are defined."""
        expected_codes = [
            'SYS_SUSPENSE', 'CLEARING_CHQ', 'CLEARING_IT', 'CLEARING_GST',
            'CLEARING_SEC', 'AP', 'AR', 'TAX_IT', 'TAX_GST'
        ]
        
        actual_codes = [choice[0] for choice in SystemCode.choices]
        
        for code in expected_codes:
            self.assertIn(code, actual_codes, f"SystemCode.{code} is missing from enum")
    
    def test_system_code_uniqueness(self):
        """Test that system_code field is unique on GlobalHead."""
        major = MajorHead.objects.create(code='G01', name='Test Major')
        minor = MinorHead.objects.create(code='G011', name='Test Minor', major=major)
        
        # Create first GlobalHead with AR code
        gh1 = GlobalHead.objects.create(
            code='TEST001',
            name='Test Head 1',
            minor=minor,
            account_type=AccountType.ASSET,
            system_code=SystemCode.AR
        )
        
        # Try to create another with same system_code - should fail
        with self.assertRaises(Exception):  # IntegrityError
            GlobalHead.objects.create(
                code='TEST002',
                name='Test Head 2',
                minor=minor,
                account_type=AccountType.ASSET,
                system_code=SystemCode.AR
            )
    
    def test_global_head_without_system_code(self):
        """Test that GlobalHead can exist without system_code (optional field)."""
        major = MajorHead.objects.create(code='A03', name='Operating')
        minor = MinorHead.objects.create(code='A039', name='General', major=major)
        
        gh = GlobalHead.objects.create(
            code='A03901',
            name='Stationery',
            minor=minor,
            account_type=AccountType.EXPENDITURE,
            system_code=None  # No system code
        )
        
        self.assertIsNone(gh.system_code)
        self.assertEqual(gh.code, 'A03901')


class AssignSystemCodesCommandTests(TestCase):
    """Test the assign_system_codes management command."""
    
    def test_command_creates_all_system_codes(self):
        """Test that command creates all 9 system code GlobalHeads."""
        out = StringIO()
        call_command('assign_system_codes', stdout=out)
        
        # Check all system codes exist
        for sys_code in [SystemCode.SYS_SUSPENSE, SystemCode.CLEARING_CHQ, 
                        SystemCode.CLEARING_IT, SystemCode.CLEARING_GST,
                        SystemCode.CLEARING_SEC, SystemCode.AP, SystemCode.AR,
                        SystemCode.TAX_IT, SystemCode.TAX_GST]:
            self.assertTrue(
                GlobalHead.objects.filter(system_code=sys_code).exists(),
                f"{sys_code} GlobalHead not created"
            )
        
        output = out.getvalue()
        self.assertIn('Created:', output)
        self.assertIn('SUMMARY:', output)
    
    def test_command_idempotent(self):
        """Test that running command multiple times doesn't duplicate."""
        # Run once
        call_command('assign_system_codes', stdout=StringIO())
        count_first = GlobalHead.objects.filter(system_code__isnull=False).count()
        
        # Run again
        call_command('assign_system_codes', stdout=StringIO())
        count_second = GlobalHead.objects.filter(system_code__isnull=False).count()
        
        self.assertEqual(count_first, count_second, "Command created duplicates")
        self.assertEqual(count_first, 9, "Should have exactly 9 system code heads")
    
    def test_command_updates_existing_untagged_heads(self):
        """Test that command can tag existing GlobalHeads with system codes."""
        # Create GlobalHead without system_code
        major = MajorHead.objects.create(code='G05', name='Suspense & Clearing')
        minor = MinorHead.objects.create(code='G051', name='Suspense', major=major)
        gh = GlobalHead.objects.create(
            code='G05101',
            name='Suspense Account',
            minor=minor,
            account_type=AccountType.LIABILITY,
            system_code=None
        )
        
        self.assertIsNone(gh.system_code)
        
        # Run command
        out = StringIO()
        call_command('assign_system_codes', stdout=out)
        
        gh.refresh_from_db()
        self.assertEqual(gh.system_code, SystemCode.SYS_SUSPENSE)
        self.assertIn('Updated:', out.getvalue())
    
    def test_command_dry_run_mode(self):
        """Test that --dry-run doesn't make changes."""
        initial_count = GlobalHead.objects.count()
        
        out = StringIO()
        call_command('assign_system_codes', '--dry-run', stdout=out)
        
        final_count = GlobalHead.objects.count()
        self.assertEqual(initial_count, final_count, "Dry run should not create records")
        
        output = out.getvalue()
        self.assertIn('DRY RUN', output)
        self.assertIn('No changes were made', output)
    
    def test_command_creates_hierarchy(self):
        """Test that command creates Major/Minor hierarchy if missing."""
        # Ensure clean state
        self.assertEqual(MajorHead.objects.count(), 0)
        self.assertEqual(MinorHead.objects.count(), 0)
        
        call_command('assign_system_codes', stdout=StringIO())
        
        # Check hierarchy created
        self.assertGreater(MajorHead.objects.count(), 0, "Major heads not created")
        self.assertGreater(MinorHead.objects.count(), 0, "Minor heads not created")
        
        # Verify specific hierarchy
        major_g05 = MajorHead.objects.filter(code='G05').first()
        self.assertIsNotNone(major_g05)
        self.assertEqual(major_g05.name, 'Suspense & Clearing')
        
        minor_g051 = MinorHead.objects.filter(code='G051').first()
        self.assertIsNotNone(minor_g051)
        self.assertEqual(minor_g051.major, major_g05)


class SystemCodeWorkflowTests(TestCase):
    """Test system code integration in financial workflows."""
    
    def setUp(self):
        """Set up test data."""
        # Create organization
        self.org = Organization.objects.create(
            name='Test TMA',
            org_type='TMA'
        )
        
        # Create user
        self.user = User.objects.create_user(
            username='test@test.com',
            email='test@test.com',
            password='test123',
            organization=self.org
        )
        
        # Create fiscal year
        self.fy = FiscalYear.objects.create(
            organization=self.org,
            year_name='2025-26',
            start_date='2025-07-01',
            end_date='2026-06-30',
            is_active=True,
            created_by=self.user,
            updated_by=self.user
        )
        
        # Create fund and function
        self.fund = Fund.objects.create(code='GEN', name='General Fund', is_active=True)
        self.function = FunctionCode.objects.create(code='AD', name='Administration', is_active=True)
        
        # Run assign_system_codes to set up system heads
        call_command('assign_system_codes', stdout=StringIO())
        
        # Create BudgetHeads for system codes
        for sys_code in [SystemCode.AP, SystemCode.AR, SystemCode.TAX_IT]:
            gh = GlobalHead.objects.get(system_code=sys_code)
            BudgetHead.objects.create(
                fund=self.fund,
                function=self.function,
                global_head=gh,
                is_active=True,
                budget_control=False,
                posting_allowed=True
            )
    
    def test_ar_account_retrievable(self):
        """Test that AR system account can be retrieved."""
        ar_head = BudgetHead.objects.filter(
            global_head__system_code=SystemCode.AR
        ).first()
        
        self.assertIsNotNone(ar_head, "AR account not found")
        self.assertEqual(ar_head.global_head.system_code, SystemCode.AR)
        self.assertEqual(ar_head.global_head.account_type, AccountType.ASSET)
    
    def test_ap_account_retrievable(self):
        """Test that AP system account can be retrieved."""
        ap_head = BudgetHead.objects.filter(
            global_head__system_code=SystemCode.AP
        ).first()
        
        self.assertIsNotNone(ap_head, "AP account not found")
        self.assertEqual(ap_head.global_head.system_code, SystemCode.AP)
        self.assertEqual(ap_head.global_head.account_type, AccountType.LIABILITY)
    
    def test_tax_accounts_retrievable(self):
        """Test that tax withholding accounts can be retrieved."""
        tax_it = BudgetHead.objects.filter(
            global_head__system_code=SystemCode.TAX_IT
        ).first()
        
        tax_gst = GlobalHead.objects.filter(
            system_code=SystemCode.TAX_GST
        ).first()
        
        self.assertIsNotNone(tax_it, "Income Tax account not found")
        self.assertIsNotNone(tax_gst, "GST account not found")
        self.assertEqual(tax_it.global_head.account_type, AccountType.LIABILITY)
        self.assertEqual(tax_gst.account_type, AccountType.LIABILITY)
    
    def test_clearing_accounts_exist(self):
        """Test that all clearing accounts exist."""
        clearing_codes = [
            SystemCode.CLEARING_CHQ,
            SystemCode.CLEARING_IT,
            SystemCode.CLEARING_GST,
            SystemCode.CLEARING_SEC
        ]
        
        for code in clearing_codes:
            gh = GlobalHead.objects.filter(system_code=code).first()
            self.assertIsNotNone(gh, f"{code} not found")
            self.assertEqual(gh.account_type, AccountType.LIABILITY)
    
    def test_suspense_account_exists(self):
        """Test that suspense account exists."""
        suspense = GlobalHead.objects.filter(
            system_code=SystemCode.SYS_SUSPENSE
        ).first()
        
        self.assertIsNotNone(suspense)
        self.assertEqual(suspense.account_type, AccountType.LIABILITY)
        self.assertIn('Suspense', suspense.name)


class SystemCodeQueryTests(TestCase):
    """Test querying patterns for system codes."""
    
    def setUp(self):
        """Set up test data."""
        call_command('assign_system_codes', stdout=StringIO())
        
        self.fund = Fund.objects.create(code='GEN', name='General', is_active=True)
        self.function = FunctionCode.objects.create(code='AD', name='Admin', is_active=True)
    
    def test_query_budget_head_by_system_code(self):
        """Test querying BudgetHead via global_head__system_code."""
        gh_ar = GlobalHead.objects.get(system_code=SystemCode.AR)
        BudgetHead.objects.create(
            fund=self.fund,
            function=self.function,
            global_head=gh_ar,
            is_active=True
        )
        
        # Query pattern used in models
        ar_head = BudgetHead.objects.filter(
            global_head__system_code=SystemCode.AR
        ).first()
        
        self.assertIsNotNone(ar_head)
        self.assertEqual(ar_head.global_head.code, gh_ar.code)
    
    def test_query_multiple_system_codes(self):
        """Test querying multiple system codes at once."""
        # Create BudgetHeads for multiple system codes
        for sys_code in [SystemCode.AP, SystemCode.AR, SystemCode.TAX_IT]:
            gh = GlobalHead.objects.get(system_code=sys_code)
            BudgetHead.objects.create(
                fund=self.fund,
                function=self.function,
                global_head=gh,
                is_active=True
            )
        
        # Query all system budget heads
        system_heads = BudgetHead.objects.filter(
            global_head__system_code__isnull=False
        )
        
        self.assertEqual(system_heads.count(), 3)
    
    def test_query_by_account_type_and_system_code(self):
        """Test combined filtering by account type and system code."""
        # Create budget heads
        for sys_code in [SystemCode.AP, SystemCode.AR]:
            gh = GlobalHead.objects.get(system_code=sys_code)
            BudgetHead.objects.create(
                fund=self.fund,
                function=self.function,
                global_head=gh,
                is_active=True
            )
        
        # Query liability system heads
        liability_heads = BudgetHead.objects.filter(
            global_head__system_code__isnull=False,
            global_head__account_type=AccountType.LIABILITY
        )
        
        self.assertEqual(liability_heads.count(), 1)  # Only AP
        self.assertEqual(
            liability_heads.first().global_head.system_code,
            SystemCode.AP
        )


class SystemCodeDataIntegrityTests(TestCase):
    """Test data integrity rules for system codes."""
    
    def test_system_code_pifra_codes_follow_convention(self):
        """Test that system code PIFRA codes follow naming conventions."""
        call_command('assign_system_codes', stdout=StringIO())
        
        # Liabilities should start with G or L
        ap_head = GlobalHead.objects.get(system_code=SystemCode.AP)
        self.assertIn(ap_head.code[0], ['G', 'L'])
        
        # Assets should start with A or F
        ar_head = GlobalHead.objects.get(system_code=SystemCode.AR)
        self.assertIn(ar_head.code[0], ['A', 'F'])
    
    def test_system_code_hierarchy_integrity(self):
        """Test that all system code GlobalHeads have proper Major/Minor parents."""
        call_command('assign_system_codes', stdout=StringIO())
        
        system_heads = GlobalHead.objects.filter(system_code__isnull=False)
        
        for gh in system_heads:
            self.assertIsNotNone(gh.minor, f"{gh.code} has no Minor parent")
            self.assertIsNotNone(gh.minor.major, f"{gh.code} has no Major parent")
            
            # Verify code hierarchy
            self.assertTrue(
                gh.code.startswith(gh.minor.code[:3]),
                f"{gh.code} doesn't match Minor {gh.minor.code}"
            )
    
    def test_no_duplicate_pifra_codes(self):
        """Test that PIFRA codes assigned to system heads are unique."""
        call_command('assign_system_codes', stdout=StringIO())
        
        system_heads = GlobalHead.objects.filter(system_code__isnull=False)
        codes = [gh.code for gh in system_heads]
        
        self.assertEqual(len(codes), len(set(codes)), "Duplicate PIFRA codes found")


class SystemCodeMigrationTests(TestCase):
    """Test migration from old BudgetHead.system_code to GlobalHead.system_code."""
    
    def test_no_budget_head_system_code_field(self):
        """Test that BudgetHead.system_code field no longer exists."""
        budget_head_fields = [f.name for f in BudgetHead._meta.get_fields()]
        self.assertNotIn('system_code', budget_head_fields,
                        "BudgetHead.system_code field still exists - should be removed")
    
    def test_global_head_has_system_code_field(self):
        """Test that GlobalHead.system_code field exists."""
        global_head_fields = [f.name for f in GlobalHead._meta.get_fields()]
        self.assertIn('system_code', global_head_fields,
                     "GlobalHead.system_code field missing")


def run_tests():
    """Convenience function to run all system code tests."""
    import sys
    from django.core.management import call_command
    
    # Run tests
    call_command('test', 'apps.finance.tests.test_system_codes', verbosity=2)


if __name__ == '__main__':
    run_tests()
