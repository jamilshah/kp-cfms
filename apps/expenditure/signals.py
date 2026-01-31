"""
-------------------------------------------------------------------------
System: KP-CFMS (Computerized Financial Management System)
Client: Local Government Department, Khyber Pakhtunkhwa
Team Lead: Jamil Shah
Developers: Ali Asghar, Akhtar Munir and Zarif Khan
Description: Signal handlers for expenditure workflow automation.
             Automatically sends notifications when bill status changes.
-------------------------------------------------------------------------
"""
from typing import Optional
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.urls import reverse

from apps.expenditure.models import Bill, BillStatus
from apps.core.services import NotificationService
from apps.core.models import NotificationCategory


@receiver(post_save, sender=Bill)
def bill_status_change_notification(sender, instance: Bill, created: bool, **kwargs):
    """
    Send notifications when Bill status changes.
    
    Triggers on:
    - SUBMITTED: Notify Finance Officers/Accountants
    - MARKED_FOR_AUDIT: Notify Audit Officers
    - AUDITED: Notify TMO/Approvers
    - APPROVED: Notify Cashier and Bill Creator
    - RETURNED: Notify Bill Creator
    - REJECTED: Notify Bill Creator
    """
    # Skip if bill is just created (not a status change)
    if created:
        return
    
    # Get the bill URL for deep linking
    bill_url = reverse('expenditure:bill_detail', kwargs={'pk': instance.pk})
    
    # Route notifications based on status
    if instance.status == BillStatus.SUBMITTED:
        _notify_on_submit(instance, bill_url)
    
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


def _notify_on_submit(bill: Bill, bill_url: str) -> None:
    """
    Notify Finance Officers when bill is submitted.
    
    Args:
        bill: The Bill instance that was submitted.
        bill_url: URL to the bill detail page.
    """
    # Get all Finance Officers and Accountants in the organization
    finance_officers = bill.organization.users.filter(
        roles__code__in=['FINANCE_OFFICER', 'ACCOUNTANT', 'AC', 'TOF']
    ).distinct()
    
    for officer in finance_officers:
        NotificationService.send_notification(
            recipient=officer,
            title=f"Bill #{bill.bill_number} Pending Review",
            message=f"Bill from {bill.payee.name} for {bill.budget_head.name} "
                    f"(Amount: Rs. {bill.net_amount:,.2f}) requires your review.",
            link=bill_url,
            category=NotificationCategory.WORKFLOW,
            icon='bi-file-earmark-text'
        )


def _notify_on_marked_for_audit(bill: Bill, bill_url: str) -> None:
    """
    Notify Audit Officers when bill is marked for audit.
    
    Args:
        bill: The Bill instance marked for audit.
        bill_url: URL to the bill detail page.
    """
    # Get all Audit Officers (if role exists) or Finance Officers
    audit_officers = bill.organization.users.filter(
        roles__code__in=['AUDIT_OFFICER', 'FINANCE_OFFICER']
    ).distinct()
    
    for officer in audit_officers:
        NotificationService.send_notification(
            recipient=officer,
            title=f"Bill #{bill.bill_number} Marked for Audit",
            message=f"Bill from {bill.payee.name} requires pre-audit review. "
                    f"Amount: Rs. {bill.net_amount:,.2f}",
            link=bill_url,
            category=NotificationCategory.WORKFLOW,
            icon='bi-clipboard-check'
        )


def _notify_on_audited(bill: Bill, bill_url: str) -> None:
    """
    Notify TMO/Approvers when bill passes audit.
    
    Args:
        bill: The Bill instance that passed audit.
        bill_url: URL to the bill detail page.
    """
    # Get all TMOs in the organization
    tmos = bill.organization.users.filter(
        roles__code__in=['TMO']
    ).distinct()
    
    for tmo in tmos:
        NotificationService.send_notification(
            recipient=tmo,
            title=f"Bill #{bill.bill_number} Ready for Approval",
            message=f"Bill from {bill.payee.name} has passed audit and requires your approval. "
                    f"Amount: Rs. {bill.net_amount:,.2f}",
            link=bill_url,
            category=NotificationCategory.WORKFLOW,
            icon='bi-check-circle'
        )


def _notify_on_approved(bill: Bill, bill_url: str) -> None:
    """
    Notify Cashier and Bill Creator when bill is approved.
    
    Args:
        bill: The Bill instance that was approved.
        bill_url: URL to the bill detail page.
    """
    # Notify Cashiers for payment processing
    cashiers = bill.organization.users.filter(
        roles__code__in=['CASHIER', 'CSH']
    ).distinct()
    
    for cashier in cashiers:
        NotificationService.send_notification(
            recipient=cashier,
            title=f"Bill #{bill.bill_number} Approved for Payment",
            message=f"Bill from {bill.payee.name} has been approved. "
                    f"Process payment of Rs. {bill.net_amount:,.2f}",
            link=bill_url,
            category=NotificationCategory.WORKFLOW,
            icon='bi-cash-stack'
        )
    
    # Notify the bill creator (submitted_by)
    if bill.submitted_by:
        NotificationService.send_notification(
            recipient=bill.submitted_by,
            title=f"Bill #{bill.bill_number} Approved",
            message=f"Your bill for {bill.payee.name} has been approved. "
                    f"Amount: Rs. {bill.net_amount:,.2f}",
            link=bill_url,
            category=NotificationCategory.WORKFLOW,
            icon='bi-check-circle-fill'
        )


def _notify_on_returned(bill: Bill, bill_url: str) -> None:
    """
    Notify Bill Creator when bill is returned for corrections.
    
    Args:
        bill: The Bill instance that was returned.
        bill_url: URL to the bill detail page.
    """
    if bill.submitted_by:
        NotificationService.send_notification(
            recipient=bill.submitted_by,
            title=f"Bill #{bill.bill_number} Returned",
            message=f"Your bill for {bill.payee.name} has been returned for corrections. "
                    f"Reason: {bill.rejection_reason or 'Not specified'}",
            link=bill_url,
            category=NotificationCategory.ALERT,
            icon='bi-arrow-return-left'
        )


def _notify_on_rejected(bill: Bill, bill_url: str) -> None:
    """
    Notify Bill Creator when bill is rejected.
    
    Args:
        bill: The Bill instance that was rejected.
        bill_url: URL to the bill detail page.
    """
    if bill.submitted_by:
        NotificationService.send_notification(
            recipient=bill.submitted_by,
            title=f"Bill #{bill.bill_number} Rejected",
            message=f"Your bill for {bill.payee.name} has been rejected. "
                    f"Reason: {bill.rejection_reason or 'Not specified'}",
            link=bill_url,
            category=NotificationCategory.ALERT,
            icon='bi-x-circle-fill'
        )
