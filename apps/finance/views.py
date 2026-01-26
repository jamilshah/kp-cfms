"""
Views for the Finance module.
"""
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from typing import Dict, Any

from apps.users.permissions import AdminRequiredMixin
from apps.finance.models import BudgetHead, Fund
from apps.finance.forms import BudgetHeadForm


class FundListView(LoginRequiredMixin, AdminRequiredMixin, ListView):
    """List all funds."""
    model = Fund
    template_name = 'finance/setup_fund_list.html'
    context_object_name = 'funds'
    ordering = ['code']


class FundCreateView(LoginRequiredMixin, AdminRequiredMixin, CreateView):
    """Create new fund."""
    model = Fund
    fields = ['code', 'name', 'description', 'is_active']
    template_name = 'budgeting/setup_form.html'
    success_url = reverse_lazy('budgeting:setup_funds')
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['code'].widget.attrs.update({'class': 'form-control'})
        form.fields['name'].widget.attrs.update({'class': 'form-control'})
        form.fields['description'].widget.attrs.update({'class': 'form-control', 'rows': 3})
        form.fields['is_active'].widget.attrs.update({'class': 'form-check-input'})
        return form
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = _('Add New Fund')
        context['back_url'] = reverse_lazy('budgeting:setup_funds')
        return context


class FundUpdateView(LoginRequiredMixin, AdminRequiredMixin, UpdateView):
    """Update fund."""
    model = Fund
    fields = ['code', 'name', 'description', 'is_active']
    template_name = 'budgeting/setup_form.html'
    success_url = reverse_lazy('budgeting:setup_funds')
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['code'].widget.attrs.update({'class': 'form-control', 'readonly': 'readonly'})
        form.fields['name'].widget.attrs.update({'class': 'form-control'})
        form.fields['description'].widget.attrs.update({'class': 'form-control', 'rows': 3})
        form.fields['is_active'].widget.attrs.update({'class': 'form-check-input'})
        return form
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = _('Edit Fund')
        context['back_url'] = reverse_lazy('budgeting:setup_funds')
        return context


class FundDeleteView(LoginRequiredMixin, AdminRequiredMixin, DeleteView):
    """Delete fund."""
    model = Fund
    template_name = 'budgeting/setup_confirm_delete.html'
    success_url = reverse_lazy('budgeting:setup_funds')
    context_object_name = 'item'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = _('Delete Fund')
        context['back_url'] = reverse_lazy('budgeting:setup_funds')
        return context

class BudgetHeadListView(LoginRequiredMixin, AdminRequiredMixin, ListView):
    """List all Budget Heads (Chart of Accounts)."""
    model = BudgetHead
    template_name = 'finance/budget_head_list.html'
    context_object_name = 'budget_heads'
    ordering = ['pifra_object', 'tma_sub_object']
    # Disable pagination for Tree View
    paginate_by = None

    def get_queryset(self):
        qs = super().get_queryset()
        query = self.request.GET.get('q')
        if query:
            qs = qs.filter(
                tma_description__icontains=query
            ) | qs.filter(
                pifra_object__icontains=query
            )
        return qs

    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context['page_title'] = _('Chart of Accounts Management')
        
        # Build Tree Structure (Flat list with levels)
        # Assumes queryset is sorted by pifra_object
        heads = list(context['budget_heads'])
        tree_list = []
        
        # Stack keeps track of current branch chain: [(code, level), ...]
        stack = []
        
        for head in heads:
            code = head.pifra_object
            
            # Pop stack until we find the parent (or stack empty)
            # Parent is defined as: current code starts with parent code AND is strictly longer
            while stack and (not code.startswith(stack[-1][0]) or code == stack[-1][0]):
                stack.pop()
            
            level = len(stack)
            
            # Add to tree list wrapper
            tree_list.append({
                'obj': head,
                'level': level,
                'is_leaf': True, # Will update next
                'parent_code': stack[-1][0] if stack else None
            })
            
            # If previous item was parent of this one, update previous item's leaf status
            if stack:
                 # Find the last item added to tree_list which corresponds to stack[-1]
                 # Actually, simplify: if we added a child, the parent (stack top) is not a leaf.
                 # We can't easily track back to the dict object unless we keep it in stack.
                 pass

            # Push current to stack
            stack.append((code, level))
            
        # Post-process to identifying leaves (visual polish, optional)
        # Simple scan: if next item.level > current.level, current is not leaf.
        for i in range(len(tree_list) - 1):
            if tree_list[i+1]['level'] > tree_list[i]['level']:
                tree_list[i]['is_leaf'] = False
                
        context['tree_nodes'] = tree_list
        return context


class BudgetHeadCreateView(LoginRequiredMixin, AdminRequiredMixin, CreateView):
    """Create new Budget Head."""
    model = BudgetHead
    form_class = BudgetHeadForm
    template_name = 'finance/budget_head_form.html'
    success_url = reverse_lazy('budgeting:setup_coa_list')

    def form_valid(self, form):
        messages.success(self.request, _('Budget Head created successfully.'))
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = _('Add New Budget Head')
        context['back_url'] = self.success_url
        return context


class BudgetHeadUpdateView(LoginRequiredMixin, AdminRequiredMixin, UpdateView):
    """Update Budget Head."""
    model = BudgetHead
    form_class = BudgetHeadForm
    template_name = 'finance/budget_head_form.html'
    success_url = reverse_lazy('budgeting:setup_coa_list')

    def form_valid(self, form):
        messages.success(self.request, _('Budget Head updated successfully.'))
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = _('Edit Budget Head')
        context['back_url'] = self.success_url
        return context


class BudgetHeadDeleteView(LoginRequiredMixin, AdminRequiredMixin, DeleteView):
    """Delete Budget Head."""
    model = BudgetHead
    template_name = 'finance/budget_head_confirm_delete.html'
    success_url = reverse_lazy('budgeting:setup_coa_list')

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, _('Budget Head deleted successfully.'))
        return super().delete(request, *args, **kwargs)
