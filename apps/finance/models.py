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


class BudgetHead(AuditLogMixin, StatusMixin):
    """
    Budget Head representing a Chart of Accounts entry.
    
    Follows the PIFRA/NAM hierarchy:
    Entity -> Fund -> Function -> Object (Major/Minor/Detailed)
    
    The PUGF classification is DERIVED from:
    1. Object code (A01101 = Officers = PUGF, A01151 = Other Staff = Non-PUGF)
    2. Designation keywords in description
    
    Attributes:
        fund_id: Numeric fund identifier (1=Current, 2=Development, 5=Pension)
        function: ForeignKey to FunctionCode
        pifra_object: PIFRA object code (e.g., A01101)
        tma_sub_object: TMA-specific sub-object code
        description: Human-readable description
        account_type: Expenditure, Revenue, etc.
        fund_type: Derived PUGF/Non-PUGF classification
        budget_control: Whether budget limits apply
        project_required: Whether project code is required
        posting_allowed: Whether transactions can be posted
    """
    
    # NAM Code validator (alphanumeric with optional dash)
    nam_code_validator = RegexValidator(
        regex=r'^[A-Z0-9]+-?[A-Z0-9]*$',
        message=_('NAM code must be alphanumeric (e.g., A01101 or A01101-000).')
    )
    
    fund = models.ForeignKey(
        'finance.Fund',
        on_delete=models.PROTECT,
        related_name='budget_heads',
        verbose_name=_('Fund'),
        default=2
    )
    function = models.ForeignKey(
        FunctionCode,
        on_delete=models.PROTECT,
        related_name='budget_heads',
        verbose_name=_('Function'),
        null=True,
        blank=True
    )
    pifra_object = models.CharField(
        max_length=20,
        validators=[nam_code_validator],
        verbose_name=_('PIFRA Object Code'),
        help_text=_('Standard PIFRA object code (e.g., A01101).')
    )
    pifra_description = models.CharField(
        max_length=255,
        verbose_name=_('PIFRA Description'),
        help_text=_('Standard PIFRA description.')
    )
    tma_sub_object = models.CharField(
        max_length=30,
        unique=True,
        validators=[nam_code_validator],
        verbose_name=_('TMA Sub-Object Code'),
        help_text=_('TMA-specific sub-object code (e.g., A01101-000).')
    )
    tma_description = models.CharField(
        max_length=255,
        verbose_name=_('TMA Description'),
        help_text=_('TMA-specific description.')
    )
    account_type = models.CharField(
        max_length=3,
        choices=AccountType.choices,
        default=AccountType.EXPENDITURE,
        verbose_name=_('Account Type')
    )
    fund_type = models.CharField(
        max_length=5,
        choices=FundType.choices,
        default=FundType.NON_PUGF,
        verbose_name=_('Fund Type'),
        help_text=_('PUGF/Non-PUGF classification (derived from object code).')
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
    is_charged = models.BooleanField(
        default=False,
        verbose_name=_('Is Charged (Non-Votable)'),
        help_text=_('Charged expenditure that Council cannot reduce.')
    )
    
    class Meta:
        verbose_name = _('Budget Head')
        verbose_name_plural = _('Budget Heads')
        ordering = ['fund', 'pifra_object', 'tma_sub_object']
        indexes = [
            models.Index(fields=['pifra_object']),
            models.Index(fields=['tma_sub_object']),
            models.Index(fields=['fund_type']),
            models.Index(fields=['account_type']),
        ]
    
    def __str__(self) -> str:
        return f"{self.tma_sub_object} - {self.tma_description}"
    
    def save(self, *args, **kwargs) -> None:
        """
        Override save to auto-derive fund_type based on object code.
        """
        self.fund_type = self.derive_fund_type()
        super().save(*args, **kwargs)
    
    def derive_fund_type(self) -> str:
        """
        Derive PUGF/Non-PUGF classification based on rules.
        
        Logic (as per KP LG Act 2013 clarification):
        1. Fund 5 -> PENSION
        2. Fund 2 -> DEVELOPMENT
        3. Fund 1 with A01101 (Officers) -> PUGF
        4. Fund 1 with A01151 (Other Staff) -> NON_PUGF
        5. Fund 1 + Officer keywords in desc -> PUGF
        6. Otherwise -> NON_PUGF
        
        Returns:
            FundType value string.
        """
        # Pension is always separate
        if self.fund_id == 5:
            return FundType.PENSION
        
        # Development is always separate
        if self.fund_id == 2:
            return FundType.DEVELOPMENT
        
        # For Fund 1 (Current), derive from object code
        if self.fund_id == 1:
            # A01101 = Basic Pay of Officers = PUGF
            if self.pifra_object == 'A01101':
                return FundType.PUGF
            
            # A01151 = Basic Pay of Other Staff = Non-PUGF
            if self.pifra_object == 'A01151':
                return FundType.NON_PUGF
            
            # Check for officer keywords in description
            pugf_keywords = ['tmo', 'tehsil officer', 'engineer', 'superintendent']
            desc_lower = self.tma_description.lower()
            if any(keyword in desc_lower for keyword in pugf_keywords):
                return FundType.PUGF
        
        # Default to Non-PUGF
        return FundType.NON_PUGF
    
    def get_full_code(self) -> str:
        """Return the complete NAM code path."""
        func_code = self.function.code if self.function else 'XX'
        return f"F{self.fund_id}-{func_code}-{self.tma_sub_object}"
    
    def is_salary_head(self) -> bool:
        """Check if this is a salary-related budget head (A01*)."""
        return self.pifra_object.startswith('A01')
    
    def is_development_head(self) -> bool:
        """Check if this is a development budget head."""
        return self.fund_id == 2 or self.fund_type == FundType.DEVELOPMENT


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
    
    class Meta:
        verbose_name = _('Journal Entry')
        verbose_name_plural = _('Journal Entries')
        ordering = ['voucher', 'id']
        indexes = [
            models.Index(fields=['voucher']),
            models.Index(fields=['budget_head']),
        ]
    
    def __str__(self) -> str:
        amount = self.debit if self.debit > 0 else self.credit
        entry_type = 'Dr' if self.debit > 0 else 'Cr'
        return f"{self.budget_head.tma_sub_object} - {entry_type} {amount}"
    
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

