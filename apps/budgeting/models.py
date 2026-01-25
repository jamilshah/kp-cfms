"""
-------------------------------------------------------------------------
System: KP-CFMS (Computerized Financial Management System)
Client: Local Government Department, Khyber Pakhtunkhwa
Team Lead: Jamil Shah
Developers: Ali Asghar, Akhtar Munir and Zarif Khan
Description: Database models for the budgeting module including
             FiscalYear, BudgetAllocation, ScheduleOfEstablishment,
             and SAE (Schedule of Authorized Expenditure).
             Updated for multi-tenancy and PUGF/Local workflows.
-------------------------------------------------------------------------
"""
from decimal import Decimal
from typing import Optional, List
from django.db import models
from django.db.models import Sum, F
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.translation import gettext_lazy as _
from django.utils import timezone

from apps.core.mixins import AuditLogMixin, StatusMixin, TimeStampedMixin, TenantAwareMixin
from apps.core.exceptions import (
    BudgetLockedException,
    FiscalYearInactiveException,
    ReserveViolationException,
    WorkflowTransitionException,
)


class BudgetStatus(models.TextChoices):
    """
    Status choices for budget workflow.
    """
    DRAFT = 'DRAFT', _('Draft')
    SUBMITTED = 'SUBMITTED', _('Submitted for Review')
    VERIFIED = 'VERIFIED', _('Verified by Accountant')
    APPROVED = 'APPROVED', _('Approved by TMO')
    LOCKED = 'LOCKED', _('Locked (Finalized)')


class ReleaseQuarter(models.TextChoices):
    """
    Quarterly release periods for fund disbursement.
    """
    Q1 = 'Q1', _('Q1 (July-September)')
    Q2 = 'Q2', _('Q2 (October-December)')
    Q3 = 'Q3', _('Q3 (January-March)')
    Q4 = 'Q4', _('Q4 (April-June)')


class PostType(models.TextChoices):
    """
    Post classification for approval workflow.
    
    PUGF: Provincial Unified Group of Fund - requires LCB approval.
    LOCAL: Local/TMA posts - TMO has final approval authority.
    """
    PUGF = 'PUGF', _('PUGF (Provincial)')
    LOCAL = 'LOCAL', _('Local (TMA)')


class ApprovalStatus(models.TextChoices):
    """
    Approval status for PUGF/Local dual-workflow.
    
    Local Workflow: DRAFT -> VERIFIED -> APPROVED
    PUGF Workflow:  DRAFT -> VERIFIED -> RECOMMENDED -> APPROVED
    """
    DRAFT = 'DRAFT', _('Draft')
    VERIFIED = 'VERIFIED', _('Verified by TO Finance')
    RECOMMENDED = 'RECOMMENDED', _('Recommended by TMO (Pending LCB)')
    APPROVED = 'APPROVED', _('Approved')
    REJECTED = 'REJECTED', _('Rejected')


class FiscalYear(AuditLogMixin, TenantAwareMixin):
    """
    Represents a financial year for budget planning.
    
    The fiscal year in Pakistan runs from July 1 to June 30.
    Budget entry is controlled via is_active and is_locked flags.
    
    Attributes:
        organization: The TMA this fiscal year belongs to
        year_name: Display name (e.g., "2026-27")
        start_date: First day of fiscal year (July 1)
        end_date: Last day of fiscal year (June 30)
        is_active: Whether budget entry window is open
        is_locked: Whether budget is finalized (no edits allowed)
        status: Current workflow status
    """
    
    year_name = models.CharField(
        max_length=20,
        verbose_name=_('Fiscal Year'),
        help_text=_('Display name for the fiscal year (e.g., "2026-27").')
    )
    start_date = models.DateField(
        verbose_name=_('Start Date'),
        help_text=_('First day of the fiscal year (July 1).')
    )
    end_date = models.DateField(
        verbose_name=_('End Date'),
        help_text=_('Last day of the fiscal year (June 30).')
    )
    is_active = models.BooleanField(
        default=False,
        verbose_name=_('Budget Entry Active'),
        help_text=_('Whether budget entry window is currently open.')
    )
    is_locked = models.BooleanField(
        default=False,
        verbose_name=_('Budget Locked'),
        help_text=_('Whether budget is finalized and locked for edits.')
    )
    status = models.CharField(
        max_length=15,
        choices=BudgetStatus.choices,
        default=BudgetStatus.DRAFT,
        verbose_name=_('Status')
    )
    sae_number = models.CharField(
        max_length=50,
        blank=True,
        verbose_name=_('SAE Number'),
        help_text=_('Unique identifier for Schedule of Authorized Expenditure.')
    )
    sae_generated_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('SAE Generated At')
    )
    
    class Meta:
        verbose_name = _('Fiscal Year')
        verbose_name_plural = _('Fiscal Years')
        ordering = ['-start_date']
        unique_together = ['organization', 'year_name']
    
    def __str__(self) -> str:
        return f"FY {self.year_name}"
    
    def clean(self) -> None:
        """Validate that start_date is before end_date."""
        from django.core.exceptions import ValidationError
        if self.start_date and self.end_date:
            if self.start_date >= self.end_date:
                raise ValidationError({
                    'end_date': _('End date must be after start date.')
                })
    
    def can_edit_budget(self) -> bool:
        """Check if budget entries can be modified."""
        return self.is_active and not self.is_locked
    
    def lock_budget(self, sae_number: str) -> None:
        """
        Lock the budget and set SAE number.
        
        Args:
            sae_number: Unique SAE identifier.
            
        Raises:
            BudgetLockedException: If budget is already locked.
        """
        if self.is_locked:
            raise BudgetLockedException(
                f"Budget for {self.year_name} is already locked."
            )
        self.is_locked = True
        self.is_active = False
        self.status = BudgetStatus.LOCKED
        self.sae_number = sae_number
        self.sae_generated_at = timezone.now()
        self.save(update_fields=[
            'is_locked', 'is_active', 'status', 
            'sae_number', 'sae_generated_at', 'updated_at'
        ])
    
    def get_total_receipts(self) -> Decimal:
        """Calculate total budgeted receipts for this fiscal year."""
        from apps.finance.models import AccountType
        result = self.allocations.filter(
            budget_head__account_type=AccountType.REVENUE
        ).aggregate(total=Sum('original_allocation'))
        return result['total'] or Decimal('0.00')
    
    def get_total_expenditure(self) -> Decimal:
        """Calculate total budgeted expenditure for this fiscal year."""
        from apps.finance.models import AccountType
        result = self.allocations.filter(
            budget_head__account_type=AccountType.EXPENDITURE
        ).aggregate(total=Sum('original_allocation'))
        return result['total'] or Decimal('0.00')
    
    def get_contingency_amount(self) -> Decimal:
        """Get the contingency/reserve allocation amount."""
        result = self.allocations.filter(
            budget_head__pifra_object__startswith='A09'
        ).aggregate(total=Sum('original_allocation'))
        return result['total'] or Decimal('0.00')


class BudgetAllocation(AuditLogMixin, TenantAwareMixin):
    """
    Budget allocation for a specific head within a fiscal year.
    
    Tracks original allocation, revisions, releases, and spending.
    This is the core model for Hard Budget Constraints.
    """
    
    fiscal_year = models.ForeignKey(
        FiscalYear,
        on_delete=models.PROTECT,
        related_name='allocations',
        verbose_name=_('Fiscal Year')
    )
    budget_head = models.ForeignKey(
        'finance.BudgetHead',
        on_delete=models.PROTECT,
        related_name='allocations',
        verbose_name=_('Budget Head')
    )
    original_allocation = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name=_('Original Allocation'),
        help_text=_('Initially approved budget amount.')
    )
    revised_allocation = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name=_('Revised Allocation'),
        help_text=_('Current allocation after re-appropriations.')
    )
    released_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name=_('Released Amount'),
        help_text=_('Amount currently available for spending.')
    )
    spent_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name=_('Spent Amount'),
        help_text=_('Actual expenditure posted to date.')
    )
    previous_year_actual = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name=_('Previous Year Actual'),
        help_text=_('Last year actual for comparison.')
    )
    current_year_budget = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name=_('Current Year Budget'),
        help_text=_('Current year budget for comparison.')
    )
    remarks = models.TextField(
        blank=True,
        verbose_name=_('Remarks'),
        help_text=_('Justification for significant changes.')
    )
    
    class Meta:
        verbose_name = _('Budget Allocation')
        verbose_name_plural = _('Budget Allocations')
        ordering = ['fiscal_year', 'budget_head__pifra_object']
        unique_together = ['organization', 'fiscal_year', 'budget_head']
        indexes = [
            models.Index(fields=['fiscal_year', 'budget_head']),
            models.Index(fields=['organization']),
        ]
    
    def __str__(self) -> str:
        return f"{self.fiscal_year} - {self.budget_head.tma_sub_object}"
    
    def save(self, *args, **kwargs) -> None:
        """Initialize revised_allocation from original if not set."""
        if self.revised_allocation == Decimal('0.00') and self.original_allocation > Decimal('0.00'):
            self.revised_allocation = self.original_allocation
        super().save(*args, **kwargs)
    
    def get_available_budget(self) -> Decimal:
        """Calculate remaining available budget."""
        return self.released_amount - self.spent_amount
    
    def get_commitment_balance(self) -> Decimal:
        """Get uncommitted balance from revised allocation."""
        return self.revised_allocation - self.spent_amount
    
    def can_spend(self, amount: Decimal) -> bool:
        """Check if the given amount can be spent from this allocation."""
        return (self.spent_amount + amount) <= self.released_amount
    
    def get_growth_percentage(self) -> Optional[Decimal]:
        """Calculate growth percentage from previous year."""
        if self.previous_year_actual == Decimal('0.00'):
            return None
        growth = ((self.original_allocation - self.previous_year_actual) 
                  / self.previous_year_actual) * 100
        return growth.quantize(Decimal('0.01'))


class DesignationMaster(TimeStampedMixin):
    """
    Master table for unique designations.
    
    Used to standardize designation names across the system
    and link them to BPS scales.
    """
    
    name = models.CharField(
        max_length=100,
        unique=True,
        verbose_name=_('Designation Name'),
        help_text=_('Standard designation name (e.g., Junior Clerk, TMO).')
    )
    bps_scale = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(22)],
        verbose_name=_('BPS Grade'),
        help_text=_('Default Basic Pay Scale grade (1-22).')
    )
    post_type = models.CharField(
        max_length=10,
        choices=PostType.choices,
        default=PostType.LOCAL,
        verbose_name=_('Post Type'),
        help_text=_('PUGF (Provincial) or LOCAL (TMA) classification.')
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_('Is Active')
    )
    
    class Meta:
        verbose_name = _('Designation Master')
        verbose_name_plural = _('Designation Masters')
        ordering = ['name']
    
    def __str__(self) -> str:
        return f"{self.name} (BPS-{self.bps_scale})"


class ScheduleOfEstablishment(AuditLogMixin, TenantAwareMixin):
    """
    Schedule of Establishment (Form BDC-2) - Staffing positions.
    
    Links sanctioned posts to salary budget heads (A01*).
    Used to validate that salary budgets are backed by approved posts.
    Supports PUGF/Local dual-workflow approval.
    """
    
    fiscal_year = models.ForeignKey(
        FiscalYear,
        on_delete=models.PROTECT,
        related_name='establishment_schedule',
        verbose_name=_('Fiscal Year')
    )
    department = models.CharField(
        max_length=100,
        verbose_name=_('Department/Wing'),
        help_text=_('Name of the department or administrative wing.')
    )
    designation = models.ForeignKey(
        DesignationMaster,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='establishment_entries',
        verbose_name=_('Designation'),
        help_text=_('Link to master designation.')
    )
    designation_name = models.CharField(
        max_length=100,
        verbose_name=_('Designation Name'),
        help_text=_('Post title (e.g., Junior Clerk, Superintendent).')
    )
    bps_scale = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(22)],
        verbose_name=_('BPS Grade'),
        help_text=_('Basic Pay Scale grade (1-22).')
    )
    post_type = models.CharField(
        max_length=10,
        choices=PostType.choices,
        default=PostType.LOCAL,
        verbose_name=_('Post Type'),
        help_text=_('PUGF requires LCB approval; LOCAL requires TMO approval.')
    )
    sanctioned_posts = models.PositiveIntegerField(
        default=0,
        verbose_name=_('Sanctioned Posts'),
        help_text=_('Number of approved/authorized positions.')
    )
    occupied_posts = models.PositiveIntegerField(
        default=0,
        verbose_name=_('Occupied Posts'),
        help_text=_('Number of currently filled positions.')
    )
    annual_salary = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name=_('Annual Salary per Post'),
        help_text=_('Annual salary cost per position including allowances.')
    )
    budget_head = models.ForeignKey(
        'finance.BudgetHead',
        on_delete=models.PROTECT,
        related_name='establishment_entries',
        verbose_name=_('Salary Budget Head'),
        help_text=_('Linked salary head (A01*).')
    )
    approval_status = models.CharField(
        max_length=15,
        choices=ApprovalStatus.choices,
        default=ApprovalStatus.DRAFT,
        verbose_name=_('Approval Status'),
        help_text=_('Current approval status in the workflow.')
    )
    recommended_by = models.ForeignKey(
        'users.CustomUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='recommended_establishments',
        verbose_name=_('Recommended By'),
        help_text=_('TMO who recommended (for PUGF posts).')
    )
    recommended_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Recommended At')
    )
    approved_by = models.ForeignKey(
        'users.CustomUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_establishments',
        verbose_name=_('Approved By'),
        help_text=_('TMO (for Local) or LCB (for PUGF) who approved.')
    )
    approved_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Approved At')
    )
    rejection_reason = models.TextField(
        blank=True,
        verbose_name=_('Rejection Reason')
    )
    
    class Meta:
        verbose_name = _('Schedule of Establishment')
        verbose_name_plural = _('Schedule of Establishment Entries')
        ordering = ['fiscal_year', 'department', '-bps_scale']
        unique_together = ['organization', 'fiscal_year', 'department', 'designation_name', 'bps_scale']
    
    def __str__(self) -> str:
        return f"{self.designation_name} (BPS-{self.bps_scale}) - {self.department}"
    
    @property
    def vacant_posts(self) -> int:
        """Calculate number of vacant positions."""
        return max(0, self.sanctioned_posts - self.occupied_posts)
    
    @property
    def total_annual_cost(self) -> Decimal:
        """Calculate total annual salary cost for sanctioned posts."""
        return self.annual_salary * self.sanctioned_posts
    
    @property
    def actual_annual_cost(self) -> Decimal:
        """Calculate actual annual salary cost for occupied posts."""
        return self.annual_salary * self.occupied_posts
    
    @property
    def is_pugf(self) -> bool:
        """Check if this is a PUGF post."""
        return self.post_type == PostType.PUGF
    
    def can_tmo_approve(self) -> bool:
        """Check if TMO can directly approve this post."""
        return self.post_type == PostType.LOCAL
    
    def requires_lcb_approval(self) -> bool:
        """Check if this post requires LCB approval."""
        return self.post_type == PostType.PUGF
    
    def clean(self) -> None:
        """Validate budget_head and post counts."""
        from django.core.exceptions import ValidationError
        if self.budget_head and not self.budget_head.is_salary_head():
            raise ValidationError({
                'budget_head': _(
                    'Schedule of Establishment must link to a salary head (A01*). '
                    f'Selected head {self.budget_head.pifra_object} is not a salary head.'
                )
            })
        if self.occupied_posts > self.sanctioned_posts:
            raise ValidationError({
                'occupied_posts': _('Occupied posts cannot exceed sanctioned posts.')
            })


class QuarterlyRelease(AuditLogMixin, TenantAwareMixin):
    """
    Tracks quarterly fund releases for budget allocations.
    """
    
    fiscal_year = models.ForeignKey(
        FiscalYear,
        on_delete=models.PROTECT,
        related_name='quarterly_releases',
        verbose_name=_('Fiscal Year')
    )
    quarter = models.CharField(
        max_length=2,
        choices=ReleaseQuarter.choices,
        verbose_name=_('Quarter')
    )
    release_date = models.DateField(
        verbose_name=_('Release Date'),
        help_text=_('Date when the quarterly release was processed.')
    )
    is_released = models.BooleanField(
        default=False,
        verbose_name=_('Released'),
        help_text=_('Whether the quarterly funds have been released.')
    )
    total_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name=_('Total Released Amount')
    )
    notes = models.TextField(
        blank=True,
        verbose_name=_('Notes')
    )
    
    class Meta:
        verbose_name = _('Quarterly Release')
        verbose_name_plural = _('Quarterly Releases')
        ordering = ['fiscal_year', 'quarter']
        unique_together = ['organization', 'fiscal_year', 'quarter']
    
    def __str__(self) -> str:
        status = "Released" if self.is_released else "Pending"
        return f"{self.fiscal_year} - {self.get_quarter_display()} ({status})"
    
    @classmethod
    def get_quarter_for_date(cls, date) -> str:
        """Determine which quarter a date falls into."""
        month = date.month
        if month in (7, 8, 9):
            return ReleaseQuarter.Q1
        elif month in (10, 11, 12):
            return ReleaseQuarter.Q2
        elif month in (1, 2, 3):
            return ReleaseQuarter.Q3
        else:
            return ReleaseQuarter.Q4


class SAERecord(TimeStampedMixin, TenantAwareMixin):
    """
    Schedule of Authorized Expenditure record.
    
    Immutable record generated when budget is finalized.
    This is the legal document authorizing expenditure.
    """
    
    fiscal_year = models.OneToOneField(
        FiscalYear,
        on_delete=models.PROTECT,
        related_name='sae_record',
        verbose_name=_('Fiscal Year')
    )
    sae_number = models.CharField(
        max_length=50,
        unique=True,
        verbose_name=_('SAE Number')
    )
    total_receipts = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name=_('Total Receipts')
    )
    total_expenditure = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name=_('Total Expenditure')
    )
    contingency_reserve = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name=_('Contingency Reserve (2%)')
    )
    approved_by = models.ForeignKey(
        'users.CustomUser',
        on_delete=models.PROTECT,
        related_name='approved_saes',
        verbose_name=_('Approved By')
    )
    approval_date = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Approval Date')
    )
    pdf_file = models.FileField(
        upload_to='sae_documents/',
        blank=True,
        null=True,
        verbose_name=_('PDF Document')
    )
    is_authenticated = models.BooleanField(
        default=False,
        verbose_name=_('Authenticated by Nazim'),
        help_text=_('Whether the SAE has been digitally signed by Nazim.')
    )
    
    class Meta:
        verbose_name = _('SAE Record')
        verbose_name_plural = _('SAE Records')
        ordering = ['-approval_date']
    
    def __str__(self) -> str:
        return f"SAE {self.sae_number} - {self.fiscal_year}"
    
    def get_surplus_deficit(self) -> Decimal:
        """Calculate surplus (positive) or deficit (negative)."""
        return self.total_receipts - self.total_expenditure
