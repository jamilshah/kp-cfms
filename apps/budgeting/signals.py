"""
-------------------------------------------------------------------------
System: KP-CFMS (Computerized Financial Management System)
Client: Local Government Department, Khyber Pakhtunkhwa
Team Lead: Jamil Shah
Developers: Ali Asghar, Akhtar Munir and Zarif Khan
Description: Django signals for the budgeting module.
             Handles automatic actions on model save/delete.
-------------------------------------------------------------------------
"""
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from apps.budgeting.models import (
    FiscalYear, BudgetAllocation, ScheduleOfEstablishment, BudgetStatus
)


# Signal removed: FiscalYear.is_active field no longer exists
# The logic for active fiscal year is now handled by FiscalYear.get_current_operating_year()
# and is_planning_active / is_revision_active flags.


# DISABLED: FiscalYear doesn't have is_locked or status fields
# This signal was incorrectly referencing fields that don't exist on the model
# @receiver(post_save, sender=FiscalYear)
# def fiscal_year_post_save(sender, instance: FiscalYear, created: bool, **kwargs) -> None:
#     """
#     Post-save signal for FiscalYear.
#     
#     Updates status based on lock state.
#     """
#     if instance.is_locked and instance.status != BudgetStatus.LOCKED:
#         # Use update to avoid recursion
#         FiscalYear.objects.filter(pk=instance.pk).update(
#             status=BudgetStatus.LOCKED
#         )


@receiver(post_save, sender=BudgetAllocation)
def budget_allocation_post_save(
    sender, 
    instance: BudgetAllocation, 
    created: bool, 
    **kwargs
) -> None:
    """
    Post-save signal for BudgetAllocation.
    
    Initializes revised_allocation from original if needed.
    """
    from decimal import Decimal
    
    if created and instance.revised_allocation == Decimal('0.00'):
        if instance.original_allocation > Decimal('0.00'):
            BudgetAllocation.objects.filter(pk=instance.pk).update(
                revised_allocation=instance.original_allocation
            )




