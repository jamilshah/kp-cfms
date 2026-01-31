"""
-------------------------------------------------------------------------
System: KP-CFMS (Computerized Financial Management System)
Client: Local Government Department, Khyber Pakhtunkhwa
Team Lead: Jamil Shah
Developers: Ali Asghar, Akhtar Munir and Zarif Khan
Description: Core services for notification management and other
             shared business logic.
-------------------------------------------------------------------------
"""
from typing import Optional, List
from django.db import transaction
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

from apps.core.models import Notification, NotificationCategory

User = get_user_model()


class NotificationService:
    """
    Service class for managing notifications.
    
    Provides methods to send notifications to users and query
    notification statistics.
    """
    
    @staticmethod
    @transaction.atomic
    def send_notification(
        recipient,
        title: str,
        message: str,
        link: str = '',
        category: str = NotificationCategory.WORKFLOW,
        icon: str = 'bi-bell'
    ) -> Notification:
        """
        Send a notification to a user.
        
        Args:
            recipient: CustomUser instance who should receive the notification.
            title: Short notification title.
            message: Detailed notification message.
            link: Optional URL to the document or page.
            category: Notification category (WORKFLOW, SYSTEM, ALERT).
            icon: Bootstrap icon class (default: 'bi-bell').
        
        Returns:
            The created Notification instance.
        
        Example:
            >>> from apps.core.services import NotificationService
            >>> NotificationService.send_notification(
            ...     recipient=accountant,
            ...     title="Bill #105 Pending Audit",
            ...     message="Bill submitted by Dealing Assistant requires your review.",
            ...     link="/expenditure/bills/105/",
            ...     category=NotificationCategory.WORKFLOW,
            ...     icon='bi-file-earmark-text'
            ... )
        """
        notification = Notification.objects.create(
            recipient=recipient,
            title=title,
            message=message,
            link=link,
            category=category,
            icon=icon
        )
        return notification
    
    @staticmethod
    def send_bulk_notification(
        recipients: List,
        title: str,
        message: str,
        link: str = '',
        category: str = NotificationCategory.WORKFLOW,
        icon: str = 'bi-bell'
    ) -> List[Notification]:
        """
        Send the same notification to multiple recipients.
        
        Args:
            recipients: List of CustomUser instances.
            title: Short notification title.
            message: Detailed notification message.
            link: Optional URL to the document or page.
            category: Notification category.
            icon: Bootstrap icon class.
        
        Returns:
            List of created Notification instances.
        """
        notifications = []
        for recipient in recipients:
            notification = NotificationService.send_notification(
                recipient=recipient,
                title=title,
                message=message,
                link=link,
                category=category,
                icon=icon
            )
            notifications.append(notification)
        return notifications
    
    @staticmethod
    def get_unread_count(user) -> int:
        """
        Get count of unread notifications for a user.
        
        Args:
            user: CustomUser instance.
        
        Returns:
            Count of unread notifications.
        """
        return Notification.objects.filter(
            recipient=user,
            is_read=False
        ).count()
    
    @staticmethod
    def get_recent_notifications(user, limit: int = 10):
        """
        Get recent notifications for a user.
        
        Args:
            user: CustomUser instance.
            limit: Maximum number of notifications to return (default: 10).
        
        Returns:
            QuerySet of recent notifications.
        """
        return Notification.objects.filter(
            recipient=user
        ).order_by('-created_at')[:limit]
    
    @staticmethod
    @transaction.atomic
    def mark_all_as_read(user) -> int:
        """
        Mark all notifications for a user as read.
        
        Args:
            user: CustomUser instance.
        
        Returns:
            Number of notifications marked as read.
        """
        return Notification.objects.filter(
            recipient=user,
            is_read=False
        ).update(is_read=True)
    
    @staticmethod
    @transaction.atomic
    def delete_old_notifications(days: int = 90) -> int:
        """
        Delete notifications older than specified days.
        
        Args:
            days: Number of days to keep notifications (default: 90).
        
        Returns:
            Number of notifications deleted.
        """
        from django.utils import timezone
        from datetime import timedelta
        
        cutoff_date = timezone.now() - timedelta(days=days)
        count, _ = Notification.objects.filter(
            created_at__lt=cutoff_date
        ).delete()
        return count


# Convenience function for quick access
def send_notification(
    recipient,
    title: str,
    message: str,
    link: str = '',
    category: str = NotificationCategory.WORKFLOW,
    icon: str = 'bi-bell'
) -> Notification:
    """
    Convenience function to send a notification.
    
    This is a shortcut to NotificationService.send_notification().
    """
    return NotificationService.send_notification(
        recipient=recipient,
        title=title,
        message=message,
        link=link,
        category=category,
        icon=icon
    )
