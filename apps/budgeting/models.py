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


class EstablishmentStatus(models.TextChoices):
    """
    Establishment status for distinguishing existing vs proposed posts.
    
    SANCTIONED: Existing approved posts (imported from baseline).
    PROPOSED: New posts proposed for Council approval (SNE).
    """
    SANCTIONED = 'SANCTIONED', _('Sanctioned (Existing)')
    PROPOSED = 'PROPOSED', _('Proposed (New)')


class PensionEstimateStatus(models.TextChoices):
    """
    Status choices for pension estimate workflow.
    """
    DRAFT = 'DRAFT', _('Draft')
    LOCKED = 'LOCKED', _('Locked (Finalized)')


class SupplementaryGrantStatus(models.TextChoices):
    """
    Status choices for supplementary grant workflow.
    """
    DRAFT = 'DRAFT', _('Draft')
    APPROVED = 'APPROVED', _('Approved')
    REJECTED = 'REJECTED', _('Rejected')


class ReappropriationStatus(models.TextChoices):
    """
    Status choices for re-appropriation workflow.
    """
    DRAFT = 'DRAFT', _('Draft')
    APPROVED = 'APPROVED', _('Approved')


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
    
    @classmethod
    def get_current_operating_year(cls, organization):
        """
        Get the fiscal year that covers the current date.
        
        This is used for expenditure/receipt transactions, where we need
        the fiscal year that contains today's date, not the one open
        for budget entry (is_active).
        
        Args:
            organization: The organization to filter by.
            
        Returns:
            FiscalYear or None: The fiscal year containing today's date.
        """
        from django.utils import timezone
        today = timezone.now().date()
        return cls.objects.filter(
            organization=organization,
            start_date__lte=today,
            end_date__gte=today
        ).first()

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
            budget_head__global_head__account_type=AccountType.REVENUE
        ).aggregate(total=Sum('original_allocation'))
        return result['total'] or Decimal('0.00')
    
    def get_total_expenditure(self) -> Decimal:
        """Calculate total budgeted expenditure for this fiscal year."""
        from apps.finance.models import AccountType
        result = self.allocations.filter(
            budget_head__global_head__account_type=AccountType.EXPENDITURE
        ).aggregate(total=Sum('original_allocation'))
        return result['total'] or Decimal('0.00')
    
    def get_contingency_amount(self) -> Decimal:
        """Get the contingency/reserve allocation amount."""
        result = self.allocations.filter(
            budget_head__global_head__code__startswith='A09'
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
        ordering = ['fiscal_year', 'budget_head__global_head__code']
        unique_together = ['organization', 'fiscal_year', 'budget_head']
        indexes = [
            models.Index(fields=['fiscal_year', 'budget_head']),
            models.Index(fields=['organization']),
        ]
    
    def __str__(self) -> str:
        return f"{self.fiscal_year} - {self.budget_head.code}"
    
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


class Department(TimeStampedMixin):
    """
    Master table for Departments/Wings.
    
    Used to standardize department names across the system.
    """
    
    name = models.CharField(
        max_length=100,
        unique=True,
        verbose_name=_('Department Name'),
        help_text=_('Name of the Department or Wing (e.g., Administration, Finance).')
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_('Is Active')
    )
    
    class Meta:
        verbose_name = _('Department')
        verbose_name_plural = _('Departments')
        ordering = ['name']
    
    def __str__(self) -> str:
        return self.name


class BPSSalaryScale(AuditLogMixin):
    """
    Master Data for BPS Pay Scales & Allowances (e.g., 2024 Scale).
    Mirroring the Finance Department Notification structure.
    """
    bps_grade = models.PositiveSmallIntegerField(
        unique=True, 
        verbose_name=_("BPS Grade"),
        validators=[MinValueValidator(1), MaxValueValidator(22)]
    )

    # --- PART 1: THE BASIC PAY SCALE (The Chart) ---
    basic_pay_min = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=Decimal('0.00'),
        verbose_name=_("Initial Stage (0)"),
        help_text=_("Initial Basic Pay")
    )
    annual_increment = models.DecimalField(
        max_digits=8, 
        decimal_places=2, 
        default=Decimal('0.00'),
        verbose_name=_("Annual Increment"),
        help_text=_("Annual Increment Amount")
    )
    basic_pay_max = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=Decimal('0.00'),
        verbose_name=_("Last Stage (30)"),
        help_text=_("Maximum Basic Pay")
    )

    # --- PART 2: FIXED ALLOWANCES (Slab Based) ---
    # These are fixed amounts defined per BPS (e.g., BPS 11 Conveyance = 2840)
    conveyance_allowance = models.DecimalField(
        max_digits=8, 
        decimal_places=2, 
        default=0,
        verbose_name=_("Conveyance Allowance")
    )
    medical_allowance = models.DecimalField(
        max_digits=8, 
        decimal_places=2, 
        default=0,
        verbose_name=_("Medical Allowance")
    )
    
    # --- PART 3: VARIABLE ALLOWANCES (Percentage Based) ---
    # House Rent: Usually 30% or 45% of the *Initial* Basic Pay
    house_rent_percent = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=Decimal('0.45'), 
        verbose_name=_("House Rent %"),
        help_text=_("e.g., 0.45 for 45% of Initial Pay")
    )

    # Adhoc Reliefs: The sum of all active reliefs (2022, 2023, 2024)
    # Usually calculated on *Running* Basic Pay. 
    # For budgeting new posts, we apply this to Initial Basic Pay.
    adhoc_relief_total_percent = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=Decimal('0.35'),
        verbose_name=_("Total Adhoc Relief %"),
        help_text=_("Sum of all active Adhoc Reliefs (e.g., 0.35 for 35%)")
    )

    class Meta:
        ordering = ['bps_grade']
        verbose_name = _("BPS Salary Scale")
        verbose_name_plural = _("BPS Salary Scales")

    def __str__(self):
        return f"BPS-{self.bps_grade} ({self.basic_pay_min}-{self.annual_increment}-{self.basic_pay_max})"

    @property
    def estimated_gross_salary(self):
        """
        Calculates the gross salary for a fresh entrant (Stage 0).
        Formula: (Min Pay * (1 + Adhoc%)) + (Min Pay * HRA%) + Fixed Allowances
        """
        # 1. Basic Pay
        basic = self.basic_pay_min

        # 2. Variable Allowances
        adhoc_amount = basic * self.adhoc_relief_total_percent
        hra_amount = basic * self.house_rent_percent

        # 3. Fixed Allowances
        fixed_total = self.conveyance_allowance + self.medical_allowance

        # Total
        return basic + adhoc_amount + hra_amount + fixed_total
    
    def get_annual_salary(self) -> Decimal:
        """
        Calculate estimated annual salary including allowances.
        
        Returns:
            Annual salary (basic × 12 × (1 + allowance_percentage/100))
        """
        return self.estimated_gross_salary * 12
    
    @classmethod
    def get_salary_for_grade(cls, bps_grade: int) -> Decimal:
        """
        Get annual salary for a given BPS grade.
        
        Args:
            bps_grade: BPS grade (1-22)
            
        Returns:
            Annual salary or default estimate if grade not found.
        """
        scale = cls.objects.filter(bps_grade=bps_grade, is_active=True).first()
        if scale:
            return scale.get_annual_salary()
        
        # Fallback to hardcoded rates if not in database
        default_rates = {
            1: 22000, 2: 22500, 3: 23000, 4: 24000, 5: 25000,
            6: 26000, 7: 28000, 8: 30000, 9: 32000, 10: 35000,
            11: 40000, 12: 45000, 13: 50000, 14: 55000, 15: 60000,
            16: 70000, 17: 80000, 18: 100000, 19: 120000, 20: 150000,
            21: 180000, 22: 220000
        }
        monthly = Decimal(str(default_rates.get(bps_grade, 25000)))
        return monthly * 12 * Decimal('1.5')  # 50% allowance


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
        default='',
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
    
    # SNE (Schedule of New Expenditure) fields
    establishment_status = models.CharField(
        max_length=15,
        choices=EstablishmentStatus.choices,
        default=EstablishmentStatus.SANCTIONED,
        verbose_name=_('Establishment Status'),
        help_text=_('SANCTIONED = existing posts, PROPOSED = new requests (SNE).')
    )
    justification = models.TextField(
        blank=True,
        verbose_name=_('Justification'),
        help_text=_('Required for PROPOSED posts. Explain why new posts are needed.')
    )
    financial_impact = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name=_('Financial Impact'),
        help_text=_('Auto-calculated: Initial Pay x 12 x Number of Posts.')
    )
    estimated_budget = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name=_('Estimated Budget'),
        help_text=_('Budget estimate from Smart Calculator (filled + vacant costs + inflation).')
    )
    last_month_bill = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name=_('Last Month Bill'),
        help_text=_('Last month total salary bill from bank advice (for estimation).')
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
        """Validate budget_head, post counts, and justification for proposals."""
        from django.core.exceptions import ValidationError
        
        # Safely check budget_head only if ID is present
        if self.budget_head_id:
            if not self.budget_head.is_salary_head():
                raise ValidationError({
                    'budget_head': _(
                        'Schedule of Establishment must link to a salary head (A01*). '
                        f'Selected head {self.budget_head.code} is not a salary head.'
                    )
                })
        if self.occupied_posts > self.sanctioned_posts:
            raise ValidationError({
                'occupied_posts': _('Occupied posts cannot exceed sanctioned posts.')
            })
        
        # PROPOSED posts require justification
        if self.establishment_status == EstablishmentStatus.PROPOSED:
            if not self.justification or len(self.justification.strip()) < 20:
                raise ValidationError({
                    'justification': _(
                        'Justification is required for new post proposals. '
                        'Please provide at least 20 characters explaining why these posts are needed.'
                    )
                })
    
    def is_proposed(self) -> bool:
        """Check if this is a new post proposal (SNE)."""
        return self.establishment_status == EstablishmentStatus.PROPOSED
    
    def is_sanctioned(self) -> bool:
        """Check if this is an existing sanctioned post."""
        return self.establishment_status == EstablishmentStatus.SANCTIONED
    
    def calculate_financial_impact(self) -> Decimal:
        """
        Calculate financial impact for proposed posts.
        
        Uses BPS initial stage salary rates for estimation.
        Also sets self.annual_salary if not already set.
        
        Returns:
            Annual financial impact in PKR.
        """
        # BPS 2024 initial pay stages (approximate)
        bps_initial_rates = {
            1: 22000, 2: 22500, 3: 23000, 4: 24000, 5: 25000,
            6: 26000, 7: 28000, 8: 30000, 9: 32000, 10: 35000,
            11: 40000, 12: 45000, 13: 50000, 14: 55000, 15: 60000,
            16: 70000, 17: 80000, 18: 100000, 19: 120000, 20: 150000,
            21: 180000, 22: 220000
        }
        monthly_rate = Decimal(str(bps_initial_rates.get(self.bps_scale, 25000)))
        
        # Determine annual salary per post
        estimated_annual_salary = monthly_rate * 12
        
        # Set annual_salary if missing (fixing IntegrityError for proposals)
        if not self.annual_salary:
            self.annual_salary = estimated_annual_salary
            
        # Calculate total impact
        annual_cost = estimated_annual_salary * self.sanctioned_posts
        return annual_cost
    
    def save(self, *args, **kwargs) -> None:
        """Auto-calculate financial impact for proposed posts."""
        if self.establishment_status == EstablishmentStatus.PROPOSED:
            self.financial_impact = self.calculate_financial_impact()
            # Ensure annual_salary is not None before super().save()
            if self.annual_salary is None:
                # Should have been set by calculate_financial_impact, but safety fallback
                self.annual_salary = Decimal('300000.00') 
        super().save(*args, **kwargs)
    
    def convert_to_sanctioned(self) -> None:
        """
        Convert a proposed post to sanctioned after budget approval.
        
        Called when the budget cycle is finalized.
        """
        if self.establishment_status == EstablishmentStatus.PROPOSED:
            self.establishment_status = EstablishmentStatus.SANCTIONED
            self.justification = ''  # Clear justification after approval
            self.financial_impact = Decimal('0.00')
            self.save(update_fields=[
                'establishment_status', 'justification', 
                'financial_impact', 'updated_at'
            ])
    
    def calculate_total_budget_requirement(self) -> dict:
        """
        Calculate total budget requirement using employee-wise data.
        
        This method performs precise budget estimation based on:
        1. Filled Posts: Sum of actual employee costs from BudgetEmployee records
           OR fallback to annual_salary * occupied_posts if no employees added.
        2. Vacant Posts: Calculated using BPS Stage-0 salary scales
        
        Updates:
            - self.estimated_budget with total calculated amount
        
        Returns:
            Dictionary with breakdown: {
                'filled_cost': Decimal,
                'vacant_cost': Decimal,
                'total_cost': Decimal,
                'filled_count': int,
                'vacant_count': int,
                'mode': str  # 'employee_wise' or 'legacy'
            }
        """
        import logging
        logger = logging.getLogger(__name__)
        
        # Check if we have employee records
        filled_employees = self.employees.filter(is_vacant=False)
        employee_count = filled_employees.count()
        
        # Determine calculation mode
        if employee_count > 0:
            # MODE 1: Employee-wise calculation (Precise)
            filled_count = employee_count
            filled_cost = Decimal('0.00')
            
            for emp in filled_employees:
                # Formula: (Basic + Allowances) * 12 + Annual Increment
                # (Annual increment is added once per year, not monthly)
                annual_cost = (
                    (emp.current_basic_pay + emp.monthly_allowances) * 12
                ) + emp.annual_increment_amount
                filled_cost += annual_cost
            
            filled_cost = filled_cost.quantize(Decimal('0.01'))
            mode = 'employee_wise'
            
        else:
            # MODE 2: Legacy fallback using occupied_posts and annual_salary
            filled_count = self.occupied_posts or 0
            
            if filled_count > 0 and self.annual_salary:
                # Use annual_salary as the per-post cost
                filled_cost = (self.annual_salary * filled_count).quantize(Decimal('0.01'))
            else:
                filled_cost = Decimal('0.00')
            
            mode = 'legacy'
        
        # Calculate Vacant Posts Cost
        vacant_count = max(0, self.sanctioned_posts - filled_count)
        
        vacant_cost = Decimal('0.00')
        if vacant_count > 0:
            # Fetch BPS Salary Scale for this grade
            scale = BPSSalaryScale.objects.filter(bps_grade=self.bps_scale).first()
            
            if scale:
                # Calculate Stage-0 Gross Salary
                basic = scale.basic_pay_min
                hra = basic * scale.house_rent_percent
                adhoc = basic * scale.adhoc_relief_total_percent
                fixed_allowances = scale.conveyance_allowance + scale.medical_allowance
                
                stage_0_gross = basic + hra + adhoc + fixed_allowances
                
                # Annual cost for vacant posts
                vacant_cost = (stage_0_gross * 12 * vacant_count).quantize(Decimal('0.01'))
            else:
                # Warn if scale not found
                logger.warning(
                    f"BPSSalaryScale not found for grade {self.bps_scale}. "
                    f"Using 0 for vacant posts cost."
                )
        
        # Calculate Total
        total_cost = (filled_cost + vacant_cost).quantize(Decimal('0.01'))
        
        # Update estimated_budget (don't overwrite occupied_posts in legacy mode)
        self.estimated_budget = total_cost
        if mode == 'employee_wise':
            self.occupied_posts = filled_count
        self.save(update_fields=['estimated_budget', 'occupied_posts', 'updated_at'])
        
        return {
            'filled_cost': filled_cost,
            'vacant_cost': vacant_cost,
            'total_cost': total_cost,
            'filled_count': filled_count,
            'vacant_count': vacant_count,
            'mode': mode,
        }


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


# =============================================================================
# Phase 3: Pension & Budget Execution Models
# =============================================================================

class PensionEstimate(AuditLogMixin, TenantAwareMixin):
    """
    Pension Estimate for budget planning.
    
    Calculates estimated pension (A04101) and commutation (A04102) budgets
    based on current pensioners and expected retirees.
    
    Attributes:
        fiscal_year: The fiscal year for this estimate
        current_monthly_bill: Total pension bill of June (last month of previous FY)
        expected_increase: Expected percentage increase (e.g., 10.0 for 10%)
        status: DRAFT or LOCKED
    """
    
    fiscal_year = models.ForeignKey(
        FiscalYear,
        on_delete=models.PROTECT,
        related_name='pension_estimates',
        verbose_name=_('Fiscal Year')
    )
    current_monthly_bill = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name=_('Current Monthly Pension Bill'),
        help_text=_('Total pension bill of June (last month of previous FY).')
    )
    expected_increase = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('10.00'),
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('100.00'))],
        verbose_name=_('Expected Increase (%)'),
        help_text=_('Expected percentage increase in pension (e.g., 10.0 for 10%).')
    )
    status = models.CharField(
        max_length=10,
        choices=PensionEstimateStatus.choices,
        default=PensionEstimateStatus.DRAFT,
        verbose_name=_('Status')
    )
    
    # Calculated fields (set by calculate_and_lock)
    estimated_monthly_pension = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name=_('Estimated Monthly Pension (A04101)'),
        help_text=_('Calculated: (current_bill * 12 * (1 + increase%)) + new retirees pension.')
    )
    estimated_commutation = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name=_('Estimated Commutation (A04102)'),
        help_text=_('Calculated: Sum of all retirees commutation amounts.')
    )
    locked_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Locked At')
    )
    locked_by = models.ForeignKey(
        'users.CustomUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='locked_pension_estimates',
        verbose_name=_('Locked By')
    )
    remarks = models.TextField(
        blank=True,
        verbose_name=_('Remarks')
    )
    
    class Meta:
        verbose_name = _('Pension Estimate')
        verbose_name_plural = _('Pension Estimates')
        ordering = ['-fiscal_year__start_date']
        unique_together = ['organization', 'fiscal_year']
    
    def __str__(self) -> str:
        return f"Pension Estimate - {self.fiscal_year}"
    
    def calculate_estimates(self) -> dict:
        """
        Calculate pension estimates without locking.
        
        Returns:
            Dictionary with 'monthly_pension' and 'commutation' values.
        """
        # A04101: (current_monthly_bill * 12 * (1 + expected_increase/100)) + Sum(new retirees * 12)
        base_annual = self.current_monthly_bill * 12 * (1 + self.expected_increase / 100)
        
        # Add new retirees' monthly pension * 12 (for remaining months in FY)
        new_retirees_pension = self.retiring_employees.aggregate(
            total=Sum(F('monthly_pension_amount') * 12)
        )['total'] or Decimal('0.00')
        
        monthly_pension_total = base_annual + new_retirees_pension
        
        # A04102: Sum of all commutation amounts
        commutation_total = self.retiring_employees.aggregate(
            total=Sum('commutation_amount')
        )['total'] or Decimal('0.00')
        
        return {
            'monthly_pension': monthly_pension_total.quantize(Decimal('0.01')),
            'commutation': commutation_total.quantize(Decimal('0.01')),
        }
    
    def calculate_and_lock(self, user=None) -> dict:
        """
        Calculate estimates and lock the pension estimate.
        
        Also creates/updates BudgetAllocations for heads A04101 and A04102.
        
        Args:
            user: The user performing the lock action.
            
        Returns:
            Dictionary with calculated values.
            
        Raises:
            ValidationError: If already locked.
        """
        from django.core.exceptions import ValidationError
        from django.db import transaction
        from apps.finance.models import BudgetHead
        
        if self.status == PensionEstimateStatus.LOCKED:
            raise ValidationError(_('This pension estimate is already locked.'))
        
        estimates = self.calculate_estimates()
        
        with transaction.atomic():
            self.estimated_monthly_pension = estimates['monthly_pension']
            self.estimated_commutation = estimates['commutation']
            self.status = PensionEstimateStatus.LOCKED
            self.locked_at = timezone.now()
            self.locked_by = user
            self.save()
            
            # Update BudgetAllocations for A04101 and A04102
            pension_head_codes = {
                'A04101': estimates['monthly_pension'],  # Monthly Pension
                'A04102': estimates['commutation'],      # Commutation
            }
            
            for head_code, amount in pension_head_codes.items():
                try:
                    budget_head = BudgetHead.objects.get(pifra_object=head_code)
                    allocation, created = BudgetAllocation.objects.get_or_create(
                        organization=self.organization,
                        fiscal_year=self.fiscal_year,
                        budget_head=budget_head,
                        defaults={
                            'original_allocation': amount,
                            'revised_allocation': amount,
                        }
                    )
                    if not created:
                        allocation.original_allocation = amount
                        allocation.revised_allocation = amount
                        allocation.save(update_fields=['original_allocation', 'revised_allocation', 'updated_at'])
                except BudgetHead.DoesNotExist:
                    # Head doesn't exist, skip (admin should create heads first)
                    pass
        
        return estimates


class RetiringEmployee(TimeStampedMixin):
    """
    Individual retiring employee for pension estimation.
    
    Linked to a PensionEstimate, tracks expected pension and commutation amounts.
    """
    
    estimate = models.ForeignKey(
        PensionEstimate,
        on_delete=models.CASCADE,
        related_name='retiring_employees',
        verbose_name=_('Pension Estimate')
    )
    name = models.CharField(
        max_length=100,
        verbose_name=_('Employee Name')
    )
    designation = models.CharField(
        max_length=100,
        verbose_name=_('Designation')
    )
    retirement_date = models.DateField(
        verbose_name=_('Retirement Date')
    )
    monthly_pension_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name=_('Monthly Pension Amount'),
        help_text=_('Expected monthly pension payout.')
    )
    commutation_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name=_('Commutation Amount'),
        help_text=_('Lump sum commutation payment.')
    )
    remarks = models.TextField(
        blank=True,
        verbose_name=_('Remarks')
    )
    
    class Meta:
        verbose_name = _('Retiring Employee')
        verbose_name_plural = _('Retiring Employees')
        ordering = ['retirement_date']
    
    def __str__(self) -> str:
        return f"{self.name} - {self.designation} (Retiring: {self.retirement_date})"
    
    @property
    def annual_pension(self) -> Decimal:
        """Calculate annual pension amount."""
        return self.monthly_pension_amount * 12


class SupplementaryGrant(AuditLogMixin, TenantAwareMixin):
    """
    Supplementary Grant for additional budget during the fiscal year.
    
    When approved, increases the revised_allocation of the linked BudgetAllocation.
    """
    
    fiscal_year = models.ForeignKey(
        FiscalYear,
        on_delete=models.PROTECT,
        related_name='supplementary_grants',
        verbose_name=_('Fiscal Year')
    )
    budget_head = models.ForeignKey(
        'finance.BudgetHead',
        on_delete=models.PROTECT,
        related_name='supplementary_grants',
        verbose_name=_('Budget Head')
    )
    amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name=_('Amount'),
        help_text=_('Additional budget amount to be granted.')
    )
    reference_no = models.CharField(
        max_length=50,
        verbose_name=_('Reference/Order No'),
        help_text=_('Government order or reference number.')
    )
    date = models.DateField(
        verbose_name=_('Date'),
        help_text=_('Date of supplementary grant order.')
    )
    description = models.TextField(
        verbose_name=_('Description'),
        help_text=_('Justification for supplementary budget.')
    )
    status = models.CharField(
        max_length=10,
        choices=SupplementaryGrantStatus.choices,
        default=SupplementaryGrantStatus.DRAFT,
        verbose_name=_('Status')
    )
    approved_by = models.ForeignKey(
        'users.CustomUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_supplementary_grants',
        verbose_name=_('Approved By')
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
        verbose_name = _('Supplementary Grant')
        verbose_name_plural = _('Supplementary Grants')
        ordering = ['-date']
    
    def __str__(self) -> str:
        return f"SG {self.reference_no} - {self.budget_head.tma_sub_object} ({self.amount:,.2f})"
    
    def approve(self, user) -> None:
        """
        Approve the supplementary grant and update budget allocation.
        
        Args:
            user: The user approving the grant.
            
        Raises:
            ValidationError: If already approved/rejected or allocation not found.
        """
        from django.core.exceptions import ValidationError
        from django.db import transaction
        
        if self.status != SupplementaryGrantStatus.DRAFT:
            raise ValidationError(
                _('Only draft supplementary grants can be approved.')
            )
        
        with transaction.atomic():
            # Find or create the BudgetAllocation
            allocation, created = BudgetAllocation.objects.get_or_create(
                organization=self.organization,
                fiscal_year=self.fiscal_year,
                budget_head=self.budget_head,
                defaults={
                    'original_allocation': Decimal('0.00'),
                    'revised_allocation': self.amount,
                }
            )
            
            if not created:
                allocation.revised_allocation += self.amount
                allocation.save(update_fields=['revised_allocation', 'updated_at'])
            
            self.status = SupplementaryGrantStatus.APPROVED
            self.approved_by = user
            self.approved_at = timezone.now()
            self.save(update_fields=['status', 'approved_by', 'approved_at', 'updated_at'])
    
    def reject(self, user, reason: str) -> None:
        """
        Reject the supplementary grant.
        
        Args:
            user: The user rejecting the grant.
            reason: Reason for rejection.
        """
        from django.core.exceptions import ValidationError
        
        if self.status != SupplementaryGrantStatus.DRAFT:
            raise ValidationError(
                _('Only draft supplementary grants can be rejected.')
            )
        
        self.status = SupplementaryGrantStatus.REJECTED
        self.rejection_reason = reason
        self.save(update_fields=['status', 'rejection_reason', 'updated_at'])


class Reappropriation(AuditLogMixin, TenantAwareMixin):
    """
    Re-appropriation for transferring budget between heads.
    
    Allows moving funds from one budget head to another within the same Fund.
    Validates that source has sufficient available balance.
    """
    
    fiscal_year = models.ForeignKey(
        FiscalYear,
        on_delete=models.PROTECT,
        related_name='reappropriations',
        verbose_name=_('Fiscal Year')
    )
    from_head = models.ForeignKey(
        'finance.BudgetHead',
        on_delete=models.PROTECT,
        related_name='reappropriations_out',
        verbose_name=_('From Budget Head'),
        help_text=_('Source head to transfer budget from.')
    )
    to_head = models.ForeignKey(
        'finance.BudgetHead',
        on_delete=models.PROTECT,
        related_name='reappropriations_in',
        verbose_name=_('To Budget Head'),
        help_text=_('Destination head to transfer budget to.')
    )
    amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name=_('Amount'),
        help_text=_('Amount to transfer.')
    )
    reference_no = models.CharField(
        max_length=50,
        verbose_name=_('Reference/Order No'),
        help_text=_('Authorization reference number.')
    )
    date = models.DateField(
        verbose_name=_('Date')
    )
    description = models.TextField(
        verbose_name=_('Description'),
        help_text=_('Justification for re-appropriation.')
    )
    status = models.CharField(
        max_length=10,
        choices=ReappropriationStatus.choices,
        default=ReappropriationStatus.DRAFT,
        verbose_name=_('Status')
    )
    approved_by = models.ForeignKey(
        'users.CustomUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_reappropriations',
        verbose_name=_('Approved By')
    )
    approved_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Approved At')
    )
    
    class Meta:
        verbose_name = _('Re-appropriation')
        verbose_name_plural = _('Re-appropriations')
        ordering = ['-date']
    
    def __str__(self) -> str:
        return f"RA {self.reference_no}: {self.from_head.tma_sub_object} → {self.to_head.tma_sub_object} ({self.amount:,.2f})"
    
    def clean(self) -> None:
        """
        Validate re-appropriation rules.
        
        1. Fund Check: from_head and to_head must belong to the same Fund.
        2. Balance Check: from_head must have enough Available Balance.
        """
        from django.core.exceptions import ValidationError
        
        errors = {}
        
        # Check that from_head and to_head are set
        if not self.from_head_id or not self.to_head_id:
            return  # Let field validation handle required fields
        
        # Rule 1: Same Fund check
        if self.from_head.fund_id != self.to_head.fund_id:
            errors['to_head'] = _(
                'Cannot transfer funds between different Funds. '
                f'From: {self.from_head.fund}, To: {self.to_head.fund}'
            )
        
        # Rule 2: Available Balance check (only for existing allocations)
        if self.status == ReappropriationStatus.DRAFT and self.fiscal_year_id:
            try:
                from_allocation = BudgetAllocation.objects.get(
                    organization=self.organization,
                    fiscal_year=self.fiscal_year,
                    budget_head=self.from_head
                )
                available = from_allocation.revised_allocation - from_allocation.spent_amount
                if self.amount > available:
                    errors['amount'] = _(
                        f'Insufficient balance in {self.from_head.tma_sub_object}. '
                        f'Available: Rs {available:,.2f}, Requested: Rs {self.amount:,.2f}'
                    )
            except BudgetAllocation.DoesNotExist:
                errors['from_head'] = _(
                    f'No budget allocation found for {self.from_head} in {self.fiscal_year}.'
                )
        
        if errors:
            raise ValidationError(errors)
    
    def approve(self, user) -> None:
        """
        Approve the re-appropriation and transfer funds.
        
        Args:
            user: The user approving the re-appropriation.
            
        Raises:
            ValidationError: If validation fails or already approved.
        """
        from django.core.exceptions import ValidationError
        from django.db import transaction
        
        if self.status != ReappropriationStatus.DRAFT:
            raise ValidationError(
                _('Only draft re-appropriations can be approved.')
            )
        
        # Re-validate before approval
        self.clean()
        
        with transaction.atomic():
            # Decrease from_head allocation
            from_allocation = BudgetAllocation.objects.select_for_update().get(
                organization=self.organization,
                fiscal_year=self.fiscal_year,
                budget_head=self.from_head
            )
            from_allocation.revised_allocation -= self.amount
            from_allocation.save(update_fields=['revised_allocation', 'updated_at'])
            
            # Increase to_head allocation (create if doesn't exist)
            to_allocation, created = BudgetAllocation.objects.select_for_update().get_or_create(
                organization=self.organization,
                fiscal_year=self.fiscal_year,
                budget_head=self.to_head,
                defaults={
                    'original_allocation': Decimal('0.00'),
                    'revised_allocation': self.amount,
                }
            )
            if not created:
                to_allocation.revised_allocation += self.amount
                to_allocation.save(update_fields=['revised_allocation', 'updated_at'])
            
            self.status = ReappropriationStatus.APPROVED
            self.approved_by = user
            self.approved_at = timezone.now()
            self.save(update_fields=['status', 'approved_by', 'approved_at', 'updated_at'])
