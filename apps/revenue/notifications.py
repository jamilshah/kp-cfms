"""
-------------------------------------------------------------------------
System: KP-CFMS (Computerized Financial Management System)
Client: Local Government Department, Khyber Pakhtunkhwa
Team Lead: Jamil Shah
Developers: Ali Asghar, Akhtar Munir and Zarif Khan
Description: Notification handlers for revenue module events including
             demand creation, payment receipt, overdue reminders, and
             workflow state changes.
-------------------------------------------------------------------------
"""
from typing import List, Optional, Dict
from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.core.mail import send_mail
from django.conf import settings

from apps.revenue.models import RevenueDemand, RevenueCollection, DemandStatus, CollectionStatus
from apps.core.models import Organization
from apps.core.services import NotificationService
from apps.core.models import NotificationCategory


class RevenueNotifications:
    """
    Revenue-specific notification handlers.
    
    Provides methods to send notifications for various revenue events:
    - Demand creation and posting
    - Collection receipt and posting
    - Overdue payment reminders
    - Cancellation notifications
    """
    
    @staticmethod
    def notify_demand_created(demand: RevenueDemand) -> None:
        """
        Send notification when a new demand is created.
        
        Notifies:
        - Finance Officers of the organization
        - Relevant stakeholders
        
        Args:
            demand: The newly created demand
        """
        # Notify finance officers
        finance_officers = demand.organization.users.filter(
            role='FINANCE_OFFICER',
            is_active=True
        )
        
        for officer in finance_officers:
            NotificationService.send_notification(
                recipient=officer,
                title=_('New Revenue Demand Created'),
                message=_(
                    f"Demand {demand.challan_no} for Rs. {demand.amount:,.2f} "
                    f"created for {demand.payer.name}."
                ),
                link=f"/revenue/demands/{demand.pk}/",
                category=NotificationCategory.INFO,
                icon='bi-receipt'
            )
    
    @staticmethod
    def notify_demand_posted(demand: RevenueDemand) -> None:
        """
        Send notification when a demand is posted to GL.
        
        Args:
            demand: The posted demand
        """
        # Notify finance officers
        finance_officers = demand.organization.users.filter(
            role='FINANCE_OFFICER',
            is_active=True
        )
        
        for officer in finance_officers:
            NotificationService.send_notification(
                recipient=officer,
                title=_('Demand Posted to GL'),
                message=_(
                    f"Demand {demand.challan_no} of Rs. {demand.amount:,.2f} "
                    f"from {demand.payer.name} has been posted. "
                    f"Voucher: {demand.accrual_voucher.voucher_no if demand.accrual_voucher else 'N/A'}"
                ),
                link=f"/revenue/demands/{demand.pk}/",
                category=NotificationCategory.WORKFLOW,
                icon='bi-check-circle-fill'
            )
        
        # Optionally send email to payer (if email exists)
        if demand.payer.email:
            RevenueNotifications._send_demand_email(demand)
    
    @staticmethod
    def notify_collection_received(collection: RevenueCollection) -> None:
        """
        Send notification when a payment is received.
        
        Args:
            collection: The payment collection
        """
        # Notify finance officers
        finance_officers = collection.organization.users.filter(
            role='FINANCE_OFFICER',
            is_active=True
        )
        
        outstanding = collection.demand.get_outstanding_balance()
        
        for officer in finance_officers:
            NotificationService.send_notification(
                recipient=officer,
                title=_('Payment Received'),
                message=_(
                    f"Receipt {collection.receipt_no}: Rs. {collection.amount_received:,.2f} "
                    f"received from {collection.demand.payer.name} "
                    f"against Challan {collection.demand.challan_no}. "
                    f"Outstanding: Rs. {outstanding:,.2f}"
                ),
                link=f"/revenue/collections/{collection.pk}/",
                category=NotificationCategory.SUCCESS,
                icon='bi-cash-coin'
            )
    
    @staticmethod
    def notify_collection_posted(collection: RevenueCollection) -> None:
        """
        Send notification when a collection is posted to GL.
        
        Args:
            collection: The posted collection
        """
        # Notify finance officers
        finance_officers = collection.organization.users.filter(
            role='FINANCE_OFFICER',
            is_active=True
        )
        
        for officer in finance_officers:
            NotificationService.send_notification(
                recipient=officer,
                title=_('Collection Posted to GL'),
                message=_(
                    f"Receipt {collection.receipt_no} posted. "
                    f"Amount: Rs. {collection.amount_received:,.2f}. "
                    f"Voucher: {collection.receipt_voucher.voucher_no if collection.receipt_voucher else 'N/A'}"
                ),
                link=f"/revenue/collections/{collection.pk}/",
                category=NotificationCategory.WORKFLOW,
                icon='bi-journal-check'
            )
        
        # Send receipt confirmation to payer (if email exists)
        if collection.demand.payer.email:
            RevenueNotifications._send_receipt_email(collection)
    
    @staticmethod
    def notify_demand_cancelled(
        demand: RevenueDemand,
        cancellation_reason: str
    ) -> None:
        """
        Send notification when a demand is cancelled.
        
        Args:
            demand: The cancelled demand
            cancellation_reason: Reason for cancellation
        """
        # Notify finance officers
        finance_officers = demand.organization.users.filter(
            role='FINANCE_OFFICER',
            is_active=True
        )
        
        for officer in finance_officers:
            NotificationService.send_notification(
                recipient=officer,
                title=_('Demand Cancelled'),
                message=_(
                    f"Demand {demand.challan_no} (Rs. {demand.amount:,.2f}) "
                    f"has been cancelled. Reason: {cancellation_reason}"
                ),
                link=f"/revenue/demands/{demand.pk}/",
                category=NotificationCategory.WARNING,
                icon='bi-x-circle'
            )
        
        # Notify demand creator
        if demand.created_by:
            NotificationService.send_notification(
                recipient=demand.created_by,
                title=_('Your Demand Was Cancelled'),
                message=_(
                    f"Demand {demand.challan_no} for {demand.payer.name} "
                    f"has been cancelled. Reason: {cancellation_reason}"
                ),
                link=f"/revenue/demands/{demand.pk}/",
                category=NotificationCategory.WARNING,
                icon='bi-exclamation-triangle'
            )
    
    @staticmethod
    def notify_collection_cancelled(
        collection: RevenueCollection,
        cancellation_reason: str = ''
    ) -> None:
        """
        Send notification when a collection is cancelled.
        
        Args:
            collection: The cancelled collection
            cancellation_reason: Reason for cancellation
        """
        # Notify finance officers
        finance_officers = collection.organization.users.filter(
            role='FINANCE_OFFICER',
            is_active=True
        )
        
        for officer in finance_officers:
            NotificationService.send_notification(
                recipient=officer,
                title=_('Collection Cancelled'),
                message=_(
                    f"Receipt {collection.receipt_no} (Rs. {collection.amount_received:,.2f}) "
                    f"has been cancelled. {cancellation_reason}"
                ),
                link=f"/revenue/collections/{collection.pk}/",
                category=NotificationCategory.WARNING,
                icon='bi-x-circle'
            )
    
    @staticmethod
    def notify_overdue_demands(organization: Organization) -> int:
        """
        Send reminders for overdue demands.
        
        This method should be called by a periodic task (e.g., daily cron job)
        to notify about overdue payments.
        
        Args:
            organization: The organization to check
            
        Returns:
            Number of notifications sent
        """
        today = timezone.now().date()
        
        # Find overdue demands
        overdue_demands = RevenueDemand.objects.filter(
            organization=organization,
            status__in=[DemandStatus.POSTED, DemandStatus.PARTIAL],
            due_date__lt=today
        ).select_related('payer', 'budget_head', 'budget_head__global_head')
        
        notifications_sent = 0
        
        for demand in overdue_demands:
            days_overdue = (today - demand.due_date).days
            outstanding = demand.get_outstanding_balance()
            
            if outstanding <= 0:
                continue
            
            # Send reminder at specific intervals: 1, 7, 15, 30, 60, 90 days
            reminder_days = [1, 7, 15, 30, 60, 90]
            if days_overdue not in reminder_days:
                continue
            
            # Notify finance officers
            finance_officers = organization.users.filter(
                role='FINANCE_OFFICER',
                is_active=True
            )
            
            for officer in finance_officers:
                NotificationService.send_notification(
                    recipient=officer,
                    title=_('Overdue Payment Alert'),
                    message=_(
                        f"Demand {demand.challan_no}: Rs. {outstanding:,.2f} "
                        f"overdue by {days_overdue} days from {demand.payer.name}. "
                        f"Due date was {demand.due_date.strftime('%Y-%m-%d')}."
                    ),
                    link=f"/revenue/demands/{demand.pk}/",
                    category=NotificationCategory.WARNING,
                    icon='bi-exclamation-triangle-fill'
                )
                notifications_sent += 1
            
            # Send email to payer if contact info available
            if demand.payer.email and days_overdue in [7, 30, 60]:
                RevenueNotifications._send_overdue_email(demand, days_overdue)
        
        return notifications_sent
    
    @staticmethod
    def notify_payment_due_soon(organization: Organization, days_ahead: int = 7) -> int:
        """
        Send reminders for upcoming payments.
        
        Notifies about demands that are due within the specified days.
        
        Args:
            organization: The organization to check
            days_ahead: Number of days ahead to check (default: 7)
            
        Returns:
            Number of notifications sent
        """
        today = timezone.now().date()
        due_date_threshold = today + timedelta(days=days_ahead)
        
        # Find demands due soon
        upcoming_demands = RevenueDemand.objects.filter(
            organization=organization,
            status__in=[DemandStatus.POSTED, DemandStatus.PARTIAL],
            due_date__gte=today,
            due_date__lte=due_date_threshold
        ).select_related('payer', 'budget_head', 'budget_head__global_head')
        
        notifications_sent = 0
        
        for demand in upcoming_demands:
            outstanding = demand.get_outstanding_balance()
            if outstanding <= 0:
                continue
            
            days_until_due = (demand.due_date - today).days
            
            # Send email to payer
            if demand.payer.email:
                RevenueNotifications._send_due_soon_email(demand, days_until_due)
                notifications_sent += 1
        
        return notifications_sent
    
    # =================================================================
    # Private helper methods for email notifications
    # =================================================================
    
    @staticmethod
    def _send_demand_email(demand: RevenueDemand) -> bool:
        """
        Send email to payer about new demand.
        
        Args:
            demand: The demand to notify about
            
        Returns:
            True if email sent successfully
        """
        try:
            subject = f"Revenue Demand - Challan {demand.challan_no}"
            message = f"""
Dear {demand.payer.name},

A revenue demand has been issued to you:

Challan Number: {demand.challan_no}
Organization: {demand.organization.name}
Revenue Head: {demand.budget_head.global_head.name}
Amount: Rs. {demand.amount:,.2f}
Issue Date: {demand.issue_date.strftime('%B %d, %Y')}
Due Date: {demand.due_date.strftime('%B %d, %Y')}
Period: {demand.period_description or 'N/A'}

Please make payment before the due date to avoid penalties.

Thank you,
{demand.organization.name}
            """
            
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[demand.payer.email],
                fail_silently=True
            )
            return True
        except Exception:
            return False
    
    @staticmethod
    def _send_receipt_email(collection: RevenueCollection) -> bool:
        """Send email receipt to payer."""
        try:
            subject = f"Payment Receipt - {collection.receipt_no}"
            message = f"""
Dear {collection.demand.payer.name},

Your payment has been received and recorded:

Receipt Number: {collection.receipt_no}
Receipt Date: {collection.receipt_date.strftime('%B %d, %Y')}
Challan Number: {collection.demand.challan_no}
Amount Received: Rs. {collection.amount_received:,.2f}
Payment Method: {collection.get_instrument_type_display()}
Instrument No: {collection.instrument_no or 'N/A'}
Bank Account: {collection.bank_account.title}

Outstanding Balance: Rs. {collection.demand.get_outstanding_balance():,.2f}

Thank you for your payment.

{collection.organization.name}
            """
            
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[collection.demand.payer.email],
                fail_silently=True
            )
            return True
        except Exception:
            return False
    
    @staticmethod
    def _send_overdue_email(demand: RevenueDemand, days_overdue: int) -> bool:
        """Send overdue payment email to payer."""
        try:
            outstanding = demand.get_outstanding_balance()
            
            subject = f"Overdue Payment Notice - Challan {demand.challan_no}"
            message = f"""
Dear {demand.payer.name},

This is a reminder that your payment is overdue:

Challan Number: {demand.challan_no}
Organization: {demand.organization.name}
Revenue Head: {demand.budget_head.global_head.name}
Total Amount: Rs. {demand.amount:,.2f}
Outstanding Balance: Rs. {outstanding:,.2f}
Due Date: {demand.due_date.strftime('%B %d, %Y')}
Days Overdue: {days_overdue}

Please make payment immediately to avoid further penalties.

For inquiries, please contact:
{demand.organization.name}

Thank you,
Finance Department
            """
            
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[demand.payer.email],
                fail_silently=True
            )
            return True
        except Exception:
            return False
    
    @staticmethod
    def _send_due_soon_email(demand: RevenueDemand, days_until_due: int) -> bool:
        """Send payment due soon email to payer."""
        try:
            outstanding = demand.get_outstanding_balance()
            
            subject = f"Payment Due Soon - Challan {demand.challan_no}"
            message = f"""
Dear {demand.payer.name},

This is a friendly reminder that your payment is due soon:

Challan Number: {demand.challan_no}
Organization: {demand.organization.name}
Revenue Head: {demand.budget_head.global_head.name}
Outstanding Balance: Rs. {outstanding:,.2f}
Due Date: {demand.due_date.strftime('%B %d, %Y')} ({days_until_due} days from now)

Please make payment before the due date.

Thank you,
{demand.organization.name}
            """
            
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[demand.payer.email],
                fail_silently=True
            )
            return True
        except Exception:
            return False


# =============================================================================
# Management Command Helper
# =============================================================================

def send_daily_overdue_reminders() -> Dict[str, int]:
    """
    Send overdue reminders for all organizations.
    
    This function should be called by a Django management command
    or Celery periodic task.
    
    Returns:
        Dictionary mapping organization names to notification counts
    """
    from apps.core.models import Organization
    
    results = {}
    
    for org in Organization.objects.filter(is_active=True):
        count = RevenueNotifications.notify_overdue_demands(org)
        results[org.name] = count
    
    return results
