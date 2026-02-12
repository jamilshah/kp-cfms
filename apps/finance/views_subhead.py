"""
Views for SubHead (Level 5) Management
"""
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q, Count
from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView
from django.utils.translation import gettext_lazy as _

from apps.finance.models import SubHead, NAMHead, AccountType
from apps.finance.forms import SubHeadForm
from apps.users.permissions import SuperAdminRequiredMixin


class SubHeadListView(LoginRequiredMixin, SuperAdminRequiredMixin, ListView):
    """
    List all Sub-Heads (Level 5) with filtering options.
    """
    model = SubHead
    template_name = 'finance/subhead_list.html'
    context_object_name = 'subheads'
    paginate_by = 50
    
    def get_queryset(self):
        queryset = SubHead.objects.select_related(
            'nam_head',
            'nam_head__minor',
            'nam_head__minor__major'
        ).order_by('nam_head__code', 'sub_code')
        
        # Filter by NAM head
        nam_head_id = self.request.GET.get('nam_head')
        if nam_head_id:
            queryset = queryset.filter(nam_head_id=nam_head_id)
        
        # Filter by account type
        account_type = self.request.GET.get('account_type')
        if account_type and account_type in dict(AccountType.choices):
            queryset = queryset.filter(nam_head__account_type=account_type)
        
        # Filter by active status
        status = self.request.GET.get('status')
        if status == 'active':
            queryset = queryset.filter(is_active=True)
        elif status == 'inactive':
            queryset = queryset.filter(is_active=False)
        
        # Search by code or name
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(nam_head__code__icontains=search) |
                Q(sub_code__icontains=search) |
                Q(name__icontains=search) |
                Q(description__icontains=search)
            )
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Provide NAM heads for filtering
        context['nam_heads'] = NAMHead.objects.filter(
            is_active=True
        ).select_related('minor__major').order_by('code')
        
        context['account_types'] = AccountType.choices
        
        # Current filter values
        context['selected_nam_head'] = self.request.GET.get('nam_head', '')
        context['selected_account_type'] = self.request.GET.get('account_type', '')
        context['selected_status'] = self.request.GET.get('status', '')
        context['search_query'] = self.request.GET.get('search', '')
        
        # Statistics
        context['total_count'] = SubHead.objects.count()
        context['active_count'] = SubHead.objects.filter(is_active=True).count()
        context['inactive_count'] = SubHead.objects.filter(is_active=False).count()
        
        # NAM heads with sub-heads
        context['nam_heads_with_subs'] = NAMHead.objects.filter(
            sub_heads__isnull=False
        ).distinct().count()
        
        # Build query string for pagination
        query_params = []
        for key, value in self.request.GET.items():
            if key != 'page' and value:
                query_params.append(f'{key}={value}')
        context['query_string'] = '&' + '&'.join(query_params) if query_params else ''
        
        return context


class SubHeadCreateView(LoginRequiredMixin, SuperAdminRequiredMixin, CreateView):
    """
    Create a new Sub-Head (Level 5).
    """
    model = SubHead
    form_class = SubHeadForm
    template_name = 'finance/subhead_form.html'
    success_url = reverse_lazy('finance:subhead_list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = _('Create Sub-Head')
        context['submit_text'] = _('Create Sub-Head')
        return context
    
    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(
            self.request,
            _(f'Sub-Head {self.object.code} created successfully. '
              f'Parent NAM Head {self.object.nam_head.code} now accepts posting only via sub-heads.')
        )
        return response


class SubHeadUpdateView(LoginRequiredMixin, SuperAdminRequiredMixin, UpdateView):
    """
    Edit an existing Sub-Head (Level 5).
    """
    model = SubHead
    form_class = SubHeadForm
    template_name = 'finance/subhead_form.html'
    success_url = reverse_lazy('finance:subhead_list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = _(f'Edit Sub-Head: {self.object.code}')
        context['submit_text'] = _('Update Sub-Head')
        return context
    
    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(
            self.request,
            _(f'Sub-Head {self.object.code} updated successfully.')
        )
        return response
