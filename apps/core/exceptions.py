"""
-------------------------------------------------------------------------
System: KP-CFMS (Computerized Financial Management System)
Client: Local Government Department, Khyber Pakhtunkhwa
Team Lead: Jamil Shah
Developers: Ali Asghar, Akhtar Munir and Zarif Khan
Description: Custom exceptions for the KP-CFMS system. These provide
             specific error codes for budget and workflow violations.
-------------------------------------------------------------------------
"""
from typing import Optional


class CFMSException(Exception):
    """Base exception for all KP-CFMS specific errors."""
    
    error_code: str = "ERR_CFMS_GENERIC"
    default_message: str = "An error occurred in the CFMS system."
    
    def __init__(self, message: Optional[str] = None, details: Optional[dict] = None) -> None:
        """
        Initialize CFMS exception.
        
        Args:
            message: Custom error message. If None, uses default_message.
            details: Additional context dictionary for debugging.
        """
        self.message = message or self.default_message
        self.details = details or {}
        super().__init__(self.message)
    
    def to_dict(self) -> dict:
        """Convert exception to dictionary for API responses."""
        return {
            "error_code": self.error_code,
            "message": self.message,
            "details": self.details
        }


# Budget-related Exceptions
class BudgetExceededException(CFMSException):
    """Raised when a transaction exceeds the available budget."""
    
    error_code = "ERR_BUDGET_EXCEEDED"
    default_message = "The requested amount exceeds the available budget for this head."


class ReserveViolationException(CFMSException):
    """Raised when the 2% contingency reserve rule is violated."""
    
    error_code = "ERR_RESERVE_VIOLATION"
    default_message = "Budget submission failed: Contingency reserve must be at least 2% of total receipts."


class BudgetLockedException(CFMSException):
    """Raised when attempting to modify a locked budget."""
    
    error_code = "ERR_BUDGET_LOCKED"
    default_message = "This budget is locked and cannot be modified."


class FiscalYearInactiveException(CFMSException):
    """Raised when budget entry is attempted outside the active fiscal year window."""
    
    error_code = "ERR_FISCAL_YEAR_INACTIVE"
    default_message = "Budget entry is not allowed. The fiscal year window is closed."


# Workflow-related Exceptions
class WorkflowTransitionException(CFMSException):
    """Raised when an invalid state transition is attempted."""
    
    error_code = "ERR_INVALID_TRANSITION"
    default_message = "Invalid workflow transition attempted."


class SelfApprovalException(CFMSException):
    """Raised when a user tries to approve their own transaction."""
    
    error_code = "ERR_SELF_APPROVAL"
    default_message = "You cannot approve your own transaction (Segregation of Duties)."


class UnauthorizedRoleException(CFMSException):
    """Raised when a user lacks the required role for an action."""
    
    error_code = "ERR_UNAUTHORIZED_ROLE"
    default_message = "You do not have the required role to perform this action."


# Compliance-related Exceptions
class CashPaymentLimitException(CFMSException):
    """Raised when cash payment exceeds Rs 500 limit."""
    
    error_code = "ERR_CASH_LIMIT_EXCEEDED"
    default_message = "Cash payments exceeding Rs 500 are not allowed. Use cheque or bank transfer."


class ReconciliationRequiredException(CFMSException):
    """Raised when previous month is not reconciled."""
    
    error_code = "ERR_RECONCILIATION_REQUIRED"
    default_message = "Previous month's bank reconciliation must be completed before proceeding."


class SurrenderWindowClosedException(CFMSException):
    """Raised when surrender is attempted outside the allowed window."""
    
    error_code = "ERR_SURRENDER_WINDOW_CLOSED"
    default_message = "The surrender window for this fiscal year is closed."


# Data Validation Exceptions
class NAMCodeValidationException(CFMSException):
    """Raised when an invalid NAM code structure is provided."""
    
    error_code = "ERR_INVALID_NAM_CODE"
    default_message = "The provided NAM code does not follow the required hierarchy structure."


class SanctionedPostLinkException(CFMSException):
    """Raised when salary budget is not linked to a sanctioned post."""
    
    error_code = "ERR_SANCTIONED_POST_REQUIRED"
    default_message = "Salary budget heads (A01) must be linked to a sanctioned post in the Schedule of Establishment."
