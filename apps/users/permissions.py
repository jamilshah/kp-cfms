"""
-------------------------------------------------------------------------
System: KP-CFMS (Computerized Financial Management System)
Client: Local Government Department, Khyber Pakhtunkhwa
Team Lead: Jamil Shah
Developers: Ali Asghar, Akhtar Munir and Zarif Khan
Description: Permission classes for role-based access control.
             Implements Maker/Checker/Approver permission checks.
-------------------------------------------------------------------------
"""
from typing import Any
from django.contrib.auth.mixins import UserPassesTestMixin
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest

from apps.core.exceptions import UnauthorizedRoleException, SelfApprovalException


class RoleRequiredMixin(UserPassesTestMixin):
    """
    Base mixin for role-based view access control.
    
    Subclasses should define the `required_roles` attribute as a list
    of UserRole values that are allowed to access the view.
    
    Attributes:
        required_roles: List of role codes that can access this view.
    """
    
    required_roles: list = []
    
    def test_func(self) -> bool:
        """
        Test if the current user has the required role.
        
        Returns:
            True if user has any of the required roles, False otherwise.
        """
        if not self.request.user.is_authenticated:
            return False
        
        if self.request.user.is_superuser:
            return True
        
        return self.request.user.role in self.required_roles
    
    def handle_no_permission(self) -> None:
        """Handle unauthorized access attempt."""
        raise PermissionDenied(
            UnauthorizedRoleException(
                f"This action requires one of the following roles: {self.required_roles}"
            ).message
        )


class MakerRequiredMixin(RoleRequiredMixin):
    """
    Mixin that restricts access to Maker (Dealing Assistant) role.
    
    Used for views that create new bills, budget entries, etc.
    System Admins (ADM) are also allowed for data setup.
    """
    
    required_roles = ['DA', 'ADM']


class CheckerRequiredMixin(RoleRequiredMixin):
    """
    Mixin that restricts access to Checker (Accountant) role.
    
    Used for views that verify/pre-audit transactions.
    """
    
    required_roles = ['AC', 'ADM']


class ApproverRequiredMixin(RoleRequiredMixin):
    """
    Mixin that restricts access to Approver (TMO) role.
    
    Used for views that approve transactions.
    """
    
    required_roles = ['TMO', 'ADM']


class FinanceOfficerRequiredMixin(RoleRequiredMixin):
    """
    Mixin that restricts access to TO Finance role.
    
    Used for budget release and financial oversight views.
    """
    
    required_roles = ['TOF', 'TMO']


class CashierRequiredMixin(RoleRequiredMixin):
    """
    Mixin that restricts access to Cashier role.
    
    Used for payment and collection recording views.
    """
    
    required_roles = ['CSH']


class LCBOfficerRequiredMixin(RoleRequiredMixin):
    """
    Mixin that restricts access to LCB Finance Officer role.
    
    Used for provincial oversight functions like CoA approval.
    """
    
    required_roles = ['LCB']


def check_segregation_of_duties(
    transaction_creator_id: int,
    current_user_id: int,
    action: str = "approve"
) -> None:
    """
    Verify segregation of duties - a user cannot approve their own work.
    
    Args:
        transaction_creator_id: ID of the user who created the transaction.
        current_user_id: ID of the user attempting the action.
        action: Description of the action being attempted.
        
    Raises:
        SelfApprovalException: If the user is trying to approve their own work.
    """
    if transaction_creator_id == current_user_id:
        raise SelfApprovalException(
            f"You cannot {action} a transaction you created (Segregation of Duties)."
        )


def has_role(user: Any, roles: list) -> bool:
    """
    Check if user has any of the specified roles.
    
    Args:
        user: The user object to check.
        roles: List of role codes to check against.
        
    Returns:
        True if user has any of the specified roles or is superuser.
    """
    if not user.is_authenticated:
        return False
    
    if user.is_superuser:
        return True
    
    return user.role in roles


def can_approve_establishment_post(user: Any, establishment_entry: Any) -> bool:
    """
    Check if user can approve a ScheduleOfEstablishment entry.
    
    PUGF posts require LCB approval; Local posts require TMO approval.
    
    Args:
        user: The user attempting to approve.
        establishment_entry: The ScheduleOfEstablishment instance.
        
    Returns:
        True if user can approve this type of post.
    """
    from apps.budgeting.models import PostType, ApprovalStatus
    
    if not user.is_authenticated:
        return False
    
    if user.is_superuser:
        return True
    
    post_type = establishment_entry.post_type
    current_status = establishment_entry.approval_status
    
    # PUGF posts: Only LCB can do final approval
    if post_type == PostType.PUGF:
        # TMO can only "Recommend" PUGF posts
        if current_status == ApprovalStatus.VERIFIED:
            # At VERIFIED stage, TMO can only recommend
            return user.role == 'TMO'  # For RECOMMEND action
        elif current_status == ApprovalStatus.RECOMMENDED:
            # At RECOMMENDED stage, only LCB can approve
            return user.role == 'LCB'
    
    # LOCAL posts: TMO has final approval authority
    elif post_type == PostType.LOCAL:
        if current_status == ApprovalStatus.VERIFIED:
            return user.role == 'TMO'
    
    return False


def can_recommend_pugf_post(user: Any, establishment_entry: Any) -> bool:
    """
    Check if user can recommend (not approve) a PUGF post.
    
    TMO can recommend PUGF posts but cannot approve them.
    
    Args:
        user: The user attempting to recommend.
        establishment_entry: The ScheduleOfEstablishment instance.
        
    Returns:
        True if user can recommend this PUGF post.
    """
    from apps.budgeting.models import PostType, ApprovalStatus
    
    if not user.is_authenticated:
        return False
    
    if user.is_superuser:
        return True
    
    # Only applies to PUGF posts at VERIFIED stage
    if establishment_entry.post_type != PostType.PUGF:
        return False
    
    if establishment_entry.approval_status != ApprovalStatus.VERIFIED:
        return False
    
    # TMO can recommend PUGF posts
    return user.role == 'TMO'


class CanApprovePUGFMixin(UserPassesTestMixin):
    """
    Mixin that restricts PUGF post approval to LCB officers only.
    
    This mixin checks if the establishment entry is PUGF and if so,
    only allows LCB officers to perform the approval action.
    """
    
    def test_func(self) -> bool:
        """
        Test if the current user can approve PUGF posts.
        
        Returns:
            True if user is LCB officer or superuser.
        """
        if not self.request.user.is_authenticated:
            return False
        
        if self.request.user.is_superuser:
            return True
        
        return self.request.user.role == 'LCB'
    
    def handle_no_permission(self) -> None:
        """Handle unauthorized access attempt."""
        raise PermissionDenied(
            "Only LCB Finance Officers can approve PUGF posts."
        )

class AdminRequiredMixin(RoleRequiredMixin):
    """
    Mixin that restricts access to System Admin role.
    
    Used for configuration and setup views.
    """
    
    required_roles = ['ADM']
