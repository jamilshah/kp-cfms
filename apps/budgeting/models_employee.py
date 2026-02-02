"""
-------------------------------------------------------------------------
System: KP-CFMS (Computerized Financial Management System)
Client: Local Government Department, Khyber Pakhtunkhwa
Team Lead: Jamil Shah
Developers: Ali Asghar, Akhtar Munir and Zarif Khan
Description: BudgetEmployee model for employee-wise budget estimation.
             Implements KP Government CFMS salary calculation standards:
             - Running Basic with increments
             - HRA as fixed slab (BPS + city category)
             - Fixed Conveyance and Medical allowances
             - ARA as percentage on Running Basic
             - DRA as fixed amount per employee
-------------------------------------------------------------------------
"""
from decimal import Decimal
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.translation import gettext_lazy as _

from apps.core.mixins import TimeStampedMixin


# ============================================================================
# ALLOWANCE CONFIGURATION CONSTANTS (KP Government Standards)
# ============================================================================

# HRA Slabs by BPS and City Category
HRA_SLABS = {
    'LARGE': {  # Large Cities (Peshawar, Islamabad, etc.)
        (1, 5): Decimal('2000.00'),
        (6, 10): Decimal('3000.00'),
        (11, 15): Decimal('4500.00'),
        (16, 17): Decimal('6500.00'),
        (18, 19): Decimal('9000.00'),
        (20, 22): Decimal('12000.00'),
    },
    'OTHER': {  # Other Cities / Towns
        (1, 5): Decimal('1500.00'),
        (6, 10): Decimal('2000.00'),
        (11, 15): Decimal('3000.00'),
        (16, 17): Decimal('4500.00'),
        (18, 19): Decimal('6000.00'),
        (20, 22): Decimal('8000.00'),
    }
}

# Conveyance Allowance Slabs by BPS (Fixed, not percentage-based)
CONVEYANCE_SLABS = {
    (1, 4): Decimal('1000.00'),
    (5, 10): Decimal('2000.00'),
    (11, 15): Decimal('3000.00'),
    (16, 17): Decimal('5000.00'),
    (18, 22): Decimal('7000.00'),
}

# Medical Allowance Slabs by BPS (Fixed, not percentage-based)
MEDICAL_SLABS = {
    (1, 15): Decimal('1500.00'),
    (16, 17): Decimal('3000.00'),
    (18, 22): Decimal('5000.00'),
}

# ARA Percentage (Allowance, Relief & Adjustment - percentage-based on Running Basic)
ARA_PERCENTAGE = Decimal('0.22')  # 22% of Running Basic (adjust as per latest notification)

CITY_CATEGORIES = [
    ('LARGE', 'Large Cities'),
    ('OTHER', 'Other Cities / Towns'),
]

BPS_CHOICES = [(i, f'BPS-{i}') for i in range(1, 23)]


# ============================================================================
# UTILITY FUNCTIONS FOR SALARY CALCULATIONS
# ============================================================================

def get_running_basic(min_basic: Decimal, annual_increment: Decimal, max_basic: Decimal, 
                     increments_earned: int) -> Decimal:
    """
    Calculate Running Basic = Min Basic + (Annual Increment × Increments Earned)
    Capped at Max Basic.
    
    Args:
        min_basic: Initial basic pay
        annual_increment: Annual increment amount
        max_basic: Maximum basic pay
        increments_earned: Number of annual increments earned
    
    Returns:
        Running Basic salary (capped at max_basic)
    """
    running = min_basic + (annual_increment * increments_earned)
    return min(running, max_basic)


def get_hra(bps: int, city_category: str, is_govt_accommodation: bool, 
            is_house_hiring: bool) -> Decimal:
    """
    Calculate HRA based on BPS, city category, and eligibility.
    
    Eligibility Conditions (ALL must be true):
    - NOT occupying government accommodation
    - NOT drawing house hiring benefit
    - City category allows HRA
    
    Args:
        bps: BPS grade (1-22)
        city_category: 'LARGE' or 'OTHER'
        is_govt_accommodation: True if employee has govt accommodation
        is_house_hiring: True if employee is drawing house hiring benefit
    
    Returns:
        HRA amount (0 if ineligible)
    """
    # Check eligibility
    if is_govt_accommodation or is_house_hiring:
        return Decimal('0.00')
    
    if city_category not in HRA_SLABS:
        return Decimal('0.00')
    
    # Find matching slab
    for (min_bps, max_bps), amount in HRA_SLABS[city_category].items():
        if min_bps <= bps <= max_bps:
            return amount
    
    return Decimal('0.00')


def get_conveyance(bps: int) -> Decimal:
    """
    Calculate fixed Conveyance Allowance based on BPS.
    Not linked to basic pay, not affected by increments.
    
    Args:
        bps: BPS grade (1-22)
    
    Returns:
        Conveyance allowance amount
    """
    for (min_bps, max_bps), amount in CONVEYANCE_SLABS.items():
        if min_bps <= bps <= max_bps:
            return amount
    return Decimal('0.00')


def get_medical(bps: int) -> Decimal:
    """
    Calculate fixed Medical Allowance based on BPS.
    Not linked to basic pay, not incrementable.
    
    Args:
        bps: BPS grade (1-22)
    
    Returns:
        Medical allowance amount
    """
    for (min_bps, max_bps), amount in MEDICAL_SLABS.items():
        if min_bps <= bps <= max_bps:
            return amount
    return Decimal('0.00')


def get_ara_2023(running_basic: Decimal, bps: int) -> Decimal:
    """
    Calculate ARA 2023 based on BPS level.
    - BPS 1-16: 35% of Running Basic
    - BPS 17-22: 30% of Running Basic
    
    Args:
        running_basic: Current Running Basic salary
        bps: BPS grade (1-22)
    
    Returns:
        ARA 2023 amount
    """
    if bps <= 16:
        percentage = Decimal('0.35')
    else:
        percentage = Decimal('0.30')
    return (running_basic * percentage).quantize(Decimal('0.01'))


def get_ara_2024(running_basic: Decimal, bps: int) -> Decimal:
    """
    Calculate ARA 2024 based on BPS level.
    - BPS 1-16: 25% of Running Basic
    - BPS 17-22: 20% of Running Basic
    
    Args:
        running_basic: Current Running Basic salary
        bps: BPS grade (1-22)
    
    Returns:
        ARA 2024 amount
    """
    if bps <= 16:
        percentage = Decimal('0.25')
    else:
        percentage = Decimal('0.20')
    return (running_basic * percentage).quantize(Decimal('0.01'))


def get_ara_2025(running_basic: Decimal) -> Decimal:
    """
    Calculate ARA 2025 for all BPS levels.
    - All BPS: 10% of Running Basic
    
    Args:
        running_basic: Current Running Basic salary
    
    Returns:
        ARA 2025 amount
    """
    return (running_basic * Decimal('0.10')).quantize(Decimal('0.01'))


def get_ara_2022_fallback(bps: int) -> Decimal:
    """
    Fallback calculation for ARA 2022 (new entrant case).
    Assumes 15% of Minimum Basic Pay for the given BPS in 2017 scale.
    
    Note: This requires BPSSalaryScale data. In practice, should be called 
    with the actual basic_pay_min from BPSSalaryScale.
    
    Args:
        bps: BPS grade (1-22)
    
    Returns:
        Estimated ARA 2022 amount (15% of min basic)
    """
    # In actual usage, pass the min_basic value directly
    # This is a placeholder - the actual logic will be in the model method
    return Decimal('0.00')


class BudgetEmployee(TimeStampedMixin):
    """
    Individual employee record with direct department and function assignment.
    
    KP Government CFMS Compliant Salary Structure:
    - Stores configuration and eligibility data only
    - All calculations are derived from configuration
    - Supports Running Basic, HRA, Conveyance, Medical, ARA, and DRA
    - Direct function assignment for simplified workflow
    
    Attributes:
        fiscal_year: Fiscal year for this employee record
        department: Department where employee works
        function: Function code (determines budget allocation)
        schedule: Optional link to ScheduleOfEstablishment (for reporting)
        name: Employee name
        father_name: Father's name (for official records)
        is_vacant: Whether this is a vacant post placeholder
        bps: BPS grade (1-22)
        city_category: City classification for HRA calculation
        running_basic: Current running basic pay (Min + earned increments)
        is_govt_accommodation: Has government accommodation
        is_house_hiring: Drawing house hiring benefit
        dra_amount: Fixed Disparity Reduction Allowance (from 2017 scale)
        ara_percentage: ARA percentage (configurable per notification)
    """
    
    fiscal_year = models.ForeignKey(
        'budgeting.FiscalYear',
        on_delete=models.PROTECT,
        related_name='budget_employees',
        verbose_name=_('Fiscal Year'),
        help_text=_('Fiscal year for this employee record'),
        null=True,
        blank=True
    )
    
    department = models.ForeignKey(
        'budgeting.Department',
        on_delete=models.PROTECT,
        related_name='budget_employees',
        verbose_name=_('Department'),
        help_text=_('Department where employee works'),
        null=True,
        blank=True
    )
    
    function = models.ForeignKey(
        'finance.FunctionCode',
        on_delete=models.PROTECT,
        related_name='budget_employees',
        verbose_name=_('Function'),
        help_text=_('Function code for this employee (determines budget allocation)'),
        null=True,
        blank=True
    )
    
    schedule = models.ForeignKey(
        'budgeting.ScheduleOfEstablishment',
        on_delete=models.CASCADE,
        related_name='employees',
        verbose_name=_('Schedule Entry'),
        help_text=_('Optional: Link to establishment entry (for reporting only)'),
        null=True,
        blank=True
    )
    
    # ========== PERSONAL DATA ==========
    name = models.CharField(
        max_length=150,
        verbose_name=_('Employee Name'),
        help_text=_('Full name of the employee.')
    )
    father_name = models.CharField(
        max_length=150,
        blank=True,
        verbose_name=_("Father's Name"),
        help_text=_("Father's name for official records.")
    )
    
    designation = models.CharField(
        max_length=150,
        blank=True,
        verbose_name=_('Designation'),
        help_text=_('Job designation/position title.')
    )
    
    date_of_birth = models.DateField(
        null=True,
        blank=True,
        verbose_name=_('Date of Birth'),
        help_text=_('Date of birth for age and retirement calculations.')
    )
    
    qualification = models.CharField(
        max_length=150,
        blank=True,
        verbose_name=_('Qualification'),
        help_text=_('Educational qualification (e.g., B.A., M.A., M.B.B.S.).')
    )
    
    # Status
    is_vacant = models.BooleanField(
        default=False,
        verbose_name=_('Is Vacant Post'),
        help_text=_('Mark as True if this is a placeholder for a vacant position.')
    )
    
    # ========== PAY STRUCTURE (KPGOV CFMS Standard) ==========
    bps = models.PositiveSmallIntegerField(
        choices=BPS_CHOICES,
        default=1,
        verbose_name=_('BPS Grade'),
        help_text=_('Basic Pay Scale grade (1-22).')
    )
    
    running_basic = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name=_('Current Running Basic Pay'),
        help_text=_('Current Running Basic from last pay slip. Used as basis for all ARA calculations.')
    )
    
    # ========== ARA COMPONENTS (Opening Balance Snapshot Approach) ==========
    frozen_ara_2022_input = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        blank=True,
        null=True,
        verbose_name=_('ARA 2022 (From Last Slip)'),
        help_text=_('Frozen amount from employee\'s last pay slip. If left blank, will auto-calculate as 15% of Min BPS.')
    )
    
    ara_2022_auto_calculated = models.BooleanField(
        default=False,
        verbose_name=_('ARA 2022 Auto-Calculated'),
        help_text=_('Flag: True if ARA 2022 was auto-calculated (new entrant). Needs verification.')
    )
    city_category = models.CharField(
        max_length=10,
        choices=CITY_CATEGORIES,
        default='OTHER',
        verbose_name=_('City Category'),
        help_text=_('City classification for HRA calculation (Large/Other).')
    )
    
    is_govt_accommodation = models.BooleanField(
        default=False,
        verbose_name=_('Occupies Government Accommodation'),
        help_text=_('If true, HRA = 0.')
    )
    
    is_house_hiring = models.BooleanField(
        default=False,
        verbose_name=_('Drawing House Hiring Benefit'),
        help_text=_('If true, HRA = 0.')
    )
    
    # ========== FIXED ALLOWANCES ==========
    dra_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name=_('DRA (Disparity Reduction Allowance)'),
        help_text=_('Fixed amount based on 2017 Basic Pay scale. Does NOT increase with increments.')
    )
    
    # ========== BUDGET PROJECTION ==========
    expected_salary_increase_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('100.00'))],
        verbose_name=_('Expected Salary Increase %'),
        help_text=_('Percentage increase for next year budget estimates (0-100). Used for salary projections.')
    )
    
    # ========== METADATA ==========
    joining_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_('Joining Date'),
        help_text=_('Date of joining service.')
    )
    
    remarks = models.TextField(
        blank=True,
        verbose_name=_('Remarks'),
        help_text=_('Any additional notes.')
    )
    
    class Meta:
        verbose_name = _('Budget Employee')
        verbose_name_plural = _('Budget Employees')
        ordering = ['schedule', 'name']
    
    def __str__(self) -> str:
        if self.is_vacant:
            return f"[VACANT] {self.schedule.designation_name}"
        return f"{self.name} (BPS-{self.bps})"
    
    # ========== SALARY CALCULATION METHODS (KPGOV COMPLIANT) ==========
    
    def get_hra(self) -> Decimal:
        """Get HRA for this employee (fixed slab based on BPS + city)."""
        return get_hra(self.bps, self.city_category, self.is_govt_accommodation, self.is_house_hiring)
    
    def get_conveyance(self) -> Decimal:
        """Get Conveyance Allowance (fixed based on BPS)."""
        return get_conveyance(self.bps)
    
    def get_medical(self) -> Decimal:
        """Get Medical Allowance (fixed based on BPS)."""
        return get_medical(self.bps)
    
    def get_ara_2022(self) -> Decimal:
        """
        Get ARA 2022 (Frozen from last pay slip or auto-calculated for new entrants).
        
        If frozen_ara_2022_input is NULL or 0:
        - Assume new entrant
        - Calculate as 15% of minimum basic pay for this BPS
        - Set flag ara_2022_auto_calculated = True
        """
        # If frozen value is provided, use it
        if self.frozen_ara_2022_input and self.frozen_ara_2022_input > 0:
            return self.frozen_ara_2022_input
        
        # Fallback: Auto-calculate as 15% of min basic for this BPS
        from apps.budgeting.models import BPSSalaryScale
        scale = BPSSalaryScale.objects.filter(bps_grade=self.bps).first()
        if scale:
            return (scale.basic_pay_min * Decimal('0.15')).quantize(Decimal('0.01'))
        
        return Decimal('0.00')
    
    def get_ara_2023(self) -> Decimal:
        """Get ARA 2023 (35% or 30% based on BPS)."""
        return get_ara_2023(self.running_basic, self.bps)
    
    def get_ara_2024(self) -> Decimal:
        """Get ARA 2024 (25% or 20% based on BPS)."""
        return get_ara_2024(self.running_basic, self.bps)
    
    def get_ara_2025(self) -> Decimal:
        """Get ARA 2025 (10% for all BPS)."""
        return get_ara_2025(self.running_basic)
    
    def get_ara_total(self) -> Decimal:
        """
        Get Total ARA (sum of 2022, 2023, 2024, 2025).
        This replaces the old get_ara() method.
        """
        return (
            self.get_ara_2022() +
            self.get_ara_2023() +
            self.get_ara_2024() +
            self.get_ara_2025()
        ).quantize(Decimal('0.01'))
    
    def get_dra(self) -> Decimal:
        """Get DRA (fixed amount, stored in database)."""
        return self.dra_amount
    
    @property
    def monthly_allowances(self) -> Decimal:
        """
        Total Monthly Allowances (excluding Running Basic).
        
        Composition (Opening Balance Snapshot Approach):
        = ARA 2022 (frozen from last slip)
        + ARA 2023 (35% or 30% of Running Basic)
        + ARA 2024 (25% or 20% of Running Basic)
        + ARA 2025 (10% of Running Basic)
        + DRA (fixed)
        + HRA (conditional fixed)
        + Conveyance (fixed)
        + Medical (fixed)
        """
        return (
            self.get_ara_total() +
            self.get_dra() +
            self.get_hra() +
            self.get_conveyance() +
            self.get_medical()
        ).quantize(Decimal('0.01'))
    
    @property
    def monthly_gross(self) -> Decimal:
        """
        Gross Salary = Running Basic + All Allowances.
        
        Breakdown:
        = Running Basic
        + ARA
        + DRA
        + HRA (if eligible)
        + Conveyance
        + Medical
        """
        return self.running_basic + self.monthly_allowances
    
    @property
    def annual_cost(self) -> Decimal:
        """
        Annual cost for this employee.
        
        Note: Does NOT include increments beyond Running Basic,
        as Running Basic already incorporates earned increments.
        """
        return (self.monthly_gross * 12).quantize(Decimal('0.01'))
    
    def get_projected_monthly_gross(self) -> Decimal:
        """
        Calculate projected monthly gross salary for next year.
        Applies expected_salary_increase_percentage to current running basic.
        
        Projected Salary = Current Salary × (1 + increase_percentage/100)
        
        Returns:
            Projected monthly gross salary
        """
        if self.expected_salary_increase_percentage <= 0:
            return self.monthly_gross
        
        # Calculate increase multiplier (e.g., 5% = 1.05)
        multiplier = 1 + (self.expected_salary_increase_percentage / 100)
        projected_basic = (self.running_basic * Decimal(str(multiplier))).quantize(Decimal('0.01'))
        
        # Calculate allowances based on projected basic
        # Note: Only ARA changes with running basic; others are fixed
        projected_ara_2023 = (projected_basic * 
            (Decimal('0.35') if self.bps <= 16 else Decimal('0.30'))
        ).quantize(Decimal('0.01'))
        
        projected_ara_2024 = (projected_basic * 
            (Decimal('0.25') if self.bps <= 16 else Decimal('0.20'))
        ).quantize(Decimal('0.01'))
        
        projected_ara_2025 = (projected_basic * Decimal('0.10')).quantize(Decimal('0.01'))
        
        # Total projected allowances (ARA changes, others fixed)
        projected_allowances = (
            self.get_ara_2022() +  # Frozen, unchanged
            projected_ara_2023 +
            projected_ara_2024 +
            projected_ara_2025 +
            self.get_dra() +
            self.get_hra() +
            self.get_conveyance() +
            self.get_medical()
        ).quantize(Decimal('0.01'))
        
        return (projected_basic + projected_allowances).quantize(Decimal('0.01'))
    
    def get_projected_annual_cost(self) -> Decimal:
        """
        Calculate projected annual cost for next year.
        
        Returns:
            Projected annual salary cost (monthly × 12)
        """
        return (self.get_projected_monthly_gross() * 12).quantize(Decimal('0.01'))
    
    def get_salary_breakdown(self) -> dict:
        """
        Get detailed salary breakdown for reporting/auditing.
        Uses Opening Balance Snapshot Approach (year-by-year ARA).
        
        Returns:
            Dictionary with all salary components
        """
        return {
            'running_basic': self.running_basic,
            'ara_2022': self.get_ara_2022(),
            'ara_2022_auto_calculated': self.ara_2022_auto_calculated,
            'ara_2023': self.get_ara_2023(),
            'ara_2024': self.get_ara_2024(),
            'ara_2025': self.get_ara_2025(),
            'ara_total': self.get_ara_total(),
            'dra': self.get_dra(),
            'hra': self.get_hra(),
            'conveyance': self.get_conveyance(),
            'medical': self.get_medical(),
            'total_allowances': self.monthly_allowances,
            'monthly_gross': self.monthly_gross,
            'annual_cost': self.annual_cost,
            'hra_eligibility': {
                'has_govt_accommodation': self.is_govt_accommodation,
                'has_house_hiring': self.is_house_hiring,
                'city_category': self.city_category,
            }
        }
