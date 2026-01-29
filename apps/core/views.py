"""
Views for the Core module.
"""
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _

from apps.users.permissions import AdminRequiredMixin
from apps.core.models import BankAccount


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
