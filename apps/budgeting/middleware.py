"""
-------------------------------------------------------------------------
System: KP-CFMS (Computerized Financial Management System)
Client: Local Government Department, Khyber Pakhtunkhwa
Team Lead: Jamil Shah
Developers: Ali Asghar, Akhtar Munir and Zarif Khan
Description: Django middleware for the budgeting module.
             Implements budget lock enforcement.
-------------------------------------------------------------------------
"""
from typing import Callable
from django.http import HttpRequest, HttpResponse
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse

from apps.core.exceptions import FiscalYearInactiveException, BudgetLockedException


class BudgetLockMiddleware:
    """
    Middleware to block budget modifications when fiscal year is locked.
    
    This middleware intercepts POST requests to budget entry URLs
    and checks if the target fiscal year is locked or inactive.
    """
    
    # URL patterns that should be blocked when budget is locked
    BLOCKED_URL_PATTERNS = [
        '/budgeting/receipt/',
        '/budgeting/expenditure/',
        '/budgeting/establishment/create',
        '/budgeting/allocation/',
    ]
    
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        """
        Initialize middleware.
        
        Args:
            get_response: The next middleware or view in the chain.
        """
        self.get_response = get_response
    
    def __call__(self, request: HttpRequest) -> HttpResponse:
        """
        Process request and check budget lock status.
        
        Args:
            request: The incoming HTTP request.
            
        Returns:
            HTTP response from the view or redirect if blocked.
        """
        # Only check POST requests to blocked patterns
        if request.method == 'POST' and self._should_check(request.path):
            try:
                self._check_budget_status(request)
            except (FiscalYearInactiveException, BudgetLockedException) as e:
                messages.error(request, e.message)
                return redirect(request.META.get('HTTP_REFERER', '/budgeting/'))
        
        return self.get_response(request)
    
    def _should_check(self, path: str) -> bool:
        """
        Check if the URL path should be validated for budget lock.
        
        Args:
            path: Request URL path.
            
        Returns:
            True if the path should be checked.
        """
        return any(pattern in path for pattern in self.BLOCKED_URL_PATTERNS)
    
    def _check_budget_status(self, request: HttpRequest) -> None:
        """
        Validate that budget is editable for the user's organization.
        
        Args:
            request: The HTTP request.
            
        Raises:
            FiscalYearInactiveException: If no planning-active fiscal year.
            BudgetLockedException: If budget proposal is locked.
        """
        from apps.budgeting.models import FiscalYear, BudgetProposal
        
        # User must have an organization
        if not request.user.is_authenticated or not request.user.organization:
            raise FiscalYearInactiveException(
                "You must be logged in with an organization to edit budgets."
            )
        
        # Try to get fiscal year from request
        fiscal_year_id = (
            request.POST.get('fiscal_year') or 
            request.GET.get('fiscal_year')
        )
        
        if fiscal_year_id:
            try:
                fiscal_year = FiscalYear.objects.get(pk=fiscal_year_id)
            except FiscalYear.DoesNotExist:
                raise FiscalYearInactiveException(
                    "The specified fiscal year does not exist."
                )
        else:
            # Default to planning-active fiscal year
            fiscal_year = FiscalYear.objects.filter(is_planning_active=True).first()
            if not fiscal_year:
                raise FiscalYearInactiveException(
                    "No active planning window found. Please contact the administrator."
                )
        
        # Get or create BudgetProposal for this TMA
        try:
            proposal = BudgetProposal.objects.get(
                organization=request.user.organization,
                fiscal_year=fiscal_year
            )
        except BudgetProposal.DoesNotExist:
            # If no proposal exists, check if planning window is open
            if not fiscal_year.is_planning_active:
                raise FiscalYearInactiveException(
                    f"Budget planning for {fiscal_year.year_name} is not currently allowed."
                )
            # Proposal will be created on first budget entry
            return
        
        # Check if proposal is locked
        if proposal.is_locked:
            raise BudgetLockedException(
                f"Budget proposal for {fiscal_year.year_name} is locked and cannot be modified. "
                f"Status: {proposal.get_status_display()}"
            )
        
        # Check if planning window is open
        if not proposal.can_edit_budget():
            raise FiscalYearInactiveException(
                f"Budget entry for {fiscal_year.year_name} is not currently allowed. "
                f"Status: {proposal.get_status_display()}"
            )

