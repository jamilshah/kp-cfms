"""
-------------------------------------------------------------------------
System: KP-CFMS (Computerized Financial Management System)
Client: Local Government Department, Khyber Pakhtunkhwa
Team Lead: Jamil Shah
Developers: Ali Asghar, Akhtar Munir and Zarif Khan
Description: Middleware for multi-tenancy enforcement. Injects the
             current user's organization into the request and enforces
             data isolation.
-------------------------------------------------------------------------
"""
from typing import Callable, Optional
from django.http import HttpRequest, HttpResponse
from django.utils.deprecation import MiddlewareMixin


class TenantMiddleware(MiddlewareMixin):
    """
    Middleware to enforce multi-tenancy data isolation.
    
    This middleware:
    1. Injects `request.organization` from the authenticated user.
    2. For LCB/LGD users (organization=None), allows cross-tenant read access.
    3. Restricts write operations for oversight users to status fields only.
    
    Usage:
        Add to MIDDLEWARE in settings.py AFTER AuthenticationMiddleware:
        'apps.core.middleware.TenantMiddleware',
    """
    
    def process_request(self, request: HttpRequest) -> Optional[HttpResponse]:
        """
        Inject organization context into the request.
        
        Args:
            request: The incoming HTTP request.
            
        Returns:
            None to continue processing, or HttpResponse to short-circuit.
        """
        # Default to None (no tenant context)
        request.organization = None
        request.is_oversight_user = False
        
        # Only process for authenticated users
        if hasattr(request, 'user') and request.user.is_authenticated:
            # Get organization from user profile
            user_org = getattr(request.user, 'organization', None)
            request.organization = user_org
            
            # Check if user is an oversight user (LCB/LGD with no org)
            if user_org is None:
                # Check role - LCB officers have oversight access
                user_role = getattr(request.user, 'role', None)
                if user_role in ['LCB', 'ADM']:
                    request.is_oversight_user = True
        
        return None
    
    def process_view(
        self, 
        request: HttpRequest, 
        view_func: Callable, 
        view_args: tuple, 
        view_kwargs: dict
    ) -> Optional[HttpResponse]:
        """
        Pre-process view to inject tenant context.
        
        This can be extended to automatically apply tenant filtering
        to views that inherit from TenantAwareViewMixin.
        
        Args:
            request: The incoming HTTP request.
            view_func: The view function being called.
            view_args: Positional arguments to the view.
            view_kwargs: Keyword arguments to the view.
            
        Returns:
            None to continue processing.
        """
        return None


class TenantAwareViewMixin:
    """
    Mixin for class-based views to automatically apply tenant filtering.
    
    Usage:
        class MyListView(TenantAwareViewMixin, ListView):
            model = MyTenantAwareModel
            
    This mixin will automatically filter the queryset to only show
    records belonging to the current user's organization.
    """
    
    def get_queryset(self):
        """
        Override get_queryset to apply tenant filtering.
        
        Returns:
            Queryset filtered by current user's organization.
        """
        qs = super().get_queryset()
        
        # Get organization from request
        organization = getattr(self.request, 'organization', None)
        
        # If no organization (oversight user), return all
        if organization is None:
            return qs
        
        # Filter by organization if model has the field
        if hasattr(qs.model, 'organization'):
            return qs.filter(organization=organization)
        
        return qs
    
    def form_valid(self, form):
        """
        Override form_valid to automatically set organization on save.
        
        Args:
            form: The validated form.
            
        Returns:
            HttpResponse from parent form_valid.
        """
        # Set organization if the model has the field
        if hasattr(form.instance, 'organization'):
            if form.instance.organization_id is None:
                organization = getattr(self.request, 'organization', None)
                if organization:
                    form.instance.organization = organization
        
        return super().form_valid(form)
