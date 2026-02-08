"""
Signals for the Finance app.

Handles cache invalidation and other side effects when models are modified.
"""
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache
import logging

logger = logging.getLogger(__name__)


@receiver([post_save, post_delete], sender='finance.BudgetHead')
def invalidate_cache_on_budgethead_change(sender, instance, **kwargs):
    """
    Invalidate budget head caches when a BudgetHead is created, updated, or deleted.
    
    Since we use LocMemCache which doesn't support pattern-based deletion,
    we rely on the 5-minute TTL. For production with Redis, implement
    pattern-based cache invalidation here.
    """
    logger.info(f"BudgetHead changed: {instance.id} - cache will auto-expire in 5 min")
    
    # For Redis, you could do:
    # cache_pattern = f"cfms_*_org:{instance.department.organization_id if instance.department else '*'}_*"
    # cache.delete_pattern(cache_pattern)


@receiver([post_save, post_delete], sender='finance.DepartmentFunctionConfiguration')
def invalidate_cache_on_config_change(sender, instance, **kwargs):
    """
    Invalidate caches when DepartmentFunctionConfiguration changes.
    This is critical as it affects which budget heads are visible.
    """
    logger.info(f"DeptFuncConfig changed: dept={instance.department_id}, func={instance.function_id}")
    
    # For Redis:
    # cache_pattern = f"cfms_*_dept:{instance.department_id}_func:{instance.function_id}_*"
    # cache.delete_pattern(cache_pattern)


@receiver([post_save, post_delete], sender='budgeting.BudgetAllocation')
def invalidate_cache_on_allocation_change(sender, instance, **kwargs):
    """
    Invalidate caches when BudgetAllocation changes.
    This affects budget availability indicators in the search results.
    """
    logger.info(f"BudgetAllocation changed for budget_head={instance.budget_head_id}")
    
    # For Redis:
    # cache_pattern = f"cfms_smart_search_*_org:{instance.organization_id}_*"
    # cache.delete_pattern(cache_pattern)
