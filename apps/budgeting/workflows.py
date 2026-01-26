"""
-------------------------------------------------------------------------
System: KP-CFMS (Computerized Financial Management System)
Client: Local Government Department, Khyber Pakhtunkhwa
Team Lead: Jamil Shah
Developers: Ali Asghar, Akhtar Munir and Zarif Khan
Description: Workflow state machines for PUGF and Local approval paths.
             Enforces the dual-track approval process based on post type.
-------------------------------------------------------------------------
"""
from typing import Optional, Tuple, List
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core.exceptions import WorkflowTransitionException, UnauthorizedRoleException
from apps.budgeting.models import ApprovalStatus, PostType


# Define valid state transitions
LOCAL_TRANSITIONS = {
    ApprovalStatus.DRAFT: [ApprovalStatus.VERIFIED, ApprovalStatus.APPROVED],
    ApprovalStatus.VERIFIED: [ApprovalStatus.APPROVED, ApprovalStatus.REJECTED],
    ApprovalStatus.APPROVED: [],
    ApprovalStatus.REJECTED: [ApprovalStatus.DRAFT],
}

PUGF_TRANSITIONS = {
    ApprovalStatus.DRAFT: [ApprovalStatus.VERIFIED, ApprovalStatus.RECOMMENDED],
    ApprovalStatus.VERIFIED: [ApprovalStatus.RECOMMENDED, ApprovalStatus.REJECTED],
    ApprovalStatus.RECOMMENDED: [ApprovalStatus.APPROVED, ApprovalStatus.REJECTED],
    ApprovalStatus.APPROVED: [],
    ApprovalStatus.REJECTED: [ApprovalStatus.DRAFT],
}


def get_valid_transitions(post_type: str, current_status: str) -> List[str]:
    """
    Get the list of valid next states for a given post type and current status.
    
    Args:
        post_type: PostType.PUGF or PostType.LOCAL
        current_status: Current ApprovalStatus
        
    Returns:
        List of valid next status values.
    """
    transitions = PUGF_TRANSITIONS if post_type == PostType.PUGF else LOCAL_TRANSITIONS
    return transitions.get(current_status, [])


def can_transition(post_type: str, current_status: str, target_status: str) -> bool:
    """
    Check if a transition from current_status to target_status is valid.
    
    Args:
        post_type: PostType.PUGF or PostType.LOCAL
        current_status: Current ApprovalStatus
        target_status: Desired ApprovalStatus
        
    Returns:
        True if the transition is valid.
    """
    valid_targets = get_valid_transitions(post_type, current_status)
    return target_status in valid_targets


def validate_transition(
    post_type: str,
    current_status: str,
    target_status: str,
    user_role: str
) -> Tuple[bool, Optional[str]]:
    """
    Validate a workflow transition including role-based permissions.
    
    Args:
        post_type: PostType.PUGF or PostType.LOCAL
        current_status: Current ApprovalStatus
        target_status: Desired ApprovalStatus
        user_role: The role code of the user attempting the transition
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    # Check state machine validity first
    if not can_transition(post_type, current_status, target_status):
        return False, _(
            f"Invalid transition from {current_status} to {target_status} "
            f"for {post_type} posts."
        )
    
    # Role-based validation
    if target_status == ApprovalStatus.VERIFIED:
        # TO Finance or Accountant can verify
        if user_role not in ['TOF', 'AC', 'ADM']:
            return False, _("Only TO Finance or Accountant can verify entries.")
    
    elif target_status == ApprovalStatus.APPROVED:
        if post_type == PostType.LOCAL:
            # TMO can approve LOCAL posts
            if user_role not in ['TMO', 'ADM']:
                return False, _("Only TMO can approve Local posts.")
        elif post_type == PostType.PUGF:
            # Only LCB can approve PUGF posts
            if user_role not in ['LCB', 'ADM']:
                return False, _("Only LCB can approve PUGF posts.")
    
    elif target_status == ApprovalStatus.RECOMMENDED:
        # Only TMO can recommend PUGF posts
        if user_role not in ['TMO', 'ADM']:
            return False, _("Only TMO can recommend PUGF posts.")
    
    elif target_status == ApprovalStatus.REJECTED:
        # TMO can reject LOCAL, LCB can reject PUGF (at their stage)
        if post_type == PostType.LOCAL:
            if user_role not in ['TMO', 'TOF', 'ADM']:
                return False, _("Only TMO or TO Finance can reject Local posts.")
        elif post_type == PostType.PUGF:
            if current_status == ApprovalStatus.VERIFIED:
                if user_role not in ['TMO', 'ADM']:
                    return False, _("Only TMO can reject at verification stage.")
            elif current_status == ApprovalStatus.RECOMMENDED:
                if user_role not in ['LCB', 'ADM']:
                    return False, _("Only LCB can reject at recommendation stage.")
    
    return True, None


def perform_transition(
    establishment_entry,
    target_status: str,
    user,
    rejection_reason: str = ""
) -> None:
    """
    Perform a workflow transition on a ScheduleOfEstablishment entry.
    
    Args:
        establishment_entry: The ScheduleOfEstablishment instance
        target_status: Desired ApprovalStatus
        user: The CustomUser performing the action
        rejection_reason: Required if target_status is REJECTED
        
    Raises:
        WorkflowTransitionException: If the transition is invalid
        UnauthorizedRoleException: If the user lacks permission
    """
    is_valid, error = validate_transition(
        establishment_entry.post_type,
        establishment_entry.approval_status,
        target_status,
        user.role
    )
    
    if not is_valid:
        raise WorkflowTransitionException(error)
    
    # Update the entry
    establishment_entry.approval_status = target_status
    
    if target_status == ApprovalStatus.RECOMMENDED:
        establishment_entry.recommended_by = user
        establishment_entry.recommended_at = timezone.now()
    
    elif target_status == ApprovalStatus.APPROVED:
        establishment_entry.approved_by = user
        establishment_entry.approved_at = timezone.now()
    
    elif target_status == ApprovalStatus.REJECTED:
        establishment_entry.rejection_reason = rejection_reason
    
    establishment_entry.save()


def get_status_display_class(status: str) -> str:
    """
    Get Bootstrap CSS class for status badge display.
    
    Args:
        status: ApprovalStatus value
        
    Returns:
        Bootstrap badge class name.
    """
    status_classes = {
        ApprovalStatus.DRAFT: 'bg-secondary',
        ApprovalStatus.VERIFIED: 'bg-info',
        ApprovalStatus.RECOMMENDED: 'bg-warning text-dark',
        ApprovalStatus.APPROVED: 'bg-success',
        ApprovalStatus.REJECTED: 'bg-danger',
    }
    return status_classes.get(status, 'bg-secondary')


def get_user_allowed_actions(user, establishment_entry) -> List[str]:
    """
    Get the list of actions a user can perform on an establishment entry.
    
    Args:
        user: CustomUser instance
        establishment_entry: ScheduleOfEstablishment instance
        
    Returns:
        List of valid target status values the user can transition to.
    """
    valid_transitions = get_valid_transitions(
        establishment_entry.post_type,
        establishment_entry.approval_status
    )
    
    allowed = []
    
    # Force 'ADM' role for superusers to ensure full access
    # This covers cases where superuser has a default role like 'DA'
    user_role = 'ADM' if user.is_superuser else user.role
    
    for target in valid_transitions:
        is_valid, _ = validate_transition(
            establishment_entry.post_type,
            establishment_entry.approval_status,
            target,
            user_role
        )
        if is_valid:
            allowed.append(target)
    
    return allowed
