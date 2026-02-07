from apps.core.services import NotificationService

def notifications(request):
    """
    Context processor to add unread notification count for the authenticated user.
    """
    if request.user.is_authenticated:
        return {
            'unread_count': NotificationService.get_unread_count(request.user)
        }
    return {'unread_count': 0}

def sidebar_counts(request):
    """
    Context processor to add sidebar counts for pending items.
    """
    if not request.user.is_authenticated:
        return {}
    
    # Check if user has an organization attribute (e.g. from a profile or direct on user if using custom user model)
    # The requirement mentions request.user.organization, ensuring we handle cases where it might be missing
    org = getattr(request.user, 'organization', None)
    if not org:
        return {}
    
    from apps.expenditure.models import Bill, BillStatus
    from apps.revenue.models import RevenueDemand, DemandStatus
    from django.utils import timezone
    
    return {
        'pending_bills_count': Bill.objects.filter(
            organization=org,
            status=BillStatus.SUBMITTED
        ).count(),
        'overdue_demands_count': RevenueDemand.objects.filter(
            organization=org,
            status__in=[DemandStatus.POSTED, DemandStatus.PARTIAL],
            due_date__lt=timezone.now().date()
        ).count(),
    }
