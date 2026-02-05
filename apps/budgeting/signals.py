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


@receiver(pre_save, sender=FiscalYear)
def fiscal_year_pre_save(sender, instance: FiscalYear, **kwargs) -> None:
    """
    Pre-save signal for FiscalYear.
    
    Ensures only one fiscal year can be active at a time.
    """
    if instance.is_active and instance.pk:
        # Deactivate other fiscal years if this one is being activated
        FiscalYear.objects.exclude(pk=instance.pk).filter(
            is_active=True
        ).update(is_active=False)
    elif instance.is_active:
        # New instance being created as active
        FiscalYear.objects.filter(is_active=True).update(is_active=False)


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




