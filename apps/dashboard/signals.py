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
        # Invalidate cache for the voucher's organization
        if instance.organization_id:
            # Get all fiscal years for this organization
            from apps.budgeting.models import FiscalYear
            fiscal_years = FiscalYear.objects.filter(
                organization=instance.organization
            ).values_list('id', flat=True)
            
            for fy_id in fiscal_years:
                cache_key = f'dashboard_stats_{instance.organization_id}_{fy_id}'
                cache.delete(cache_key)
        
        # Also invalidate provincial summary cache
        from apps.budgeting.models import FiscalYear
        all_fiscal_years = FiscalYear.objects.values_list('id', flat=True).distinct()
        
        for fy_id in all_fiscal_years:
            provincial_cache_key = f'dashboard_stats_provincial_{fy_id}'
            cache.delete(provincial_cache_key)
