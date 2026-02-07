"""
-------------------------------------------------------------------------
System: KP-CFMS (Computerized Financial Management System)
FIXED VERSION - Signal handlers with proper error handling and transactions
-------------------------------------------------------------------------
"""
import logging
from typing import Optional
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.urls import reverse

from apps.expenditure.models import Bill, BillStatus
from apps.core.services import NotificationService
from apps.core.models import NotificationCategory

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Bill)
def bill_status_change_notification(sender, instance: Bill, created: bool, **kwargs):
    """
    Send notifications when Bill status changes.
    
    FIXED:
    - Added transaction management
    - Added comprehensive error handling
    - Added logging for debugging
    - Graceful failure (doesn't block bill save)
    
    Triggers on:
    - SUBMITTED: Notify Finance Officers/Accountants
    - MARKED_FOR_AUDIT: Notify Audit Officers
    - VERIFIED: Notify TMO/Approvers
    - AUDITED: Notify TMO/Approvers
    - APPROVED: Notify Cashier and Bill Creator
    - RETURNED: Notify Bill Creator
    - REJECTED: Notify Bill Creator
    """
    # Skip if bill is just created (not a status change)
    if created:
        return
    
    try:
        # Wrap in transaction to ensure atomicity
        with transaction.atomic():
            # Get the bill URL for deep linking
            bill_url = reverse('expenditure:bill_detail', kwargs={'pk': instance.pk})
            
            # Route notifications based on status
            if instance.status == BillStatus.SUBMITTED:
                _notify_on_submit(instance, bill_url)
            
            elif instance.status == BillStatus.VERIFIED:
                _notify_on_verified(instance, bill_url)
            
            elif instance.status == BillStatus.MARKED_FOR_AUDIT:
                _notify_on_marked_for_audit(instance, bill_url)
            
            elif instance.status == BillStatus.AUDITED:
                _notify_on_audited(instance, bill_url)
            
            elif instance.status == BillStatus.APPROVED:
                _notify_on_approved(instance, bill_url)
            
            elif instance.status == BillStatus.RETURNED:
                _notify_on_returned(instance, bill_url)
            
            elif instance.status == BillStatus.REJECTED:
                _notify_on_rejected(instance, bill_url)
                
            logger.info(
                f"Notification sent for Bill #{instance.bill_number} status change to {instance.status}",
                extra={
                    'bill_id': instance.id,
                    'bill_number': instance.bill_number,
                    'status': instance.status,
                    'organization': instance.organization.name
                }
            )
    
    except Exception as e:
        # Log the error but don't block bill save
        logger.error(
            f"Failed to send notification for Bill #{instance.bill_number} (ID: {instance.id})",
            exc_info=True,
            extra={
                'bill_id': instance.id,
                'bill_number': instance.bill_number,
                'status': instance.status,
                'error': str(e)
            }
        )
        # Don't re-raise - allow bill save to succeed even if notification fails


def _notify_on_submit(bill: Bill, bill_url: str) -> None:
    """
    Notify Finance Officers when bill is submitted.
    
    FIXED:
    - Added error handling for each notification
    - Added validation for missing data
    - Better error messages
    
    Args:
        bill: The Bill instance that was submitted.
        bill_url: URL to the bill detail page.
    """
    try:
        # Get all Finance Officers and Accountants in the organization
        finance_officers = bill.organization.users.filter(
            roles__code__in=['FINANCE_OFFICER', 'ACCOUNTANT', 'AC', 'TOF']
        ).distinct()
        
        if not finance_officers.exists():
            logger.warning(
                f"No Finance Officers found for Bill #{bill.bill_number}",
                extra={'bill_id': bill.id, 'organization': bill.organization.name}
            )
            return
        
        # Handle legacy budget_head vs new bill lines
        head_name = "Unknown Head"
        if bill.budget_head:
            head_name = bill.budget_head.name
        elif bill.lines.exists():
            head_name = bill.lines.first().budget_head.name
            if bill.lines.count() > 1:
                head_name += f" (+{bill.lines.count() - 1} others)"
        
        success_count = 0
        for officer in finance_officers:
            try:
                notification = NotificationService.send_notification(
                    recipient=officer,
                    title=f"Bill #{bill.bill_number} Pending Review",
                    message=f"Bill from {bill.payee.name} for {head_name} "
                            f"(Amount: Rs. {bill.net_amount:,.2f}) requires your review.",
                    link=bill_url,
                    category=NotificationCategory.WORKFLOW,
                    icon='bi-file-earmark-text'
                )
                if notification:
                    success_count += 1
            except Exception as e:
                logger.error(
                    f"Failed to notify {officer.username} for Bill #{bill.bill_number}",
                    exc_info=True,
                    extra={'officer_id': officer.id, 'bill_id': bill.id}
                )
        
        logger.info(
            f"Sent {success_count}/{finance_officers.count()} notifications for Bill #{bill.bill_number} submission"
        )
        
    except Exception as e:
        logger.error(
            f"Error in _notify_on_submit for Bill #{bill.bill_number}",
            exc_info=True,
            extra={'bill_id': bill.id}
        )


def _notify_on_verified(bill: Bill, bill_url: str) -> None:
    """
    Notify TMO/Approvers when bill is verified by Accountant.
    
    Args:
        bill: The Bill instance that was verified.
        bill_url: URL to the bill detail page.
    """
    try:
        # Get all TMOs in the organization
        tmos = bill.organization.users.filter(
            roles__code__in=['TMO']
        ).distinct()
        
        if not tmos.exists():
            logger.warning(
                f"No TMOs found for Bill #{bill.bill_number}",
                extra={'bill_id': bill.id, 'organization': bill.organization.name}
            )
            return
        
        for tmo in tmos:
            try:
                NotificationService.send_notification(
                    recipient=tmo,
                    title=f"Bill #{bill.bill_number} Ready for Approval",
                    message=f"Bill from {bill.payee.name} has been verified by Accountant. "
                            f"Amount: Rs. {bill.net_amount:,.2f}. Please approve.",
                    link=bill_url,
                    category=NotificationCategory.WORKFLOW,
                    icon='bi-check-circle'
                )
            except Exception as e:
                logger.error(
                    f"Failed to notify TMO {tmo.username}",
                    exc_info=True,
                    extra={'tmo_id': tmo.id, 'bill_id': bill.id}
                )
    
    except Exception as e:
        logger.error(
            f"Error in _notify_on_verified for Bill #{bill.bill_number}",
            exc_info=True,
            extra={'bill_id': bill.id}
        )


def _notify_on_marked_for_audit(bill: Bill, bill_url: str) -> None:
    """
    Notify Audit Officers when bill is marked for audit.
    
    Args:
        bill: The Bill instance marked for audit.
        bill_url: URL to the bill detail page.
    """
    try:
        # Get all Audit Officers (if role exists) or Finance Officers
        audit_officers = bill.organization.users.filter(
            roles__code__in=['AUDIT_OFFICER', 'FINANCE_OFFICER']
        ).distinct()
        
        if not audit_officers.exists():
            logger.warning(
                f"No Audit Officers found for Bill #{bill.bill_number}",
                extra={'bill_id': bill.id, 'organization': bill.organization.name}
            )
            return
        
        for officer in audit_officers:
            try:
                NotificationService.send_notification(
                    recipient=officer,
                    title=f"Bill #{bill.bill_number} Marked for Audit",
                    message=f"Bill from {bill.payee.name} requires pre-audit review. "
                            f"Amount: Rs. {bill.net_amount:,.2f}",
                    link=bill_url,
                    category=NotificationCategory.WORKFLOW,
                    icon='bi-clipboard-check'
                )
            except Exception as e:
                logger.error(
                    f"Failed to notify Audit Officer {officer.username}",
                    exc_info=True,
                    extra={'officer_id': officer.id, 'bill_id': bill.id}
                )
    
    except Exception as e:
        logger.error(
            f"Error in _notify_on_marked_for_audit for Bill #{bill.bill_number}",
            exc_info=True,
            extra={'bill_id': bill.id}
        )


def _notify_on_audited(bill: Bill, bill_url: str) -> None:
    """
    Notify TO Finance/Approvers when bill passes audit.
    
    Args:
        bill: The Bill instance that passed audit.
        bill_url: URL to the bill detail page.
    """
    try:
        # Get all TO Finance and Accountants in the organization
        tofs = bill.organization.users.filter(
            roles__code__in=['TOF', 'TO_FINANCE', 'ACCOUNTANT', 'AC']
        ).distinct()
        
        if not tofs.exists():
            logger.warning(
                f"No TO Finance officers found for Bill #{bill.bill_number}",
                extra={'bill_id': bill.id, 'organization': bill.organization.name}
            )
            return
        
        for tof in tofs:
            try:
                NotificationService.send_notification(
                    recipient=tof,
                    title=f"Bill #{bill.bill_number} Ready for Verification",
                    message=f"Bill from {bill.payee.name} has passed audit. "
                            f"Amount: Rs. {bill.net_amount:,.2f}. Please verify budget.",
                    link=bill_url,
                    category=NotificationCategory.WORKFLOW,
                    icon='bi-check-circle'
                )
            except Exception as e:
                logger.error(
                    f"Failed to notify TO Finance {tof.username}",
                    exc_info=True,
                    extra={'tof_id': tof.id, 'bill_id': bill.id}
                )
    
    except Exception as e:
        logger.error(
            f"Error in _notify_on_audited for Bill #{bill.bill_number}",
            exc_info=True,
            extra={'bill_id': bill.id}
        )


def _notify_on_approved(bill: Bill, bill_url: str) -> None:
    """
    Notify Cashier and Bill Creator when bill is approved.
    
    Args:
        bill: The Bill instance that was approved.
        bill_url: URL to the bill detail page.
    """
    try:
        # Notify Cashiers for payment processing
        cashiers = bill.organization.users.filter(
            roles__code__in=['CASHIER', 'CSH']
        ).distinct()
        
        for cashier in cashiers:
            try:
                NotificationService.send_notification(
                    recipient=cashier,
                    title=f"Bill #{bill.bill_number} Approved for Payment",
                    message=f"Bill from {bill.payee.name} has been approved. "
                            f"Process payment of Rs. {bill.net_amount:,.2f}",
                    link=bill_url,
                    category=NotificationCategory.WORKFLOW,
                    icon='bi-cash-stack'
                )
            except Exception as e:
                logger.error(
                    f"Failed to notify Cashier {cashier.username}",
                    exc_info=True,
                    extra={'cashier_id': cashier.id, 'bill_id': bill.id}
                )
        
        # Notify the bill creator (submitted_by)
        if bill.submitted_by:
            try:
                NotificationService.send_notification(
                    recipient=bill.submitted_by,
                    title=f"Bill #{bill.bill_number} Approved",
                    message=f"Your bill for {bill.payee.name} has been approved. "
                            f"Amount: Rs. {bill.net_amount:,.2f}",
                    link=bill_url,
                    category=NotificationCategory.WORKFLOW,
                    icon='bi-check-circle-fill'
                )
            except Exception as e:
                logger.error(
                    f"Failed to notify bill creator {bill.submitted_by.username}",
                    exc_info=True,
                    extra={'creator_id': bill.submitted_by.id, 'bill_id': bill.id}
                )
    
    except Exception as e:
        logger.error(
            f"Error in _notify_on_approved for Bill #{bill.bill_number}",
            exc_info=True,
            extra={'bill_id': bill.id}
        )


def _notify_on_returned(bill: Bill, bill_url: str) -> None:
    """
    Notify Bill Creator when bill is returned for corrections.
    
    Args:
        bill: The Bill instance that was returned.
        bill_url: URL to the bill detail page.
    """
    try:
        if bill.submitted_by:
            try:
                NotificationService.send_notification(
                    recipient=bill.submitted_by,
                    title=f"Bill #{bill.bill_number} Returned",
                    message=f"Your bill for {bill.payee.name} has been returned for corrections. "
                            f"Reason: {bill.rejection_reason or 'Not specified'}",
                    link=bill_url,
                    category=NotificationCategory.ALERT,
                    icon='bi-arrow-return-left'
                )
            except Exception as e:
                logger.error(
                    f"Failed to notify bill creator {bill.submitted_by.username}",
                    exc_info=True,
                    extra={'creator_id': bill.submitted_by.id, 'bill_id': bill.id}
                )
        else:
            logger.warning(
                f"Bill #{bill.bill_number} returned but no submitted_by user",
                extra={'bill_id': bill.id}
            )
    
    except Exception as e:
        logger.error(
            f"Error in _notify_on_returned for Bill #{bill.bill_number}",
            exc_info=True,
            extra={'bill_id': bill.id}
        )


def _notify_on_rejected(bill: Bill, bill_url: str) -> None:
    """
    Notify Bill Creator when bill is rejected.
    
    Args:
        bill: The Bill instance that was rejected.
        bill_url: URL to the bill detail page.
    """
    try:
        if bill.submitted_by:
            try:
                NotificationService.send_notification(
                    recipient=bill.submitted_by,
                    title=f"Bill #{bill.bill_number} Rejected",
                    message=f"Your bill for {bill.payee.name} has been rejected. "
                            f"Reason: {bill.rejection_reason or 'Not specified'}",
                    link=bill_url,
                    category=NotificationCategory.ALERT,
                    icon='bi-x-circle-fill'
                )
            except Exception as e:
                logger.error(
                    f"Failed to notify bill creator {bill.submitted_by.username}",
                    exc_info=True,
                    extra={'creator_id': bill.submitted_by.id, 'bill_id': bill.id}
                )
        else:
            logger.warning(
                f"Bill #{bill.bill_number} rejected but no submitted_by user",
                extra={'bill_id': bill.id}
            )
    
    except Exception as e:
        logger.error(
            f"Error in _notify_on_rejected for Bill #{bill.bill_number}",
            exc_info=True,
            extra={'bill_id': bill.id}
        )
