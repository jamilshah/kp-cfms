"""
-------------------------------------------------------------------------
System: KP-CFMS (Computerized Financial Management System)
Client: Local Government Department, Khyber Pakhtunkhwa
Team Lead: Jamil Shah
Developers: Ali Asghar, Akhtar Munir and Zarif Khan
Description: Business logic services for the budgeting module.
             Implements Hard Budget Constraints as per TMA Budget Rules 2016.
-------------------------------------------------------------------------
"""
from decimal import Decimal
from typing import Dict, Tuple, Optional, List
from datetime import date
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.core.exceptions import (
    ReserveViolationException,
    BudgetLockedException,
    FiscalYearInactiveException,
    BudgetExceededException,
    SanctionedPostLinkException,
)


# Constants
RESERVE_PERCENTAGE = Decimal('0.02')  # 2% contingency reserve
MAX_RECEIPT_GROWTH = Decimal('0.15')  # 15% maximum growth on receipts
QUARTERLY_RELEASE_PERCENTAGE = Decimal('0.25')  # 25% per quarter


def validate_receipt_growth(
    previous_year_actual: Decimal,
    next_year_estimate: Decimal,
    max_growth: Decimal = MAX_RECEIPT_GROWTH
) -> Tuple[bool, Optional[str]]:
    """
    Validate that receipt estimate does not exceed maximum allowed growth.
    
    As per TMA Budget Rules 2016, next year estimates cannot exceed
    previous year actuals by more than 15% without justification.
    
    Args:
        previous_year_actual: Last year's actual receipt amount.
        next_year_estimate: Proposed estimate for next year.
        max_growth: Maximum allowed growth percentage (default 15%).
        
    Returns:
        Tuple of (is_valid, error_message).
        If valid, error_message is None.
    """
    if previous_year_actual <= Decimal('0.00'):
        # No previous data, allow any amount
        return True, None
    
    max_allowed = previous_year_actual * (1 + max_growth)
    
    if next_year_estimate > max_allowed:
        growth_pct = ((next_year_estimate - previous_year_actual) 
                      / previous_year_actual * 100)
        return False, (
            f"Receipt estimate exceeds 15% growth limit. "
            f"Previous year: Rs {previous_year_actual:,.2f}, "
            f"Maximum allowed: Rs {max_allowed:,.2f}, "
            f"Proposed: Rs {next_year_estimate:,.2f} ({growth_pct:.1f}% growth). "
            f"Please provide justification in remarks."
        )
    
    return True, None


def validate_reserve_requirement(
    total_receipts: Decimal,
    contingency_allocation: Decimal,
    reserve_percentage: Decimal = RESERVE_PERCENTAGE
) -> Tuple[bool, Optional[str]]:
    """
    Validate that contingency reserve meets minimum requirement.
    
    As per TMA Budget Rules 2016, contingency must be at least 2%
    of total receipts.
    
    Args:
        total_receipts: Total budgeted receipts.
        contingency_allocation: Amount allocated to contingency head.
        reserve_percentage: Minimum reserve percentage (default 2%).
        
    Returns:
        Tuple of (is_valid, error_message).
        
    Raises:
        ReserveViolationException: If reserve is insufficient.
    """
    required_reserve = total_receipts * reserve_percentage
    
    if contingency_allocation < required_reserve:
        error_msg = (
            f"Contingency reserve is insufficient. "
            f"Required: Rs {required_reserve:,.2f} (2% of Rs {total_receipts:,.2f}), "
            f"Allocated: Rs {contingency_allocation:,.2f}. "
            f"Deficit: Rs {required_reserve - contingency_allocation:,.2f}"
        )
        return False, error_msg
    
    return True, None


def validate_zero_deficit(
    total_receipts: Decimal,
    total_expenditure: Decimal
) -> Tuple[bool, Optional[str]]:
    """
    Validate that budget does not have a deficit.
    
    Total expenditure must not exceed total receipts
    (balanced or surplus budget required).
    
    Args:
        total_receipts: Total budgeted receipts.
        total_expenditure: Total budgeted expenditure.
        
    Returns:
        Tuple of (is_valid, error_message).
    """
    if total_expenditure > total_receipts:
        deficit = total_expenditure - total_receipts
        return False, (
            f"Budget has a deficit. "
            f"Total Receipts: Rs {total_receipts:,.2f}, "
            f"Total Expenditure: Rs {total_expenditure:,.2f}. "
            f"Deficit: Rs {deficit:,.2f}. "
            f"Please reduce expenditure or increase receipts."
        )
    
    return True, None


def validate_salary_linkage(fiscal_year_id: int) -> Tuple[bool, List[str]]:
    """
    Validate that all salary budget heads are linked to sanctioned posts.
    
    As per TMA Budget Rules 2016, salary heads (A01*) must have
    corresponding entries in the Schedule of Establishment.
    
    Args:
        fiscal_year_id: ID of the fiscal year to validate.
        
    Returns:
        Tuple of (is_valid, list_of_errors).
    """
    from apps.budgeting.models import BudgetAllocation, ScheduleOfEstablishment
    
    errors: List[str] = []
    
    # Get all salary allocations
    salary_allocations = BudgetAllocation.objects.filter(
        fiscal_year_id=fiscal_year_id,
        budget_head__pifra_object__startswith='A01',
        original_allocation__gt=Decimal('0.00')
    ).select_related('budget_head')
    
    # Get all establishment entries
    establishment_heads = set(
        ScheduleOfEstablishment.objects.filter(
            fiscal_year_id=fiscal_year_id
        ).values_list('budget_head_id', flat=True)
    )
    
    for allocation in salary_allocations:
        if allocation.budget_head_id not in establishment_heads:
            errors.append(
                f"Salary head {allocation.budget_head.tma_sub_object} "
                f"({allocation.budget_head.tma_description}) has allocation of "
                f"Rs {allocation.original_allocation:,.2f} but no linked "
                f"sanctioned posts in Schedule of Establishment."
            )
    
    return len(errors) == 0, errors


def validate_establishment_vs_budget(fiscal_year_id: int) -> Tuple[bool, List[str]]:
    """
    Cross-validate establishment costs against budget allocations.
    
    Args:
        fiscal_year_id: ID of the fiscal year to validate.
        
    Returns:
        Tuple of (is_valid, list_of_warnings).
    """
    from apps.budgeting.models import BudgetAllocation, ScheduleOfEstablishment
    from django.db.models import Sum
    
    warnings: List[str] = []
    
    # Group establishment costs by budget head
    establishment_costs = ScheduleOfEstablishment.objects.filter(
        fiscal_year_id=fiscal_year_id
    ).values('budget_head_id').annotate(
        total_cost=Sum('annual_salary') * Sum('sanctioned_posts')
    )
    
    for entry in establishment_costs:
        try:
            allocation = BudgetAllocation.objects.get(
                fiscal_year_id=fiscal_year_id,
                budget_head_id=entry['budget_head_id']
            )
            if entry['total_cost'] > allocation.original_allocation:
                warnings.append(
                    f"Establishment cost for {allocation.budget_head.tma_sub_object} "
                    f"(Rs {entry['total_cost']:,.2f}) exceeds budget allocation "
                    f"(Rs {allocation.original_allocation:,.2f})."
                )
        except BudgetAllocation.DoesNotExist:
            warnings.append(
                f"No budget allocation found for establishment budget head "
                f"ID {entry['budget_head_id']}."
            )
    
    return len(warnings) == 0, warnings


def generate_sae_number(fiscal_year_name: str) -> str:
    """
    Generate unique SAE number for a fiscal year.
    
    Format: SAE-YYYY-XXXX where YYYY is the start year
    and XXXX is a sequential number.
    
    Args:
        fiscal_year_name: Fiscal year name (e.g., "2026-27").
        
    Returns:
        Unique SAE number string.
    """
    from apps.budgeting.models import SAERecord
    
    year_prefix = fiscal_year_name.split('-')[0]
    
    # Count existing SAEs for this year
    count = SAERecord.objects.filter(
        sae_number__startswith=f'SAE-{year_prefix}'
    ).count()
    
    return f"SAE-{year_prefix}-{count + 1:04d}"


@transaction.atomic
def finalize_budget(fiscal_year_id: int, approver_id: int) -> Dict:
    """
    Finalize budget and generate SAE (Schedule of Authorized Expenditure).
    
    This function:
    1. Validates all budget rules (reserve, deficit, salary linkage)
    2. Locks the fiscal year
    3. Creates the SAE record
    4. Initializes quarterly release schedule
    
    Args:
        fiscal_year_id: ID of the fiscal year to finalize.
        approver_id: ID of the TMO approving the budget.
        
    Returns:
        Dictionary with SAE details and validation results.
        
    Raises:
        FiscalYearInactiveException: If fiscal year is not active.
        BudgetLockedException: If budget is already locked.
        ReserveViolationException: If reserve requirement not met.
    """
    from apps.budgeting.models import (
        FiscalYear, SAERecord, QuarterlyRelease, ReleaseQuarter
    )
    from apps.users.models import CustomUser
    
    # Lock the fiscal year record for update
    fiscal_year = FiscalYear.objects.select_for_update().get(id=fiscal_year_id)
    approver = CustomUser.objects.get(id=approver_id)
    
    # Check if budget can be finalized
    if fiscal_year.is_locked:
        raise BudgetLockedException(
            f"Budget for {fiscal_year.year_name} is already locked."
        )
    
    if not fiscal_year.is_active:
        raise FiscalYearInactiveException(
            f"Fiscal year {fiscal_year.year_name} is not active for budget entry."
        )
    
    # Calculate totals
    total_receipts = fiscal_year.get_total_receipts()
    total_expenditure = fiscal_year.get_total_expenditure()
    contingency = fiscal_year.get_contingency_amount()
    
    # Run validations
    validation_results = {
        'reserve_check': None,
        'deficit_check': None,
        'salary_linkage': None,
        'establishment_check': None,
    }
    
    # 1. Reserve requirement
    is_valid, error = validate_reserve_requirement(total_receipts, contingency)
    if not is_valid:
        raise ReserveViolationException(error)
    validation_results['reserve_check'] = {'valid': True, 'required': total_receipts * RESERVE_PERCENTAGE}
    
    # 2. Zero deficit
    is_valid, error = validate_zero_deficit(total_receipts, total_expenditure)
    if not is_valid:
        raise BudgetExceededException(error)
    validation_results['deficit_check'] = {'valid': True, 'surplus': total_receipts - total_expenditure}
    
    # 3. Salary linkage (warning only, not blocking)
    is_valid, errors = validate_salary_linkage(fiscal_year_id)
    validation_results['salary_linkage'] = {'valid': is_valid, 'warnings': errors}
    
    # 4. Establishment vs budget (warning only)
    is_valid, warnings = validate_establishment_vs_budget(fiscal_year_id)
    validation_results['establishment_check'] = {'valid': is_valid, 'warnings': warnings}
    
    # Generate SAE number
    sae_number = generate_sae_number(fiscal_year.year_name)
    
    # Create SAE record
    sae_record = SAERecord.objects.create(
        fiscal_year=fiscal_year,
        sae_number=sae_number,
        total_receipts=total_receipts,
        total_expenditure=total_expenditure,
        contingency_reserve=contingency,
        approved_by=approver
    )
    
    # NEW: Convert PROPOSED posts (SNE) to SANCTIONED
    # This officially sanctions the new posts requested in this budget
    from apps.budgeting.models import EstablishmentStatus, ScheduleOfEstablishment
    
    proposed_posts = ScheduleOfEstablishment.objects.filter(
        fiscal_year=fiscal_year,
        establishment_status=EstablishmentStatus.PROPOSED
    )
    
    for post in proposed_posts:
        # Calls the model method to convert and clear justification
        post.convert_to_sanctioned()
    
    # Lock fiscal year
    fiscal_year.lock_budget(sae_number)
    
    # Initialize quarterly releases
    release_dates = [
        (ReleaseQuarter.Q1, date(fiscal_year.start_date.year, 7, 1)),
        (ReleaseQuarter.Q2, date(fiscal_year.start_date.year, 10, 1)),
        (ReleaseQuarter.Q3, date(fiscal_year.start_date.year + 1, 1, 1)),
        (ReleaseQuarter.Q4, date(fiscal_year.start_date.year + 1, 4, 1)),
    ]
    
    for quarter, release_date in release_dates:
        QuarterlyRelease.objects.create(
            fiscal_year=fiscal_year,
            quarter=quarter,
            release_date=release_date,
            is_released=False,
            created_by=approver,
            updated_by=approver
        )
    
    return {
        'sae_number': sae_number,
        'sae_record_id': sae_record.id,
        'total_receipts': str(total_receipts),
        'total_expenditure': str(total_expenditure),
        'contingency_reserve': str(contingency),
        'surplus': str(total_receipts - total_expenditure),
        'validation_results': validation_results,
    }


@transaction.atomic
def process_quarterly_release(
    fiscal_year_id: int,
    quarter: str,
    processor_id: int
) -> Dict:
    """
    Process quarterly fund release (25% of non-salary/development budgets).
    
    Args:
        fiscal_year_id: ID of the fiscal year.
        quarter: Quarter code (Q1, Q2, Q3, Q4).
        processor_id: ID of the user processing the release.
        
    Returns:
        Dictionary with release details.
    """
    from apps.budgeting.models import (
        FiscalYear, BudgetAllocation, QuarterlyRelease
    )
    from apps.users.models import CustomUser
    
    fiscal_year = FiscalYear.objects.get(id=fiscal_year_id)
    processor = CustomUser.objects.get(id=processor_id)
    
    if not fiscal_year.is_locked:
        raise FiscalYearInactiveException(
            f"Budget for {fiscal_year.year_name} must be finalized before releasing funds."
        )
    
    # Get or update quarterly release record
    quarterly_release = QuarterlyRelease.objects.select_for_update().get(
        fiscal_year_id=fiscal_year_id,
        quarter=quarter
    )
    
    if quarterly_release.is_released:
        raise BudgetLockedException(
            f"Quarter {quarter} funds have already been released."
        )
    
    total_released = Decimal('0.00')
    
    # Release 25% of non-salary allocations
    allocations = BudgetAllocation.objects.filter(
        fiscal_year_id=fiscal_year_id
    ).exclude(
        # Exclude salary heads (A01) - these are released in full
        budget_head__pifra_object__startswith='A01'
    ).select_for_update()
    
    for allocation in allocations:
        release_amount = allocation.revised_allocation * QUARTERLY_RELEASE_PERCENTAGE
        allocation.released_amount += release_amount
        allocation.save(update_fields=['released_amount', 'updated_at'])
        total_released += release_amount
    
    # Salary heads get full release in Q1
    if quarter == 'Q1':
        salary_allocations = BudgetAllocation.objects.filter(
            fiscal_year_id=fiscal_year_id,
            budget_head__pifra_object__startswith='A01'
        ).select_for_update()
        
        for allocation in salary_allocations:
            allocation.released_amount = allocation.revised_allocation
            allocation.save(update_fields=['released_amount', 'updated_at'])
            total_released += allocation.revised_allocation
    
    # Update quarterly release record
    quarterly_release.is_released = True
    quarterly_release.total_amount = total_released
    quarterly_release.updated_by = processor
    quarterly_release.save()
    
    return {
        'quarter': quarter,
        'total_released': str(total_released),
        'release_date': str(quarterly_release.release_date),
        'processed_by': processor.get_full_name(),
    }


def check_budget_availability(
    budget_head_id: int,
    fiscal_year_id: int,
    amount: Decimal
) -> Tuple[bool, Optional[str], Optional[Decimal]]:
    """
    Check if sufficient budget is available for a transaction.
    
    This is the core Hard Budget Constraint check used before
    any expenditure is authorized.
    
    Args:
        budget_head_id: ID of the budget head.
        fiscal_year_id: ID of the fiscal year.
        amount: Amount to be spent.
        
    Returns:
        Tuple of (is_available, error_message, available_amount).
    """
    from apps.budgeting.models import BudgetAllocation
    
    try:
        allocation = BudgetAllocation.objects.get(
            budget_head_id=budget_head_id,
            fiscal_year_id=fiscal_year_id
        )
    except BudgetAllocation.DoesNotExist:
        return False, "No budget allocation found for this head.", Decimal('0.00')
    
    available = allocation.get_available_budget()
    
    if amount > available:
        return False, (
            f"Insufficient budget. Available: Rs {available:,.2f}, "
            f"Required: Rs {amount:,.2f}. "
            f"Deficit: Rs {amount - available:,.2f}"
        ), available
    
    return True, None, available
