"""
-------------------------------------------------------------------------
System: KP-CFMS (Computerized Financial Management System)  
Client: Local Government Department, Khyber Pakhtunkhwa
Description: Unit tests for NAM Chart of Accounts hierarchy
             Testing the clean 5-level structure
-------------------------------------------------------------------------
"""

from decimal import Decimal
from django.test import TestCase
from django.core.exceptions import ValidationError

from apps.finance.models import (
    MajorHead, MinorHead, NAMHead, SubHead, BudgetHead,
    Fund, FunctionCode, AccountType
)
from apps.budgeting.models import Department


class NAMHeadTestCase(TestCase):
    """Test NAM Head (Level 4) functionality."""
    
    def setUp(self):
        """Set up test data."""
        # Create hierarchy
        self.major = MajorHead.objects.create(code='A01', name='Employee Related')
        self.minor = MinorHead.objects.create(
            code='A011',
            name='Pay',
            major=self.major
        )
        self.nam_head = NAMHead.objects.create(
            code='A01101',
            name='Basic Pay - Officers',
            minor=self.minor,
            account_type=AccountType.EXPENDITURE,
            scope='UNIVERSAL'
        )
    
    def test_nam_head_creation(self):
        """Test NAM head can be created successfully."""
        self.assertEqual(self.nam_head.code, 'A01101')
        self.assertEqual(self.nam_head.name, 'Basic Pay - Officers')
        self.assertTrue(self.nam_head.allow_direct_posting)
        self.assertFalse(self.nam_head.has_sub_heads)
    
    def test_nam_head_hierarchy_properties(self):
        """Test NAM head hierarchy navigation."""
        self.assertEqual(self.nam_head.major_code, 'A01')
        self.assertEqual(self.nam_head.major_name, 'Employee Related')
        self.assertEqual(self.nam_head.minor.code, 'A011')
    
    def test_nam_head_universal_scope(self):
        """Test universal NAM heads are applicable to all departments."""
        dept = Department.objects.create(name='Health', code='HLT')
        self.assertTrue(self.nam_head.is_applicable_to_department(dept))
        self.assertTrue(self.nam_head.is_applicable_to_function(None))


class SubHeadTestCase(TestCase):
    """Test Sub-Head (Level 5) functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.major = MajorHead.objects.create(code='A12', name='Physical Assets')
        self.minor = MinorHead.objects.create(
            code='A120',
            name='Roads & Bridges',
            major=self.major
        )
        self.nam_head = NAMHead.objects.create(
            code='A12001',
            name='Roads',
            minor=self.minor,
            account_type=AccountType.EXPENDITURE
        )
    
    def test_subhead_creation(self):
        """Test sub-head can be created successfully."""
        sub = SubHead.objects.create(
            nam_head=self.nam_head,
            sub_code='01',
            name='PCC Streets'
        )
        
        self.assertEqual(sub.code, 'A12001-01')
        self.assertEqual(sub.name, 'PCC Streets')
        self.assertTrue(sub.is_active)
    
    def test_subhead_disables_parent_posting(self):
        """Test creating sub-head auto-disables parent NAM direct posting."""
        # Initially, NAM head allows direct posting
        self.assertTrue(self.nam_head.allow_direct_posting)
        
        # Create first sub-head
        SubHead.objects.create(
            nam_head=self.nam_head,
            sub_code='01',
            name='PCC Streets'
        )
        
        # Refresh and check
        self.nam_head.refresh_from_db()
        self.assertFalse(self.nam_head.allow_direct_posting)
    
    def test_multiple_subheads(self):
        """Test multiple sub-heads can be created for same NAM head."""
        SubHead.objects.create(nam_head=self.nam_head, sub_code='01', name='PCC Streets')
        SubHead.objects.create(nam_head=self.nam_head, sub_code='02', name='Shingle Roads')
        SubHead.objects.create(nam_head=self.nam_head, sub_code='03', name='Tough Tiles')
        
        self.assertEqual(self.nam_head.sub_heads.count(), 3)
        self.assertTrue(self.nam_head.has_sub_heads)
    
    def test_subhead_unique_constraint(self):
        """Test sub-code must be unique within NAM head."""
        SubHead.objects.create(nam_head=self.nam_head, sub_code='01', name='First')
        
        with self.assertRaises(Exception):  # Django will raise IntegrityError
            SubHead.objects.create(nam_head=self.nam_head, sub_code='01', name='Duplicate')


class BudgetHeadValidationTestCase(TestCase):
    """Test BudgetHead validation rules."""
    
    def setUp(self):
        """Set up test data."""
        # Create hierarchy
        self.major = MajorHead.objects.create(code='A12', name='Physical Assets')
        self.minor = MinorHead.objects.create(code='A120', name='Roads', major=self.major)
        self.nam_head = NAMHead.objects.create(
            code='A12001',
            name='Roads',
            minor=self.minor,
            account_type=AccountType.EXPENDITURE
        )
        self.sub_head = SubHead.objects.create(
            nam_head=self.nam_head,
            sub_code='01',
            name='PCC Streets'
        )
        
        # Create supporting entities
        self.dept = Department.objects.create(name='Works', code='WRK')
        self.fund = Fund.objects.create(name='General', code='GEN')
        self.function = FunctionCode.objects.create(code='AD', name='Administration')
    
    def test_budget_head_requires_nam_or_sub(self):
        """Test BudgetHead must have either NAM head or Sub-head."""
        head = BudgetHead(
            department=self.dept,
            fund=self.fund,
            function=self.function,
            nam_head=None,
            sub_head=None
        )
        
        with self.assertRaises(ValidationError) as context:
            head.clean()
        
        self.assertIn('Either NAM Head or Sub-Head must be specified', str(context.exception))
    
    def test_budget_head_cannot_have_both(self):
        """Test BudgetHead cannot have both NAM head and Sub-head."""
        head = BudgetHead(
            department=self.dept,
            fund=self.fund,
            function=self.function,
            nam_head=self.nam_head,
            sub_head=self.sub_head
        )
        
        with self.assertRaises(ValidationError) as context:
            head.clean()
        
        self.assertIn('Cannot specify both', str(context.exception))
    
    def test_budget_head_subhead_disables_nam_posting(self):
        """Test cannot create BudgetHead with NAM that has sub-heads."""
        # NAM head now has sub-heads (disabled posting)
        self.nam_head.refresh_from_db()
        self.assertFalse(self.nam_head.allow_direct_posting)
        
        head = BudgetHead(
            department=self.dept,
            fund=self.fund,
            function=self.function,
            nam_head=self.nam_head
        )
        
        with self.assertRaises(ValidationError) as context:
            head.clean()
        
        self.assertIn('has sub-heads', str(context.exception))
    
    def test_budget_head_with_nam_success(self):
        """Test BudgetHead can be created with NAM head (no sub-heads)."""
        # Create new NAM without sub-heads
        nam_clean = NAMHead.objects.create(
            code='A01101',
            name='Basic Pay',
            minor=self.minor,
            account_type=AccountType.EXPENDITURE
        )
        
        head = BudgetHead(
            department=self.dept,
            fund=self.fund,
            function=self.function,
            nam_head=nam_clean
        )
        
        # Should not raise
        head.clean()
        head.save()
        
        self.assertEqual(head.code, 'A01101')
        self.assertEqual(head.level, 4)
    
    def test_budget_head_with_subhead_success(self):
        """Test BudgetHead can be created with Sub-head."""
        head = BudgetHead(
            department=self.dept,
            fund=self.fund,
            function=self.function,
            sub_head=self.sub_head
        )
        
        # Should not raise
        head.clean()
        head.save()
        
        self.assertEqual(head.code, 'A12001-01')
        self.assertEqual(head.level, 5)
        self.assertTrue(head.is_sub_head())


class BudgetHeadPropertiesTestCase(TestCase):
    """Test BudgetHead proxy properties."""
    
    def setUp(self):
        """Set up test data."""
        self.major = MajorHead.objects.create(code='A01', name='Employee Related')
        self.minor = MinorHead.objects.create(code='A011', name='Pay', major=self.major)
        self.nam_head = NAMHead.objects.create(
            code='A01101',
            name='Basic Pay - Officers',
            minor=self.minor,
            account_type=AccountType.EXPENDITURE
        )
        self.sub_head = SubHead.objects.create(
            nam_head=self.nam_head,
            sub_code='01',
            name='Grade 17-18'
        )
        
        self.dept = Department.objects.create(name='Admin', code='ADM')
        self.fund = Fund.objects.create(name='General', code='GEN')
        self.function = FunctionCode.objects.create(code='AD', name='Administration')
    
    def test_properties_with_nam_head(self):
        """Test properties when using NAM head."""
        head = BudgetHead.objects.create(
            department=self.dept,
            fund=self.fund,
            function=self.function,
            nam_head=self.nam_head
        )
        
        self.assertEqual(head.code, 'A01101')
        self.assertEqual(head.name, 'Basic Pay - Officers')
        self.assertEqual(head.level, 4)
        self.assertEqual(head.account_type, AccountType.EXPENDITURE)
        self.assertEqual(head.major_code, 'A01')
        self.assertEqual(head.minor_code, 'A011')
        self.assertFalse(head.is_sub_head())
    
    def test_properties_with_subhead(self):
        """Test properties when using Sub-head."""
        head = BudgetHead.objects.create(
            department=self.dept,
            fund=self.fund,
            function=self.function,
            sub_head=self.sub_head
        )
        
        self.assertEqual(head.code, 'A01101-01')
        self.assertEqual(head.name, 'Grade 17-18')
        self.assertEqual(head.level, 5)
        self.assertEqual(head.account_type, AccountType.EXPENDITURE)
        self.assertEqual(head.major_code, 'A01')
        self.assertEqual(head.minor_code, 'A011')
        self.assertTrue(head.is_sub_head())
    
    def test_get_full_code(self):
        """Test full code generation."""
        head = BudgetHead.objects.create(
            department=self.dept,
            fund=self.fund,
            function=self.function,
            nam_head=self.nam_head
        )
        
        full_code = head.get_full_code()
        self.assertIn('FGEN', full_code)
        self.assertIn('ADM', full_code)
        self.assertIn('AD', full_code)
        self.assertIn('A01101', full_code)
    
    def test_hierarchy_path(self):
        """Test hierarchy path generation."""
        head = BudgetHead.objects.create(
            department=self.dept,
            fund=self.fund,
            function=self.function,
            sub_head=self.sub_head
        )
        
        path = head.get_hierarchy_path()
        self.assertIn('A01', path)
        self.assertIn('A011', path)
        self.assertIn('A01101', path)
        self.assertIn('01', path)
        self.assertIn('→', path)


class BudgetHeadManagerTestCase(TestCase):
    """Test BudgetHeadManager custom query methods."""
    
    def setUp(self):
        """Set up test data."""
        # Create hierarchy
        major = MajorHead.objects.create(code='A03', name='Operating')
        minor = MinorHead.objects.create(code='A033', name='Utilities', major=major)
        
        self.elec = NAMHead.objects.create(
            code='A03303',
            name='Electricity',
            minor=minor,
            account_type=AccountType.EXPENDITURE
        )
        self.water = NAMHead.objects.create(
            code='A03304',
            name='Water',
            minor=minor,
            account_type=AccountType.EXPENDITURE
        )
        
        # Create departments
        self.health = Department.objects.create(name='Health', code='HLT')
        self.admin = Department.objects.create(name='Admin', code='ADM')
        
        # Create functions
        self.ad_func = FunctionCode.objects.create(code='AD', name='Administration')
        self.ph_func = FunctionCode.objects.create(code='PH', name='Public Health')
        
        # Create fund
        self.fund = Fund.objects.create(name='General', code='GEN')
        
        # Create budget heads
        BudgetHead.objects.create(
            department=self.health,
            fund=self.fund,
            function=self.ph_func,
            nam_head=self.elec,
            is_active=True,
            posting_allowed=True
        )
        BudgetHead.objects.create(
            department=self.admin,
            fund=self.fund,
            function=self.ad_func,
            nam_head=self.water,
            is_active=True,
            posting_allowed=True
        )
    
    def test_for_department_and_function(self):
        """Test filtering by department and function."""
        heads = BudgetHead.objects.for_department_and_function(
            self.health,
            self.ph_func
        )
        
        self.assertEqual(heads.count(), 1)
        self.assertEqual(heads.first().nam_head.code, 'A03303')
    
    def test_for_transaction_entry_filters_correctly(self):
        """Test transaction entry method returns filtered queryset."""
        heads = BudgetHead.objects.for_transaction_entry(
            department=self.admin,
            function=self.ad_func
        )
        
        self.assertEqual(heads.count(), 1)
        head = heads.first()
        self.assertEqual(head.department, self.admin)
        self.assertEqual(head.function, self.ad_func)
    
    def test_inactive_heads_excluded(self):
        """Test inactive heads are excluded from queries."""
        # Deactivate one head
        BudgetHead.objects.filter(nam_head=self.elec).update(is_active=False)
        
        active_heads = BudgetHead.objects.active()
        self.assertEqual(active_heads.count(), 1)


class HierarchyIntegrationTestCase(TestCase):
    """Integration tests for the complete 5-level hierarchy."""
    
    def test_complete_hierarchy_creation(self):
        """Test creating complete hierarchy from Level 1 to Level 5."""
        # Level 1 & 2: Major Head
        major = MajorHead.objects.create(code='A12', name='Physical Assets')
        
        # Level 3: Minor Head
        minor = MinorHead.objects.create(code='A120', name='Roads', major=major)
        
        # Level 4: NAM Head
        nam = NAMHead.objects.create(
            code='A12001',
            name='Roads',
            minor=minor,
            account_type=AccountType.EXPENDITURE
        )
        
        # Level 5: Sub-Heads
        sub1 = SubHead.objects.create(nam_head=nam, sub_code='01', name='PCC Streets')
        sub2 = SubHead.objects.create(nam_head=nam, sub_code='02', name='Shingle Roads')
        
        # Verify hierarchy
        self.assertEqual(sub1.nam_head.minor.major.code, 'A12')
        self.assertEqual(sub2.code, 'A12001-02')
        
        # Verify NAM posting disabled
        nam.refresh_from_db()
        self.assertFalse(nam.allow_direct_posting)
        self.assertEqual(nam.sub_heads.count(), 2)
    
    def test_budget_head_queries_with_hierarchy(self):
        """Test BudgetHead manager respects hierarchy."""
        # Setup complete hierarchy
        major = MajorHead.objects.create(code='A01', name='Employee')
        minor = MinorHead.objects.create(code='A011', name='Pay', major=major)
        nam = NAMHead.objects.create(
            code='A01101',
            name='Basic Pay',
            minor=minor,
            account_type=AccountType.EXPENDITURE
        )
        sub = SubHead.objects.create(nam_head=nam, sub_code='01', name='Officers')
        
        dept = Department.objects.create(name='Admin', code='ADM')
        fund = Fund.objects.create(name='General', code='GEN')
        func = FunctionCode.objects.create(code='AD', name='Administration')
        
        # Create budget head with sub-head
        head = BudgetHead.objects.create(
            department=dept,
            fund=fund,
            function=func,
            sub_head=sub
        )
        
        # Query and verify
        heads = BudgetHead.objects.for_department_and_function(dept, func)
        self.assertEqual(heads.count(), 1)
        
        retrieved = heads.first()
        self.assertEqual(retrieved.level, 5)
        self.assertEqual(retrieved.code, 'A01101-01')
        self.assertEqual(retrieved.major_code, 'A01')
