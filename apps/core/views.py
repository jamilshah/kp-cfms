"""
-------------------------------------------------------------------------
System: KP-CFMS (Computerized Financial Management System)
Client: Local Government Department, Khyber Pakhtunkhwa
Team Lead: Jamil Shah
Developers: Ali Asghar, Akhtar Munir and Zarif Khan
Description: Core views including notification management and bank accounts.
-------------------------------------------------------------------------
"""
from typing import Dict, Any
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.template.loader import render_to_string
from django.db.models import Q

from apps.users.permissions import AdminRequiredMixin
from apps.core.models import BankAccount, Notification, NotificationCategory
from apps.core.services import NotificationService
from apps.finance.models import BudgetHead, AccountType


# =====================================================================
# NOTIFICATION VIEWS
# =====================================================================

class NotificationListView(LoginRequiredMixin, ListView):
    """
    List all notifications for the current user.
    
    Features:
    - Tabbed interface (All, Unread, Workflow, Alerts)
    - Paginated results
    - Mark as read functionality
    """
    model = Notification
    template_name = 'core/notification_list.html'
    context_object_name = 'notifications'
    paginate_by = 20
    
    def get_queryset(self):
        """Return notifications for current user."""
        return Notification.objects.filter(
            recipient=self.request.user
        ).order_by('-created_at')
    
    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Get all notifications
        all_notifications = self.get_queryset()
        
        # Filter by category
        context['unread_notifications'] = all_notifications.filter(is_read=False)
        context['workflow_notifications'] = all_notifications.filter(
            category=NotificationCategory.WORKFLOW
        )
        context['alert_notifications'] = all_notifications.filter(
            category=NotificationCategory.ALERT
        )
        
        # Counts
        context['unread_count'] = NotificationService.get_unread_count(user)
        context['workflow_count'] = all_notifications.filter(
            category=NotificationCategory.WORKFLOW
        ).count()
        context['alert_count'] = all_notifications.filter(
            category=NotificationCategory.ALERT
        ).count()
        
        return context


@login_required
def notification_dropdown_view(request):
    """
    HTMX endpoint for notification dropdown content.
    
    Returns HTML fragment with recent notifications.
    """
    notifications = NotificationService.get_recent_notifications(request.user, limit=5)
    unread_count = NotificationService.get_unread_count(request.user)
    
    html = render_to_string(
        'core/notification_dropdown.html',
        {
            'notifications': notifications,
            'unread_count': unread_count,
        },
        request=request
    )
    return HttpResponse(html)


@login_required
def notification_badge_view(request):
    """
    HTMX endpoint for notification badge (unread count).
    
    Returns HTML fragment with badge showing unread count.
    """
    unread_count = NotificationService.get_unread_count(request.user)
    
    html = render_to_string(
        'core/notification_badge.html',
        {'unread_count': unread_count},
        request=request
    )
    return HttpResponse(html)


@login_required
@require_POST
def notification_mark_read_view(request, pk):
    """
    Mark a specific notification as read.
    
    HTMX endpoint - returns updated notification HTML.
    """
    notification = get_object_or_404(
        Notification,
        pk=pk,
        recipient=request.user
    )
    notification.mark_as_read()
    
    response = HttpResponse('')
    response['HX-Trigger'] = 'reloadBadge, reloadNotifications'
    return response


@login_required
@require_POST
def notification_mark_all_read_view(request):
    """
    Mark all notifications for current user as read.
    
    HTMX endpoint - returns updated badge HTML.
    """
    NotificationService.mark_all_as_read(request.user)
    
    # Return updated badge or just trigger reload
    response = HttpResponse('')
    # Trigger both badge and dropdown list reload
    response['HX-Trigger'] = 'reloadBadge, reloadNotifications'
    return response


# =====================================================================
# BANK ACCOUNT VIEWS
# =====================================================================


class BankAccountListView(LoginRequiredMixin, AdminRequiredMixin, ListView):
    """List all bank accounts."""
    model = BankAccount
    template_name = 'core/setup_bankaccount_list.html'
    context_object_name = 'bank_accounts'
    ordering = ['organization__name', 'bank_name']
    
    def get_queryset(self):
        queryset = super().get_queryset().select_related('organization', 'gl_code')
        if self.request.user.organization:
            queryset = queryset.filter(organization=self.request.user.organization)
        return queryset


class BankAccountCreateView(LoginRequiredMixin, AdminRequiredMixin, CreateView):
    """Create new bank account."""
    model = BankAccount
    fields = ['organization', 'bank_name', 'branch_code', 'account_number', 'title', 'gl_code', 'is_active']
    template_name = 'budgeting/setup_form.html'
    success_url = reverse_lazy('budgeting:setup_bank_accounts')
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)

        # Filter GL Codes to Assets only (Bank accounts are assets)
        if 'gl_code' in form.fields:
            form.fields['gl_code'].queryset = BudgetHead.objects.filter(
                Q(nam_head__account_type=AccountType.ASSET) |
                Q(sub_head__nam_head__account_type=AccountType.ASSET)
            ).select_related('nam_head', 'sub_head__nam_head', 'function', 'fund')
        
        # Restrict Organization for TMA users
        if self.request.user.organization:
            if 'organization' in form.fields:
                del form.fields['organization']
            form.instance.organization = self.request.user.organization
        else:
            form.fields['organization'].widget.attrs.update({'class': 'form-select'})
            
        form.fields['bank_name'].widget.attrs.update({'class': 'form-control'})
        form.fields['branch_code'].widget.attrs.update({'class': 'form-control'})
        form.fields['account_number'].widget.attrs.update({'class': 'form-control'})
        form.fields['title'].widget.attrs.update({'class': 'form-control'})
        form.fields['gl_code'].widget.attrs.update({'class': 'form-select'})
        form.fields['is_active'].widget.attrs.update({'class': 'form-check-input'})
        return form
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = _('Add New Bank Account')
        context['back_url'] = reverse_lazy('budgeting:setup_bank_accounts')
        return context


class BankAccountUpdateView(LoginRequiredMixin, AdminRequiredMixin, UpdateView):
    """Update bank account."""
    model = BankAccount
    fields = ['organization', 'bank_name', 'branch_code', 'account_number', 'title', 'gl_code', 'is_active']
    template_name = 'budgeting/setup_form.html'
    success_url = reverse_lazy('budgeting:setup_bank_accounts')
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)

        # Filter GL Codes to Assets only (Bank accounts are assets)
        if 'gl_code' in form.fields:
            form.fields['gl_code'].queryset = BudgetHead.objects.filter(
                Q(nam_head__account_type=AccountType.ASSET) |
                Q(sub_head__nam_head__account_type=AccountType.ASSET)
            ).select_related('nam_head', 'sub_head__nam_head', 'function', 'fund')
        
        # Restrict Organization for TMA users
        if self.request.user.organization:
            if 'organization' in form.fields:
                del form.fields['organization']
            form.instance.organization = self.request.user.organization
        else:
            form.fields['organization'].widget.attrs.update({'class': 'form-select'})

        form.fields['bank_name'].widget.attrs.update({'class': 'form-control'})
        form.fields['branch_code'].widget.attrs.update({'class': 'form-control'})
        form.fields['account_number'].widget.attrs.update({'class': 'form-control'})
        form.fields['title'].widget.attrs.update({'class': 'form-control'})
        form.fields['gl_code'].widget.attrs.update({'class': 'form-select'})
        form.fields['is_active'].widget.attrs.update({'class': 'form-check-input'})
        return form
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = _('Edit Bank Account')
        context['back_url'] = reverse_lazy('budgeting:setup_bank_accounts')
        return context


class BankAccountDeleteView(LoginRequiredMixin, AdminRequiredMixin, DeleteView):
    """Delete bank account."""
    model = BankAccount
    template_name = 'budgeting/setup_confirm_delete.html'
    success_url = reverse_lazy('budgeting:setup_bank_accounts')
    context_object_name = 'item'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = _('Delete Bank Account')
        context['back_url'] = reverse_lazy('budgeting:setup_bank_accounts')
        return context
