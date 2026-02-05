"""
-------------------------------------------------------------------------
System: KP-CFMS (Computerized Financial Management System)
Client: Local Government Department, Khyber Pakhtunkhwa
Team Lead: Jamil Shah
Developers: Ali Asghar, Akhtar Munir and Zarif Khan
Description: Signal handlers for cache invalidation on voucher posting.
-------------------------------------------------------------------------
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.cache import cache

from apps.finance.models import Voucher


@receiver(post_save, sender=Voucher)
def invalidate_dashboard_cache(sender, instance, **kwargs) -> None:
    """
    Invalidate dashboard cache when a voucher is posted.
    
    This ensures dashboard data stays fresh without requiring
    manual cache clearing.
    
    Args:
        sender: The model class (Voucher).
        instance: The voucher instance that was saved.
        **kwargs: Additional signal arguments.
    """
    # Only invalidate on posted vouchers
    if instance.is_posted:
        # Invalidate cache for the voucher's organization and fiscal year
        if instance.organization_id and instance.fiscal_year_id:
            # Invalidate cache for this specific organization and fiscal year
            cache_key = f'dashboard_stats_{instance.organization_id}_{instance.fiscal_year_id}'
            cache.delete(cache_key)
        
        # Also invalidate provincial summary cache for this fiscal year
        if instance.fiscal_year_id:
            provincial_cache_key = f'dashboard_stats_provincial_{instance.fiscal_year_id}'
            cache.delete(provincial_cache_key)
