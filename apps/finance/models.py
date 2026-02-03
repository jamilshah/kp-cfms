"""
-------------------------------------------------------------------------
System: KP-CFMS (Computerized Financial Management System)
Client: Local Government Department, Khyber Pakhtunkhwa
Team Lead: Jamil Shah
Developers: Ali Asghar, Akhtar Munir and Zarif Khan
Description: Finance models including BudgetHead (Chart of Accounts)
             following the PIFRA/NAM hierarchy structure.
-------------------------------------------------------------------------
"""
import re
from decimal import Decimal
from typing import Optional
from django.db import models
from django.core.validators import RegexValidator, MinValueValidator
from django.utils.translation import gettext_lazy as _

from apps.core.mixins import AuditLogMixin, StatusMixin, UUIDMixin, TimeStampedMixin, TenantAwareMixin


class AccountType(models.TextChoices):
    """
    Account type classification based on NAM structure.
    """
    
    EXPENDITURE = 'EXP', _('Expenditure')
    REVENUE = 'REV', _('Revenue')
    LIABILITY = 'LIA', _('Liability')
    ASSET = 'AST', _('Asset')
    EQUITY = 'EQT', _('Equity')


class FundType(models.TextChoices):
    """
    Fund type classification for reporting.
    
    PUGF: Provincial Urban General Fund (for Provincial cadre officers)
    NON_PUGF: Local Council Staff and operational expenses
    DEVELOPMENT: Capital/ADP projects
    PENSION: Pension fund
    """
    
    PUGF = 'PUGF', _('PUGF (Provincial)')
    NON_PUGF = 'NPUGF', _('Non-PUGF (Local)')
    DEVELOPMENT = 'DEV', _('Development')
    PENSION = 'PEN', _('Pension')
    OTHER = 'OTH', _('Other')


class FunctionCode(UUIDMixin):
    """
    Functional classification of budget heads.
    
    Examples: AD (Administration), WS (Water Supply), SW (Sanitation).
    """
    
    code = models.CharField(
        max_length=10,
        unique=True,
        verbose_name=_('Function Code'),
        help_text=_('Short code for the function (e.g., AD, WS, SW).')
    )
    name = models.CharField(
        max_length=100,
        verbose_name=_('Function Name'),
        help_text=_('Full name of the function (e.g., Administration).')
    )
    description = models.TextField(
        blank=True,
        verbose_name=_('Description')
    )
    usage_notes = models.TextField(
        blank=True,
        verbose_name=_('Usage Notes'),
        help_text=_('Guidelines on what expenses should be recorded under this function (AGP/PIFRA compliance)')
    )
    is_default = models.BooleanField(
        default=False,
        verbose_name=_('Is Default'),
        help_text=_('Mark as default function for its department')
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_('Is Active')
    )
    
    class Meta:
        verbose_name = _('Function Code')
        verbose_name_plural = _('Function Codes')
        ordering = ['code']
    
    def __str__(self) -> str:
        return f"{self.code} - {self.name}"


# ============================================================================
# MASTER DATA LAYER - PIFRA Chart of Accounts Hierarchy
# ============================================================================

class MajorHead(TimeStampedMixin):
    """
    Major Object classification (Level 1 of PIFRA hierarchy).
    
    Examples: A01 (Employee Related), A03 (Operating Expenses), C01 (Tax Revenue)
    
    This is Master Data - managed at provincial level, read-only for TMAs.
    """
    
    code = models.CharField(
        max_length=10,
        unique=True,
        verbose_name=_('Major Code'),
        help_text=_('Major object code (e.g., A01, A03, C01).')
    )
    name = models.CharField(
        max_length=255,
        verbose_name=_('Major Name'),
        help_text=_('Description of major object (e.g., Employee Related Expenses).')
    )
    
    class Meta:
        verbose_name = _('Major Head')
        verbose_name_plural = _('Major Heads')
        ordering = ['code']
    
    def __str__(self) -> str:
        return f"{self.code} - {self.name}"


class MinorHead(TimeStampedMixin):
    """
    Minor Object classification (Level 2 of PIFRA hierarchy).
    
    Examples: A011 (Pay), A012 (Allowances), A035 (Operating Leases)
    
    This is Master Data - managed at provincial level, read-only for TMAs.
    """
    
    code = models.CharField(
        max_length=10,
        unique=True,
        verbose_name=_('Minor Code'),
        help_text=_('Minor object code (e.g., A011, A012).')
    )
    name = models.CharField(
        max_length=255,
        verbose_name=_('Minor Name')
    )
    major = models.ForeignKey(
        MajorHead,
        on_delete=models.PROTECT,
        related_name='minor_heads',
        verbose_name=_('Major Head')
    )
    
    class Meta:
        verbose_name = _('Minor Head')
        verbose_name_plural = _('Minor Heads')
        ordering = ['code']
    
    def __str__(self) -> str:
        return f"{self.code} - {self.name}"


class SystemCode(models.TextChoices):
    """
    System-controlled account codes for automated GL posting.
    
    These accounts are used by the system for specific workflows:
    - Suspense: Temporary holding for unclassified transactions
    - Clearing: Intermediate accounts for reconciliation
    - AP/AR: Accounts Payable/Receivable for accrual accounting
    - Tax: Tax withholding and remittance accounts
    """
    
    # Suspense & Clearing Accounts
    SYS_SUSPENSE = 'SYS_SUSPENSE', _('Suspense Account')
    CLEARING_CHQ = 'CLEARING_CHQ', _('Cheque Clearing')
    CLEARING_IT = 'CLEARING_IT', _('Income Tax Withheld')
    CLEARING_GST = 'CLEARING_GST', _('Sales Tax Withheld')
    CLEARING_SEC = 'CLEARING_SEC', _('Security/Retention Money')
    
    # Accounts Payable & Receivable
    AP = 'AP', _('Accounts Payable')
    AR = 'AR', _('Accounts Receivable')
    
    # Tax Accounts (for expenditure workflow)
    TAX_IT = 'TAX_IT', _('Income Tax Payable')
    TAX_GST = 'TAX_GST', _('GST/Sales Tax Payable')


class GlobalHead(TimeStampedMixin):
    """
    Detailed Object classification (Level 3 of PIFRA hierarchy).
    
    Examples: A01101 (Basic Pay - Officers), A01151 (Basic Pay - Other Staff)
    
    This is Master Data - the provincial standard Chart of Accounts.
    TMAs cannot modify this, but link to it via BudgetHead.
    
    Attributes:
        code: Detailed object code (e.g., A01101)
        name: Description
        minor: Parent minor head
        account_type: Expenditure, Revenue, Asset, Liability
        system_code: Optional system code for automated workflows
    """
    
    code = models.CharField(
        max_length=20,
        unique=True,
        verbose_name=_('Object Code'),
        help_text=_('Detailed object code (e.g., A01101).')
    )
    name = models.CharField(
        max_length=255,
        verbose_name=_('Object Name')
    )
    minor = models.ForeignKey(
        MinorHead,
        on_delete=models.PROTECT,
        related_name='global_heads',
        verbose_name=_('Minor Head')
    )
    account_type = models.CharField(
        max_length=3,
        choices=AccountType.choices,
        default=AccountType.EXPENDITURE,
        verbose_name=_('Account Type')
    )
    system_code = models.CharField(
        max_length=20,
        choices=SystemCode.choices,
        null=True,
        blank=True,
        unique=True,
        verbose_name=_('System Code'),
        help_text=_('System code for automated workflows (Suspense, Clearing, etc.).')
    )
    
    # Department-based access control
    scope = models.CharField(
        max_length=20,
        choices=[
            ('UNIVERSAL', _('Universal - All Departments')),
            ('DEPARTMENTAL', _('Department-Specific'))
        ],
        default='UNIVERSAL',
        verbose_name=_('Scope'),
        help_text=_('Universal heads appear for all departments. Departmental heads only for selected departments.')
    )
    applicable_departments = models.ManyToManyField(
        'budgeting.Department',
        blank=True,
        related_name='applicable_global_heads',
        verbose_name=_('Applicable Departments'),
        help_text=_('Select departments where this head is relevant. Leave empty for Universal scope.')
    )
    
    class Meta:
        verbose_name = _('Global Head')
        verbose_name_plural = _('Global Heads')
        ordering = ['code']
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['account_type']),
        ]
    
    def __str__(self) -> str:
        return f"{self.code} - {self.name}"
    
    @property
    def is_officer_related(self) -> bool:
        """
        Determine if this is an officer-related salary head.
        
        Logic:
        - Must start with A011 (Salary heads)
        - Last two digits must be between 01 and 50 (Officers range)
        
        Examples:
        - A01101 -> True (Basic Pay - Officers)
        - A01110 -> True (Current/Additional Charge Pay - Officers)
        - A01151 -> False (Basic Pay - Other Staff)
        """
        if not self.code.startswith('A011'):
            return False
        
        try:
            # Extract last two digits
            last_two = int(self.code[-2:])
            return 1 <= last_two <= 50
        except (ValueError, IndexError):
            return False
    
    @property
    def major_code(self) -> str:
        """Get the major code via the hierarchy."""
        return self.minor.major.code
    
    def is_applicable_to_department(self, department) -> bool:
        """
        Check if this GlobalHead is applicable to the given department.
        
        Args:
            department: Department instance or None
            
        Returns:
            True if applicable, False otherwise
        """
        if self.scope == 'UNIVERSAL':
            return True
        
        if not department:
            return False
        
        return self.applicable_departments.filter(pk=department.pk).exists()
    
    def get_applicable_departments_display(self) -> str:
        """Get comma-separated list of applicable department names."""
        if self.scope == 'UNIVERSAL':
            return 'All Departments'
        
        dept_names = list(self.applicable_departments.values_list('name', flat=True))
        return ', '.join(dept_names) if dept_names else 'None'
    
    @property
    def major_name(self) -> str:
        """Get the major name via the hierarchy."""
        return self.minor.major.name


# ============================================================================
# TRANSACTIONAL LAYER - Fund-Specific Budget Heads
# ============================================================================

class HeadType(models.TextChoices):
    """
    Type classification for BudgetHead entries.
    
    REGULAR: Standard PIFRA object code (sub_code='00').
    SUB_HEAD: Local sub-division of a generic object (sub_code='01'-'99').
    """
    
    REGULAR = 'REGULAR', _('Regular Head')
    SUB_HEAD = 'SUB_HEAD', _('Local Sub-Head')


class BudgetHead(AuditLogMixin, StatusMixin):
    """
    Transactional Budget Head - Multi-dimensional matrix.
    
    Structure: Fund + Function + Object (GlobalHead) + Sub-Code
    
    This represents the active Chart of Accounts for a specific Fund
    with functional context. Supports local sub-heads for granularity.
    
    Examples:
        - Standard: GEN + AD + A03303 + 00 -> Electricity (Admin)
        - Sub-Head: GEN + AD + C03880 + 01 -> Rent of Shops (sub of Other Revenue)
    
    Attributes:
        fund: The fund this budget head belongs to
        function: Functional classification (mandatory)
        global_head: Link to the master GlobalHead (PIFRA Object)
        sub_code: Local sub-division code ('00' for regular, '01'-'99' for sub-heads)
        head_type: REGULAR or SUB_HEAD
        local_description: Custom name for sub-heads
    """
    
    fund = models.ForeignKey(
        'finance.Fund',
        on_delete=models.PROTECT,
        related_name='budget_heads',
        verbose_name=_('Fund')
    )
    function = models.ForeignKey(
        FunctionCode,
        on_delete=models.PROTECT,
        related_name='budget_heads',
        verbose_name=_('Function'),
        help_text=_('Functional classification (e.g., AD for Admin, WS for Water Supply).')
    )
    global_head = models.ForeignKey(
        GlobalHead,
        on_delete=models.PROTECT,
        related_name='budget_heads',
        verbose_name=_('Global Head'),
        help_text=_('PIFRA Object code from master chart.')
    )
    sub_code = models.CharField(
        max_length=5,
        default='00',
        verbose_name=_('Sub-Code'),
        help_text=_("'00' for regular heads, '01'-'99' for local sub-divisions.")
    )
    head_type = models.CharField(
        max_length=10,
        choices=HeadType.choices,
        default=HeadType.REGULAR,
        verbose_name=_('Head Type'),
        help_text=_('REGULAR for standard objects, SUB_HEAD for local breakdowns.')
    )
    local_description = models.CharField(
        max_length=255,
        blank=True,
        default='',
        verbose_name=_('Local Description'),
        help_text=_('Custom name for sub-heads (e.g., "Rent of Shops", "Annual Sports Festival").')
    )
    current_budget = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name=_('Current Budget'),
        help_text=_('Current budget allocation for this head.')
    )
    budget_control = models.BooleanField(
        default=True,
        verbose_name=_('Budget Control'),
        help_text=_('Whether hard budget limits are enforced.')
    )
    project_required = models.BooleanField(
        default=False,
        verbose_name=_('Project Required'),
        help_text=_('Whether a project code is required for transactions.')
    )
    posting_allowed = models.BooleanField(
        default=True,
        verbose_name=_('Posting Allowed'),
        help_text=_('Whether transactions can be posted to this head.')
    )
    
    class Meta:
        verbose_name = _('Budget Head')
        verbose_name_plural = _('Budget Heads')
        # Multi-dimensional uniqueness: Fund + Function + Object + Sub-Code
        unique_together = [['fund', 'function', 'global_head', 'sub_code']]
        ordering = ['fund', 'function__code', 'global_head__code', 'sub_code']
        indexes = [
            models.Index(fields=['fund', 'global_head']),
            models.Index(fields=['function']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self) -> str:
        """
        Dynamic string representation with clear function context.
        
        Case A (Regular - sub_code='00'):
            Format: "[Function Name] - [Object Name] ([Object Code])"
            Example: "Administration - Electricity (A03303)"
        
        Case B (Sub-Head - sub_code!='00'):
            Format: "[Function Name] - [Local Description] ([Object Code]-[Sub Code])"
            Example: "Infrastructure - Rent of Shops (C03880-01)"
        """
        func_name = self.function.name if self.function else 'Unknown Function'
        
        if self.sub_code != '00' and self.local_description:
            # Sub-Head format with function name
            return f"{func_name} - {self.local_description} ({self.global_head.code}-{self.sub_code})"
        else:
            # Regular format with function name
            return f"{func_name} - {self.global_head.name} ({self.global_head.code})"
    
    # Proxy properties for template compatibility
    @property
    def code(self) -> str:
        """Proxy to global_head.code, with sub_code suffix if applicable."""
        if self.sub_code != '00':
            return f"{self.global_head.code}-{self.sub_code}"
        return self.global_head.code
    
    @property
    def name(self) -> str:
        """Proxy to local_description or global_head.name."""
        if self.local_description:
            return self.local_description
        return self.global_head.name
    
    @property
    def is_officer(self) -> bool:
        """Proxy to global_head.is_officer_related"""
        return self.global_head.is_officer_related
    
    @property
    def account_type(self) -> str:
        """Proxy to global_head.account_type"""
        return self.global_head.account_type
    
    @property
    def major_code(self) -> str:
        """Proxy to global_head.major_code"""
        return self.global_head.major_code
    
    @property
    def minor_code(self) -> str:
        """Proxy to global_head.minor.code"""
        return self.global_head.minor.code
    
    def get_full_code(self) -> str:
        """Return the complete NAM code path including sub-code."""
        func_code = self.function.code if self.function else 'XX'
        base = f"F{self.fund.code}-{func_code}-{self.global_head.code}"
        if self.sub_code != '00':
            return f"{base}-{self.sub_code}"
        return base
    
    def is_salary_head(self) -> bool:
        """Check if this is a salary-related budget head (A01*)."""
        return self.global_head.code.startswith('A01')
    
    def is_development_head(self) -> bool:
        """Check if this is a development budget head."""
        return self.fund.code == Fund.CODE_DEVELOPMENT
    
    def is_sub_head(self) -> bool:
        """Check if this is a local sub-head."""
        return self.head_type == HeadType.SUB_HEAD or self.sub_code != '00'


class Fund(TimeStampedMixin):
    """
    Fund classification for segregating financial resources.
    
    Funds allow separation of resources for different purposes:
    - General Fund: Current/Operating expenses
    - Development Fund: Capital/ADP projects
    - Pension Fund: Pension payments
    
    Attributes:
        name: Fund name (e.g., "General", "Development", "Pension")
        code: Short code (e.g., "GEN", "DEV", "PEN")
        description: Detailed description of fund purpose
        is_active: Whether fund is currently active
    """
    
    # Standard System Fund Codes
    CODE_GENERAL = 'GEN'
    CODE_DEVELOPMENT = 'DEV'
    CODE_PENSION = 'PEN'

    name = models.CharField(
        max_length=100,
        unique=True,
        verbose_name=_('Fund Name'),
        help_text=_('Name of the fund (e.g., "General", "Development", "Pension").')
    )
    code = models.CharField(
        max_length=10,
        unique=True,
        verbose_name=_('Fund Code'),
        help_text=_('Short code for the fund (e.g., "GEN", "DEV", "PEN").')
    )
    description = models.TextField(
        blank=True,
        verbose_name=_('Description'),
        help_text=_('Detailed description of fund purpose.')
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_('Is Active')
    )
    
    class Meta:
        verbose_name = _('Fund')
        verbose_name_plural = _('Funds')
        ordering = ['code']
    
    def __str__(self) -> str:
        return f"{self.code} - {self.name}"


class VoucherType(models.TextChoices):
    """
    Types of vouchers in the accounting system.
    """
    JOURNAL = 'JV', _('Journal Voucher')
    PAYMENT = 'PV', _('Payment Voucher')
    RECEIPT = 'RV', _('Receipt Voucher')


class Voucher(AuditLogMixin, TenantAwareMixin):
    """
    Voucher header for double-entry transactions.
    
    A voucher contains multiple JournalEntry lines (debits and credits).
    Can only be posted if Sum(Debit) == Sum(Credit).
    
    Attributes:
        organization: The TMA/Organization (from TenantAwareMixin)
        voucher_no: Unique voucher number within fiscal year
        fiscal_year: The fiscal year this voucher belongs to
        date: Transaction date
        voucher_type: Type of voucher (Journal, Payment, Receipt)
        fund: Fund classification
        description: Narration/explanation of transaction
        is_posted: Whether voucher has been posted to GL
        posted_at: Timestamp when voucher was posted
        posted_by: User who posted the voucher
    """
    
    voucher_no = models.CharField(
        max_length=50,
        verbose_name=_('Voucher Number'),
        help_text=_('Unique voucher number (e.g., "JV-2026-001").')
    )
    fiscal_year = models.ForeignKey(
        'budgeting.FiscalYear',
        on_delete=models.PROTECT,
        related_name='vouchers',
        verbose_name=_('Fiscal Year')
    )
    date = models.DateField(
        verbose_name=_('Transaction Date'),
        help_text=_('Date of the transaction.')
    )
    voucher_type = models.CharField(
        max_length=2,
        choices=VoucherType.choices,
        default=VoucherType.JOURNAL,
        verbose_name=_('Voucher Type')
    )
    fund = models.ForeignKey(
        Fund,
        on_delete=models.PROTECT,
        related_name='vouchers',
        verbose_name=_('Fund'),
        help_text=_('Fund classification for this transaction.')
    )
    payee = models.CharField(
        max_length=200,
        blank=True,
        verbose_name=_('Payee'),
        help_text=_('Name of payee or party (optional).')
    )
    reference_no = models.CharField(
        max_length=50,
        blank=True,
        verbose_name=_('Reference No'),
        help_text=_('External reference number (optional).')
    )
    description = models.TextField(
        verbose_name=_('Description'),
        help_text=_('Narration/explanation of the transaction.')
    )
    is_posted = models.BooleanField(
        default=False,
        verbose_name=_('Is Posted'),
        help_text=_('Whether this voucher has been posted to the General Ledger.')
    )
    posted_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Posted At')
    )
    posted_by = models.ForeignKey(
        'users.CustomUser',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='posted_vouchers',
        verbose_name=_('Posted By')
    )
    
    class Meta:
        verbose_name = _('Voucher')
        verbose_name_plural = _('Vouchers')
        ordering = ['-date', '-voucher_no']
        unique_together = ['organization', 'fiscal_year', 'voucher_no']
        indexes = [
            models.Index(fields=['organization', 'fiscal_year']),
            models.Index(fields=['date']),
            models.Index(fields=['is_posted']),
        ]
    
    def __str__(self) -> str:
        return f"{self.voucher_no} - {self.date}"
    
    def get_total_debit(self) -> Decimal:
        """Calculate total debit amount from all journal entries."""
        from django.db.models import Sum
        result = self.entries.aggregate(total=Sum('debit'))
        return result['total'] or Decimal('0.00')
    
    def get_total_credit(self) -> Decimal:
        """Calculate total credit amount from all journal entries."""
        from django.db.models import Sum
        result = self.entries.aggregate(total=Sum('credit'))
        return result['total'] or Decimal('0.00')
    
    def is_balanced(self) -> bool:
        """Check if voucher is balanced (debit == credit)."""
        total_debit = self.get_total_debit()
        total_credit = self.get_total_credit()
        return total_debit == total_credit and total_debit > Decimal('0.00')
    
    def can_post(self) -> bool:
        """Check if voucher can be posted."""
        return not self.is_posted and self.is_balanced()
    
    def post_voucher(self, user) -> None:
        """
        Post the voucher to the General Ledger.
        
        Args:
            user: The user posting the voucher.
            
        Raises:
            ValidationError: If voucher is not balanced or already posted.
        """
        from django.core.exceptions import ValidationError
        from django.utils import timezone
        
        if self.is_posted:
            raise ValidationError(_('Voucher is already posted.'))
        
        if not self.is_balanced():
            raise ValidationError(
                _('Voucher is not balanced. Sum(Debit) must equal Sum(Credit). '
                  f'Debit: {self.get_total_debit()}, Credit: {self.get_total_credit()}')
            )
        
        self.is_posted = True
        self.posted_at = timezone.now()
        self.posted_by = user
        self.save(update_fields=['is_posted', 'posted_at', 'posted_by', 'updated_at'])
    
    def unpost_voucher(self) -> None:
        """
        Unpost the voucher (reverse posting).
        
        Raises:
            ValidationError: If voucher is not posted.
        """
        from django.core.exceptions import ValidationError
        
        if not self.is_posted:
            raise ValidationError(_('Voucher is not posted.'))
        
        self.is_posted = False
        self.posted_at = None
        self.posted_by = None
        self.save(update_fields=['is_posted', 'posted_at', 'posted_by', 'updated_at'])


class JournalEntry(TimeStampedMixin):
    """
    Individual journal entry line (debit or credit).
    
    Each line posts to a BudgetHead (GL account).
    Either debit or credit must be > 0, but not both.
    
    Attributes:
        voucher: Parent voucher
        budget_head: GL account (BudgetHead)
        description: Line description
        debit: Debit amount (0 if credit entry)
        credit: Credit amount (0 if debit entry)
    """
    
    voucher = models.ForeignKey(
        Voucher,
        on_delete=models.CASCADE,
        related_name='entries',
        verbose_name=_('Voucher')
    )
    budget_head = models.ForeignKey(
        BudgetHead,
        on_delete=models.PROTECT,
        related_name='journal_entries',
        verbose_name=_('Budget Head'),
        help_text=_('GL account to post to.')
    )
    description = models.CharField(
        max_length=255,
        verbose_name=_('Description'),
        help_text=_('Description of this journal entry line.')
    )
    debit = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name=_('Debit'),
        help_text=_('Debit amount (leave 0 for credit entries).')
    )
    credit = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name=_('Credit'),
        help_text=_('Credit amount (leave 0 for debit entries).')
    )
    
    # Bank Reconciliation fields
    instrument_no = models.CharField(
        max_length=50,
        blank=True,
        db_index=True,
        verbose_name=_('Instrument No'),
        help_text=_('Cheque number or transaction reference for bank reconciliation.')
    )
    is_reconciled = models.BooleanField(
        default=False,
        verbose_name=_('Is Reconciled'),
        help_text=_('Whether this entry has been reconciled with bank statement.')
    )
    reconciled_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_('Reconciled Date'),
        help_text=_('Date when this entry was reconciled.')
    )
    
    class Meta:
        verbose_name = _('Journal Entry')
        verbose_name_plural = _('Journal Entries')
        ordering = ['voucher', 'id']
        indexes = [
            models.Index(fields=['voucher']),
            models.Index(fields=['budget_head']),
            models.Index(fields=['is_reconciled']),
            models.Index(fields=['instrument_no']),
        ]
    
    def __str__(self) -> str:
        amount = self.debit if self.debit > 0 else self.credit
        entry_type = 'Dr' if self.debit > 0 else 'Cr'
        return f"{self.budget_head.code} - {entry_type} {amount}"
    
    def clean(self) -> None:
        """Validate that either debit or credit is set, but not both."""
        from django.core.exceptions import ValidationError
        
        if self.debit > 0 and self.credit > 0:
            raise ValidationError(
                _('A journal entry cannot have both debit and credit amounts. '
                  'Please set only one.')
            )
        
        if self.debit == 0 and self.credit == 0:
            raise ValidationError(
                _('A journal entry must have either a debit or credit amount.')
            )
    
    def save(self, *args, **kwargs) -> None:
        """Override save to run validation."""
        self.clean()
        super().save(*args, **kwargs)


class LeafStatus(models.TextChoices):
    """
    Status choices for ChequeLeaf.
    """
    AVAILABLE = 'AVAILABLE', _('Available')
    ISSUED = 'ISSUED', _('Issued')
    CANCELLED = 'CANCELLED', _('Cancelled')
    DAMAGED = 'DAMAGED', _('Damaged')


class ChequeBook(AuditLogMixin, StatusMixin):
    """
    Cheque Book linked to a Bank Account.
    
    Tracks physical cheque books received from the bank.
    On creation, automatically generates ChequeLeaf records.
    
    Attributes:
        bank_account: The bank account this book belongs to
        book_no: Unique book identifier (e.g., "BK-2025-01")
        prefix: Leaf number prefix (e.g., "00" or "CHQ")
        start_serial: Starting serial number (e.g., 1001)
        end_serial: Ending serial number (e.g., 1050)
        issue_date: Date the book was received from bank
        is_active: Whether the book is currently in use
    """
    
    bank_account = models.ForeignKey(
        'core.BankAccount',
        on_delete=models.PROTECT,
        related_name='cheque_books',
        verbose_name=_('Bank Account'),
        help_text=_('Bank account this cheque book belongs to.')
    )
    book_no = models.CharField(
        max_length=50,
        verbose_name=_('Book Number'),
        help_text=_('Unique cheque book identifier (e.g., BK-2025-01).')
    )
    prefix = models.CharField(
        max_length=10,
        blank=True,
        default='',
        verbose_name=_('Prefix'),
        help_text=_('Prefix for leaf numbers (e.g., "00", "CHQ").')
    )
    start_serial = models.PositiveIntegerField(
        verbose_name=_('Start Serial'),
        help_text=_('Starting serial number (e.g., 1001).')
    )
    end_serial = models.PositiveIntegerField(
        verbose_name=_('End Serial'),
        help_text=_('Ending serial number (e.g., 1050).')
    )
    issue_date = models.DateField(
        verbose_name=_('Issue Date'),
        help_text=_('Date the book was received from bank.')
    )
    # is_active inherited from StatusMixin
    
    class Meta:
        verbose_name = _('Cheque Book')
        verbose_name_plural = _('Cheque Books')
        ordering = ['-issue_date', 'book_no']
        unique_together = ['bank_account', 'book_no']
        indexes = [
            models.Index(fields=['bank_account', 'is_active']),
        ]
    
    def __str__(self) -> str:
        return f"{self.book_no} ({self.bank_account.title})"
    
    def clean(self) -> None:
        """Validate serial range."""
        from django.core.exceptions import ValidationError
        
        if self.end_serial < self.start_serial:
            raise ValidationError({
                'end_serial': _('End serial must be greater than or equal to start serial.')
            })
        
        # Check for overlapping ranges in the same bank account
        if not self.pk:  # Only on creation
            overlapping = ChequeBook.objects.filter(
                bank_account=self.bank_account
            ).filter(
                models.Q(start_serial__lte=self.end_serial, end_serial__gte=self.start_serial)
            ).exists()
            
            if overlapping:
                raise ValidationError(
                    _('Serial range overlaps with an existing cheque book for this bank account.')
                )
    
    def save(self, *args, **kwargs) -> None:
        """
        Override save to validate and generate leaves on creation.
        """
        from django.db import transaction
        
        self.clean()
        is_new = self.pk is None
        
        with transaction.atomic():
            super().save(*args, **kwargs)
            
            if is_new:
                # Generate cheque leaves for this book
                self._generate_leaves()
    
    def _generate_leaves(self) -> None:
        """Generate ChequeLeaf records for the serial range."""
        leaves = []
        for serial in range(self.start_serial, self.end_serial + 1):
            leaf_number = f"{self.prefix}{serial}"
            leaves.append(ChequeLeaf(
                book=self,
                leaf_number=leaf_number,
                status=LeafStatus.AVAILABLE
            ))
        
        ChequeLeaf.objects.bulk_create(leaves)
    
    @property
    def total_leaves(self) -> int:
        """Total number of leaves in this book."""
        return self.end_serial - self.start_serial + 1
    
    @property
    def available_count(self) -> int:
        """Count of available leaves."""
        return self.leaves.filter(status=LeafStatus.AVAILABLE).count()
    
    @property
    def issued_count(self) -> int:
        """Count of issued leaves."""
        return self.leaves.filter(status=LeafStatus.ISSUED).count()
    
    @property
    def cancelled_count(self) -> int:
        """Count of cancelled leaves."""
        return self.leaves.filter(status=LeafStatus.CANCELLED).count()
    
    @property
    def damaged_count(self) -> int:
        """Count of damaged leaves."""
        return self.leaves.filter(status=LeafStatus.DAMAGED).count()
    
    def get_next_available_leaf(self) -> Optional['ChequeLeaf']:
        """Get the next available leaf in this book."""
        return self.leaves.filter(status=LeafStatus.AVAILABLE).order_by('id').first()


class ChequeLeaf(TimeStampedMixin):
    """
    Individual cheque leaf (page) in a cheque book.
    
    Tracks the status of each physical cheque page.
    
    Attributes:
        book: Parent cheque book
        leaf_number: Full composite number (e.g., "A1001")
        status: Current status (Available, Issued, Cancelled, Damaged)
        void_reason: Reason if cancelled/damaged
    """
    
    book = models.ForeignKey(
        ChequeBook,
        on_delete=models.CASCADE,
        related_name='leaves',
        verbose_name=_('Cheque Book')
    )
    leaf_number = models.CharField(
        max_length=30,
        verbose_name=_('Leaf Number'),
        help_text=_('Full composite cheque number (e.g., A1001).')
    )
    status = models.CharField(
        max_length=15,
        choices=LeafStatus.choices,
        default=LeafStatus.AVAILABLE,
        verbose_name=_('Status')
    )
    void_reason = models.TextField(
        blank=True,
        verbose_name=_('Void Reason'),
        help_text=_('Reason for cancellation or damage.')
    )
    used_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Used At'),
        help_text=_('When the leaf was issued/used.')
    )
    
    class Meta:
        verbose_name = _('Cheque Leaf')
        verbose_name_plural = _('Cheque Leaves')
        ordering = ['book', 'id']
        # Leaf number must be unique per bank account (across all books)
        constraints = [
            models.UniqueConstraint(
                fields=['book', 'leaf_number'],
                name='unique_leaf_per_book'
            )
        ]
        indexes = [
            models.Index(fields=['book', 'status']),
            models.Index(fields=['leaf_number']),
        ]
    
    def __str__(self) -> str:
        return f"{self.leaf_number} - {self.get_status_display()}"
    
    def mark_issued(self) -> None:
        """Mark this leaf as issued."""
        from django.utils import timezone
        
        if self.status != LeafStatus.AVAILABLE:
            from django.core.exceptions import ValidationError
            raise ValidationError(
                _(f'Cannot issue leaf. Current status: {self.get_status_display()}')
            )
        
        self.status = LeafStatus.ISSUED
        self.used_at = timezone.now()
        self.save(update_fields=['status', 'used_at', 'updated_at'])
    
    def mark_cancelled(self, reason: str = '') -> None:
        """Mark this leaf as cancelled."""
        if self.status == LeafStatus.ISSUED:
            from django.core.exceptions import ValidationError
            raise ValidationError(
                _('Cannot cancel an issued leaf. It may already be used in a payment.')
            )
        
        self.status = LeafStatus.CANCELLED
        self.void_reason = reason
        self.save(update_fields=['status', 'void_reason', 'updated_at'])
    
    def mark_damaged(self, reason: str = '') -> None:
        """Mark this leaf as damaged."""
        if self.status == LeafStatus.ISSUED:
            from django.core.exceptions import ValidationError
            raise ValidationError(
                _('Cannot mark an issued leaf as damaged.')
            )
        
        self.status = LeafStatus.DAMAGED
        self.void_reason = reason
        self.save(update_fields=['status', 'void_reason', 'updated_at'])


class StatementStatus(models.TextChoices):
    """
    Status choices for BankStatement.
    """
    DRAFT = 'DRAFT', _('Draft')
    RECONCILING = 'RECONCILING', _('Reconciling')
    RECONCILED = 'RECONCILED', _('Reconciled')
    LOCKED = 'LOCKED', _('Locked')


class BankStatement(AuditLogMixin):
    """
    Bank statement header for a specific month.
    
    Represents an external bank statement uploaded for reconciliation
    against the internal General Ledger (Cash Book).
    
    Attributes:
        bank_account: The bank account this statement is for
        month: Month number (1-12)
        year: Fiscal year reference
        opening_balance: Statement opening balance
        closing_balance: Statement closing balance
        is_locked: Whether statement is locked after reconciliation
        file: Uploaded statement file (CSV/PDF)
        status: Current reconciliation status
    """
    
    bank_account = models.ForeignKey(
        'core.BankAccount',
        on_delete=models.PROTECT,
        related_name='statements',
        verbose_name=_('Bank Account'),
        help_text=_('Bank account this statement belongs to.')
    )
    month = models.PositiveSmallIntegerField(
        verbose_name=_('Month'),
        help_text=_('Statement month (1-12).')
    )
    year = models.ForeignKey(
        'budgeting.FiscalYear',
        on_delete=models.PROTECT,
        related_name='bank_statements',
        verbose_name=_('Fiscal Year'),
        help_text=_('Fiscal year this statement belongs to.')
    )
    opening_balance = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name=_('Opening Balance'),
        help_text=_('Balance at the start of the statement period.')
    )
    closing_balance = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name=_('Closing Balance'),
        help_text=_('Balance at the end of the statement period.')
    )
    status = models.CharField(
        max_length=15,
        choices=StatementStatus.choices,
        default=StatementStatus.DRAFT,
        verbose_name=_('Status')
    )
    is_locked = models.BooleanField(
        default=False,
        verbose_name=_('Is Locked'),
        help_text=_('Whether this statement is locked after reconciliation.')
    )
    file = models.FileField(
        upload_to='bank_statements/%Y/%m/',
        blank=True,
        null=True,
        verbose_name=_('Statement File'),
        help_text=_('Uploaded bank statement file (CSV or PDF).')
    )
    notes = models.TextField(
        blank=True,
        verbose_name=_('Notes'),
        help_text=_('Additional notes about this statement.')
    )
    
    class Meta:
        verbose_name = _('Bank Statement')
        verbose_name_plural = _('Bank Statements')
        ordering = ['-year__start_date', '-month']
        unique_together = ['bank_account', 'month', 'year']
        indexes = [
            models.Index(fields=['bank_account', 'year', 'month']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self) -> str:
        month_name = [
            'January', 'February', 'March', 'April', 'May', 'June',
            'July', 'August', 'September', 'October', 'November', 'December'
        ][self.month - 1]
        return f"{self.bank_account.title} - {month_name} {self.year.year_name}"
    
    def clean(self) -> None:
        """Validate month range."""
        from django.core.exceptions import ValidationError
        
        if self.month < 1 or self.month > 12:
            raise ValidationError({
                'month': _('Month must be between 1 and 12.')
            })
    
    def save(self, *args, **kwargs) -> None:
        """Override save to validate."""
        self.clean()
        super().save(*args, **kwargs)
    
    @property
    def total_debits(self) -> Decimal:
        """Total debit (withdrawal) amount from statement lines."""
        from django.db.models import Sum
        result = self.lines.aggregate(total=Sum('debit'))
        return result['total'] or Decimal('0.00')
    
    @property
    def total_credits(self) -> Decimal:
        """Total credit (deposit) amount from statement lines."""
        from django.db.models import Sum
        result = self.lines.aggregate(total=Sum('credit'))
        return result['total'] or Decimal('0.00')
    
    @property
    def reconciled_count(self) -> int:
        """Count of reconciled lines."""
        return self.lines.filter(is_reconciled=True).count()
    
    @property
    def unreconciled_count(self) -> int:
        """Count of unreconciled lines."""
        return self.lines.filter(is_reconciled=False).count()
    
    @property
    def calculated_closing(self) -> Decimal:
        """Calculate closing balance from opening + credits - debits."""
        return self.opening_balance + self.total_credits - self.total_debits
    
    def lock(self) -> None:
        """Lock the statement after reconciliation is complete."""
        from django.core.exceptions import ValidationError
        
        if self.is_locked:
            raise ValidationError(_('Statement is already locked.'))
        
        self.is_locked = True
        self.status = StatementStatus.LOCKED
        self.save(update_fields=['is_locked', 'status', 'updated_at'])


class BankStatementLine(TimeStampedMixin):
    """
    Individual line item from a bank statement.
    
    Represents a single transaction from the bank's perspective.
    Can be matched to a JournalEntry from our GL.
    
    Attributes:
        statement: Parent bank statement
        date: Transaction date
        description: Transaction description from bank
        debit: Withdrawal amount (money out)
        credit: Deposit amount (money in)
        ref_no: Bank's reference/cheque number
        balance: Running balance after this transaction
        is_reconciled: Whether this line has been matched
        matched_entry: Link to the matching JournalEntry
    """
    
    statement = models.ForeignKey(
        BankStatement,
        on_delete=models.CASCADE,
        related_name='lines',
        verbose_name=_('Statement')
    )
    date = models.DateField(
        verbose_name=_('Transaction Date'),
        help_text=_('Date of the transaction as per bank.')
    )
    description = models.CharField(
        max_length=255,
        verbose_name=_('Description'),
        help_text=_('Transaction description from bank statement.')
    )
    debit = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name=_('Debit (Withdrawal)'),
        help_text=_('Amount debited/withdrawn from account.')
    )
    credit = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name=_('Credit (Deposit)'),
        help_text=_('Amount credited/deposited to account.')
    )
    ref_no = models.CharField(
        max_length=50,
        blank=True,
        db_index=True,
        verbose_name=_('Reference No'),
        help_text=_('Cheque number or transaction reference from bank.')
    )
    balance = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name=_('Balance'),
        help_text=_('Running balance after this transaction.')
    )
    is_reconciled = models.BooleanField(
        default=False,
        verbose_name=_('Is Reconciled'),
        help_text=_('Whether this line has been matched with GL entry.')
    )
    matched_entry = models.OneToOneField(
        JournalEntry,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bank_match',
        verbose_name=_('Matched Entry'),
        help_text=_('The GL journal entry this line is matched to.')
    )
    
    class Meta:
        verbose_name = _('Bank Statement Line')
        verbose_name_plural = _('Bank Statement Lines')
        ordering = ['statement', 'date', 'id']
        indexes = [
            models.Index(fields=['statement', 'is_reconciled']),
            models.Index(fields=['ref_no']),
            models.Index(fields=['date']),
        ]
    
    def __str__(self) -> str:
        amount = self.debit if self.debit > 0 else self.credit
        txn_type = 'DR' if self.debit > 0 else 'CR'
        return f"{self.date} - {txn_type} {amount} - {self.description[:30]}"
    
    def clean(self) -> None:
        """Validate that either debit or credit is set."""
        from django.core.exceptions import ValidationError
        
        if self.debit > 0 and self.credit > 0:
            raise ValidationError(
                _('A statement line cannot have both debit and credit amounts.')
            )
    
    def save(self, *args, **kwargs) -> None:
        """Override save to validate."""
        self.clean()
        super().save(*args, **kwargs)
    
    @property
    def amount(self) -> Decimal:
        """Get the transaction amount (positive for credit, negative for debit)."""
        if self.credit > 0:
            return self.credit
        return -self.debit
    
    def match_with_entry(self, entry: JournalEntry) -> None:
        """
        Match this statement line with a GL journal entry.
        
        Args:
            entry: The JournalEntry to match with.
            
        Raises:
            ValidationError: If already reconciled or entry already matched.
        """
        from django.core.exceptions import ValidationError
        from django.utils import timezone
        
        if self.is_reconciled:
            raise ValidationError(_('This statement line is already reconciled.'))
        
        if entry.is_reconciled:
            raise ValidationError(_('This journal entry is already reconciled.'))
        
        if hasattr(entry, 'bank_match') and entry.bank_match:
            raise ValidationError(_('This journal entry is already matched.'))
        
        # Update statement line
        self.is_reconciled = True
        self.matched_entry = entry
        self.save(update_fields=['is_reconciled', 'matched_entry', 'updated_at'])
        
        # Update journal entry
        entry.is_reconciled = True
        entry.reconciled_date = timezone.now().date()
        entry.save(update_fields=['is_reconciled', 'reconciled_date', 'updated_at'])
    
    def unmatch(self) -> None:
        """
        Remove the match between this line and its journal entry.
        
        Raises:
            ValidationError: If not reconciled or statement is locked.
        """
        from django.core.exceptions import ValidationError
        
        if not self.is_reconciled:
            raise ValidationError(_('This statement line is not reconciled.'))
        
        if self.statement.is_locked:
            raise ValidationError(_('Cannot unmatch - statement is locked.'))
        
        # Update journal entry first
        if self.matched_entry:
            self.matched_entry.is_reconciled = False
            self.matched_entry.reconciled_date = None
            self.matched_entry.save(update_fields=['is_reconciled', 'reconciled_date', 'updated_at'])
        
        # Update statement line
        self.is_reconciled = False
        self.matched_entry = None
        self.save(update_fields=['is_reconciled', 'matched_entry', 'updated_at'])

